from __future__ import annotations

import argparse
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from functools import partial

from .analysis import run_analysis
from .analysis_client import QwenEvaluationClient
from .basin_observer import BasinObserverClient, run_basin_observer
from .dossier import build_checkpoint_dossier
from .evaluator_compare import build_evaluator_comparison, build_judge_auditor_review, parse_analysis_spec, snapshot_analysis
from .forge import ForgeClient
from .generation import run_generation_suite
from .manifest import load_suite
from .observer_qualification import build_observer_qualification
from .provenance import extract_png_provenance, extract_run_png_provenance
from .reporting import build_report
from .style_observer import StyleObserverClient, run_style_observer
from .semantic_observer import SparseSemanticObserverClient, build_sparse_semantic_comparison, run_sparse_semantic_observer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Checkpoint Evaluation Framework runner.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    probe = subparsers.add_parser("probe-forge", help="Probe a Forge/A1111-compatible backend.")
    probe.add_argument("--base-url", default="http://127.0.0.1:7860")
    probe.add_argument("--timeout", default=30, type=int)

    generate = subparsers.add_parser("generate", help="Generate a CEF run from a manifest.")
    generate.add_argument("--manifest", required=True, type=Path)
    generate.add_argument("--output-root", default=Path("cef_runs"), type=Path)
    generate.add_argument("--base-url", default="http://127.0.0.1:7860")
    generate.add_argument("--timeout", default=180, type=int)
    generate.add_argument("--run-id")
    generate.add_argument("--dry-run", action="store_true")
    generation_reuse = generate.add_mutually_exclusive_group()
    generation_reuse.add_argument(
        "--resume",
        action="store_true",
        help="Reuse a matching run and skip cells with complete generation metadata and image files.",
    )
    generation_reuse.add_argument(
        "--overwrite",
        action="store_true",
        help="Regenerate every cell in an existing run only when its manifest snapshot still matches.",
    )

    analyze = subparsers.add_parser("analyze", help="Analyze a generated CEF run with an OpenAI-compatible vision model.")
    analyze.add_argument("--run-root", required=True, type=Path)
    analyze.add_argument("--directive", required=True, type=Path)
    analyze.add_argument("--endpoint", default="http://127.0.0.1:8000/v1/chat/completions")
    analyze.add_argument("--model", required=True)
    analyze.add_argument("--api-key")
    analyze.add_argument("--temperature", default=0.1, type=float)
    analyze.add_argument("--max-tokens", default=3000, type=int)
    analyze.add_argument(
        "--response-mode",
        choices=["json", "markdown"],
        default="json",
        help="Parse evaluator output as strict JSON or as a structured Markdown evaluator note.",
    )
    analyze.add_argument("--timeout", default=180, type=int)
    analyze.add_argument(
        "--no-response-format",
        action="store_true",
        help="Do not send JSON schema response_format. Useful for evaluator models that fail with schema-constrained output.",
    )
    analyze.add_argument("--overwrite", action="store_true")
    analyze.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Write evaluator-failure records instead of aborting when a model times out or returns invalid JSON.",
    )
    analyze.add_argument(
        "--compare-reference-assist",
        action="store_true",
        help="For tests with references, also run an unassisted Qwen pass and report assisted/unassisted deltas.",
    )
    analyze.add_argument(
        "--test-id",
        action="append",
        help="Analyze only the given test ID. Repeat to create small evaluator sanity batches.",
    )

    report = subparsers.add_parser("report", help="Build a CEF report from an analyzed run.")
    report.add_argument("--run-root", required=True, type=Path)

    snapshot = subparsers.add_parser("snapshot-analysis", help="Snapshot the current analysis index under an evaluator ID.")
    snapshot.add_argument("--run-root", required=True, type=Path)
    snapshot.add_argument("--analysis-id", required=True)
    snapshot.add_argument("--label")
    snapshot.add_argument("--model-name")
    snapshot.add_argument("--endpoint")
    snapshot.add_argument("--directive-used")

    compare = subparsers.add_parser("compare-evaluators", help="Build a side-by-side report for multiple evaluator analyses.")
    compare.add_argument("--run-root", required=True, type=Path)
    compare.add_argument(
        "--analysis",
        action="append",
        required=True,
        help="Evaluator analysis spec: id=path or id=label=path. Repeat for each evaluator.",
    )
    compare.add_argument("--output-name", default="evaluator_comparison.html")

    judge = subparsers.add_parser("judge-auditor", help="Build a primary-judge / secondary-auditor human review queue.")
    judge.add_argument("--run-root", required=True, type=Path)
    judge.add_argument("--primary", required=True, help="Primary analysis spec: id=label=path.")
    judge.add_argument("--auditor", required=True, help="Auditor analysis spec: id=label=path.")
    judge.add_argument("--output-stem", default="judge_auditor_review_queue")

    observer = subparsers.add_parser(
        "observer-qualification",
        help="Build observer cards and a production roster from evaluator/observer analysis snapshots.",
    )
    observer.add_argument(
        "--analysis",
        action="append",
        required=True,
        help="Observer analysis spec: id=path or id=label=path. Repeat for each observer.",
    )
    observer.add_argument("--output-root", required=True, type=Path)
    observer.add_argument("--reference-set", type=Path)
    observer.add_argument("--title", default="CEF Observer Qualification Report")

    observe_style = subparsers.add_parser(
        "observe-style",
        help="Run a score-free literal style observer against generated images and references.",
    )
    observe_style.add_argument("--run-root", required=True, type=Path)
    observe_style.add_argument("--directive", required=True, type=Path)
    observe_style.add_argument("--observer-id", required=True)
    observe_style.add_argument("--label", required=True)
    observe_style.add_argument("--endpoint", default="http://127.0.0.1:1234")
    observe_style.add_argument("--model", required=True)
    observe_style.add_argument("--api-key")
    observe_style.add_argument("--temperature", default=0.1, type=float)
    observe_style.add_argument("--max-tokens", default=1600, type=int)
    observe_style.add_argument("--timeout", default=600, type=int)
    observe_style.add_argument("--no-response-format", action="store_true")
    observe_style.add_argument("--overwrite", action="store_true")
    observe_style.add_argument("--continue-on-error", action="store_true")
    observe_style.add_argument("--test-id", action="append")
    observe_style.add_argument("--lora-profile-id", action="append")
    observe_style.add_argument(
        "--case",
        action="append",
        help="Observe one exact PROFILE_ID:TEST_ID pair. Repeat for a qualification slice.",
    )

    observe_semantic = subparsers.add_parser(
        "observe-semantic",
        help="Run a score-free Sparse Semantic Probe observer and export CPF-ready records.",
    )
    observe_semantic.add_argument("--run-root", required=True, type=Path)
    observe_semantic.add_argument("--directive", required=True, type=Path)
    observe_semantic.add_argument("--observer-id", required=True)
    observe_semantic.add_argument("--label", required=True)
    observe_semantic.add_argument("--endpoint", default="http://127.0.0.1:1234")
    observe_semantic.add_argument("--model", required=True)
    observe_semantic.add_argument("--api-key")
    observe_semantic.add_argument("--temperature", default=0.1, type=float)
    observe_semantic.add_argument("--max-tokens", default=2200, type=int)
    observe_semantic.add_argument("--timeout", default=600, type=int)
    observe_semantic.add_argument(
        "--observer-schema",
        choices=["sparse-semantic", "semantic-agency-gradient"],
        default="sparse-semantic",
        help="Structured response schema to request from the observer model.",
    )
    observe_semantic.add_argument("--no-response-format", action="store_true")
    observe_semantic.add_argument("--overwrite", action="store_true")
    observe_semantic.add_argument("--continue-on-error", action="store_true")
    observe_semantic.add_argument("--test-id", action="append")

    observe_basin = subparsers.add_parser(
        "observe-basin",
        help="Run a score-free SSP basin observer against generated images.",
    )
    observe_basin.add_argument("--run-root", required=True, type=Path)
    observe_basin.add_argument("--directive", required=True, type=Path)
    observe_basin.add_argument("--observer-id", required=True)
    observe_basin.add_argument("--label", required=True)
    observe_basin.add_argument("--endpoint", default="http://127.0.0.1:1234")
    observe_basin.add_argument("--model", required=True)
    observe_basin.add_argument("--api-key")
    observe_basin.add_argument("--temperature", default=0.1, type=float)
    observe_basin.add_argument("--max-tokens", default=2200, type=int)
    observe_basin.add_argument("--timeout", default=600, type=int)
    observe_basin.add_argument("--no-response-format", action="store_true")
    observe_basin.add_argument("--overwrite", action="store_true")
    observe_basin.add_argument("--continue-on-error", action="store_true")
    observe_basin.add_argument("--test-id", action="append")

    compare_ssp = subparsers.add_parser(
        "compare-ssp",
        help="Build a descriptive cross-checkpoint Sparse Semantic Probe comparison.",
    )
    compare_ssp.add_argument("--observer-index", action="append", required=True, type=Path)
    compare_ssp.add_argument("--output-root", required=True, type=Path)
    compare_ssp.add_argument("--title", default="CEF Sparse Semantic Probe Comparison")

    provenance = subparsers.add_parser(
        "extract-provenance",
        help="Extract Forge/A1111-style PNG metadata from one image or a generated CEF run.",
    )
    provenance_scope = provenance.add_mutually_exclusive_group(required=True)
    provenance_scope.add_argument("--run-root", type=Path)
    provenance_scope.add_argument("--image", type=Path)
    provenance.add_argument(
        "--output",
        type=Path,
        help="Optional output JSON path for --image mode. Run mode always writes png_provenance_index.json in the run folder.",
    )

    dossier = subparsers.add_parser("dossier", help="Build a checkpoint-level evaluation dossier from suite reports.")
    dossier.add_argument(
        "--run-root",
        action="append",
        required=True,
        type=Path,
        help="Suite run folder to include. Repeat for each suite.",
    )
    dossier.add_argument("--output-root", required=True, type=Path)
    dossier.add_argument("--title")
    dossier.add_argument("--checkpoint-id")
    dossier.add_argument("--schema-version", default="1.0")
    dossier.add_argument("--interpretation-mode", help="Human-adjudicated categorical Mode of Interpretation.")
    dossier.add_argument("--interpretation-mode-note", help="Evidence note for a human-adjudicated interpretation mode.")
    dossier.add_argument("--ssp-index", action="append", type=Path, help="Attach a score-free SSP observer index. Repeat for multiple observers.")

    serve = subparsers.add_parser("serve-report", help="Serve a run folder over a local HTTP server.")
    serve.add_argument("--run-root", required=True, type=Path)
    serve.add_argument("--port", default=8767, type=int)
    serve.add_argument("--bind", default="127.0.0.1")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "probe-forge":
        client = ForgeClient(args.base_url, timeout=args.timeout)
        payload = {
            "version": client.version(),
            "options": _option_summary(client.options()),
            "model_count": len(client.models()),
            "lora_count": len(client.loras()),
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    if args.command == "generate":
        suite = load_suite(args.manifest)
        client = ForgeClient(args.base_url, timeout=args.timeout)
        run_root = run_generation_suite(
            suite=suite,
            output_root=args.output_root,
            forge=client,
            run_id=args.run_id,
            dry_run=args.dry_run,
            resume=args.resume,
            overwrite=args.overwrite,
        )
        print(json.dumps({"run_root": str(run_root)}, indent=2))
        return 0

    if args.command == "analyze":
        client = QwenEvaluationClient(
            endpoint=args.endpoint,
            model=args.model,
            api_key=args.api_key,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            timeout=args.timeout,
            use_response_format=not args.no_response_format and args.response_mode == "json",
            response_mode=args.response_mode,
        )
        report = run_analysis(
            run_root=args.run_root,
            directive_path=args.directive,
            client=client,
            overwrite=args.overwrite,
            compare_reference_assist=args.compare_reference_assist,
            test_ids=args.test_id,
            continue_on_error=args.continue_on_error,
        )
        print(json.dumps({"analysis_index": str(args.run_root / "analysis_index.json"), "analyzed_images": report["analyzed_images"]}, indent=2))
        return 0

    if args.command == "report":
        report = build_report(args.run_root)
        print(json.dumps({"report_html": str(args.run_root / "report.html"), "records": len(report["records"])}, indent=2))
        return 0

    if args.command == "snapshot-analysis":
        analysis_index = snapshot_analysis(
            args.run_root,
            args.analysis_id,
            args.label,
            model_name=args.model_name,
            endpoint=args.endpoint,
            directive_used=args.directive_used,
        )
        print(json.dumps({"analysis_index": str(analysis_index)}, indent=2))
        return 0

    if args.command == "compare-evaluators":
        analyses = [parse_analysis_spec(value) for value in args.analysis]
        output = build_evaluator_comparison(args.run_root, analyses, args.output_name)
        print(json.dumps({"comparison_html": str(output), "evaluators": len(analyses)}, indent=2))
        return 0

    if args.command == "judge-auditor":
        json_path, md_path = build_judge_auditor_review(
            args.run_root,
            parse_analysis_spec(args.primary),
            parse_analysis_spec(args.auditor),
            args.output_stem,
        )
        print(json.dumps({"review_json": str(json_path), "review_markdown": str(md_path)}, indent=2))
        return 0

    if args.command == "observer-qualification":
        report = build_observer_qualification(
            analyses=[parse_analysis_spec(value) for value in args.analysis],
            output_root=args.output_root,
            reference_set=args.reference_set,
            title=args.title,
        )
        print(
            json.dumps(
                {
                    "observer_qualification_html": str(args.output_root / "observer_qualification.html"),
                    "observer_qualification_json": str(args.output_root / "observer_qualification.json"),
                    "observers": report["summary"]["observer_count"],
                },
                indent=2,
            )
        )
        return 0

    if args.command == "observe-style":
        client = StyleObserverClient(
            endpoint=args.endpoint,
            model=args.model,
            api_key=args.api_key,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            timeout=args.timeout,
            use_response_format=not args.no_response_format,
            observer_schema=args.observer_schema,
        )
        index = run_style_observer(
            run_root=args.run_root,
            directive_path=args.directive,
            client=client,
            observer_id=args.observer_id,
            label=args.label,
            overwrite=args.overwrite,
            test_ids=args.test_id,
            lora_profile_ids=args.lora_profile_id,
            cases=args.case,
            continue_on_error=args.continue_on_error,
        )
        print(
            json.dumps(
                {
                    "observer_index": str(args.run_root / "observer_runs" / args.observer_id / "observer_index.json"),
                    "observed_images": index["observed_images"],
                    "failures": index["failures"],
                },
                indent=2,
            )
        )
        return 0

    if args.command == "observe-semantic":
        client = SparseSemanticObserverClient(
            endpoint=args.endpoint,
            model=args.model,
            api_key=args.api_key,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            timeout=args.timeout,
            use_response_format=not args.no_response_format,
        )
        index = run_sparse_semantic_observer(
            run_root=args.run_root,
            directive_path=args.directive,
            client=client,
            observer_id=args.observer_id,
            label=args.label,
            overwrite=args.overwrite,
            test_ids=args.test_id,
            continue_on_error=args.continue_on_error,
        )
        output_root = args.run_root / "observer_runs" / args.observer_id
        print(json.dumps({
            "observer_index": str(output_root / "ssp_observer_index.json"),
            "behavioral_observation_records": str(output_root / "behavioral_observation_records.json"),
            "report_html": str(output_root / "ssp_report.html"),
            "observed_images": index["observed_images"],
            "failures": index["failures"],
        }, indent=2))
        return 0

    if args.command == "observe-basin":
        client = BasinObserverClient(
            endpoint=args.endpoint,
            model=args.model,
            api_key=args.api_key,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            timeout=args.timeout,
            use_response_format=not args.no_response_format,
        )
        index = run_basin_observer(
            run_root=args.run_root,
            directive_path=args.directive,
            client=client,
            observer_id=args.observer_id,
            label=args.label,
            overwrite=args.overwrite,
            test_ids=args.test_id,
            continue_on_error=args.continue_on_error,
        )
        output_root = args.run_root / "observer_runs" / args.observer_id
        print(json.dumps({
            "observer_index": str(output_root / "basin_observer_index.json"),
            "observed_images": index["observed_images"],
            "failures": index["failures"],
        }, indent=2))
        return 0

    if args.command == "compare-ssp":
        comparison = build_sparse_semantic_comparison(args.observer_index, args.output_root, args.title)
        print(json.dumps({
            "comparison_json": str(args.output_root / "ssp_comparison.json"),
            "comparison_html": str(args.output_root / "ssp_comparison.html"),
            "checkpoints": len(comparison["checkpoints"]),
        }, indent=2))
        return 0

    if args.command == "extract-provenance":
        if args.run_root:
            index = extract_run_png_provenance(args.run_root)
            print(json.dumps({
                "provenance_index": str(args.run_root / "png_provenance_index.json"),
                "image_count": index["image_count"],
                "failures": index["failure_count"],
            }, indent=2))
            return 0
        record = extract_png_provenance(args.image)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
        print(json.dumps({
            "image": str(args.image),
            "output": str(args.output) if args.output else None,
            "png_text_keys": record["png_text_keys"],
            "parsed_setting_keys": sorted(record.get("parsed_parameters", {}).get("settings", {})),
        }, indent=2))
        return 0

    if args.command == "dossier":
        dossier = build_checkpoint_dossier(
            run_roots=args.run_root,
            output_root=args.output_root,
            title=args.title,
            checkpoint_id=args.checkpoint_id,
            schema_version=args.schema_version,
            interpretation_mode=args.interpretation_mode,
            interpretation_mode_note=args.interpretation_mode_note,
            ssp_indexes=args.ssp_index,
        )
        print(
            json.dumps(
                {
                    "dossier_html": str(args.output_root / "dossier.html"),
                    "dossier_json": str(args.output_root / "dossier.json"),
                    "suites": dossier["summary"]["suite_count"],
                    "images": dossier["summary"]["image_count"],
                    "schema_version": dossier["schema_version"],
                },
                indent=2,
            )
        )
        return 0

    if args.command == "serve-report":
        run_root = args.run_root.resolve()
        if not run_root.exists():
            raise FileNotFoundError(f"Run folder does not exist: {run_root}")
        handler = partial(SimpleHTTPRequestHandler, directory=str(run_root))
        server = ThreadingHTTPServer((args.bind, args.port), handler)
        print(json.dumps({"serving": str(run_root), "url": f"http://{args.bind}:{args.port}/"}, indent=2), flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            return 0

    raise ValueError(f"Unknown command: {args.command}")


def _option_summary(options: dict) -> dict:
    return {
        "checkpoint": options.get("sd_model_checkpoint"),
        "checkpoint_hash": options.get("sd_checkpoint_hash"),
        "sampler": options.get("xl_t2i_sampler") or options.get("sd_t2i_sampler"),
        "steps": options.get("xl_t2i_step") or options.get("sd_t2i_step"),
        "cfg": options.get("xl_t2i_cfg") or options.get("sd_t2i_cfg"),
        "version_uid": options.get("VERSION_UID"),
        "forge_preset": options.get("forge_preset"),
    }


if __name__ == "__main__":
    raise SystemExit(main())
