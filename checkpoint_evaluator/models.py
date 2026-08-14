from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class Criterion:
    id: str
    description: str

    @classmethod
    def from_value(cls, index: int, value: Any) -> "Criterion":
        if isinstance(value, str):
            return cls(id=f"criterion_{index:02d}", description=value)
        if isinstance(value, dict):
            description = str(value.get("description") or value.get("criterion") or value.get("name") or "").strip()
            if not description:
                raise ValueError(f"Criterion {index} is missing description text.")
            return cls(id=str(value.get("id") or f"criterion_{index:02d}"), description=description)
        raise TypeError(f"Criterion {index} must be a string or object.")

    def to_dict(self) -> dict[str, str]:
        return {"id": self.id, "description": self.description}


@dataclass(slots=True)
class LoraSpec:
    name: str
    weight: float = 1.0

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "LoraSpec":
        return cls(name=str(data["name"]), weight=float(data.get("weight", 1.0)))

    def to_prompt_token(self) -> str:
        return f"<lora:{self.name}:{self.weight:g}>"

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "weight": self.weight}


@dataclass(slots=True)
class LoraProfile:
    id: str
    loras: list[LoraSpec] = field(default_factory=list)

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "LoraProfile":
        return cls(
            id=str(data["id"]),
            loras=[LoraSpec.from_mapping(item) for item in data.get("loras", [])],
        )

    def prompt_suffix(self) -> str:
        return " ".join(lora.to_prompt_token() for lora in self.loras)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "loras": [lora.to_dict() for lora in self.loras]}


@dataclass(slots=True)
class CheckpointProfile:
    id: str
    title: str

    @classmethod
    def from_value(cls, value: Any) -> "CheckpointProfile":
        if isinstance(value, str):
            stem = Path(value).stem
            return cls(id=_slug(stem), title=value)
        if isinstance(value, dict):
            title = str(value.get("title") or value.get("checkpoint") or value.get("name") or "").strip()
            if not title:
                raise ValueError("Checkpoint entry is missing title.")
            return cls(id=str(value.get("id") or _slug(Path(title).stem)), title=title)
        raise TypeError("Checkpoint entries must be strings or objects.")

    def to_dict(self) -> dict[str, str]:
        return {"id": self.id, "title": self.title}


@dataclass(slots=True)
class GenerationSettings:
    negative_prompt: str = ""
    steps: int = 24
    cfg_scale: float = 4.5
    width: int = 1024
    height: int = 1024
    sampler_name: str = "Euler a"
    scheduler: str | None = None
    seed: int = -1
    batch_size: int = 1
    n_iter: int = 1

    @classmethod
    def from_mapping(cls, data: dict[str, Any] | None) -> "GenerationSettings":
        data = data or {}
        return cls(
            negative_prompt=str(data.get("negative_prompt", "")),
            steps=int(data.get("steps", 24)),
            cfg_scale=float(data.get("cfg_scale", 4.5)),
            width=int(data.get("width", 1024)),
            height=int(data.get("height", 1024)),
            sampler_name=str(data.get("sampler_name", "Euler a")),
            scheduler=str(data["scheduler"]) if data.get("scheduler") is not None else None,
            seed=int(data.get("seed", -1)),
            batch_size=int(data.get("batch_size", 1)),
            n_iter=int(data.get("n_iter", 1)),
        )

    def merged(self, data: dict[str, Any] | None) -> "GenerationSettings":
        merged = self.to_dict()
        merged.update(data or {})
        return GenerationSettings.from_mapping(merged)

    def to_dict(self) -> dict[str, Any]:
        return {
            "negative_prompt": self.negative_prompt,
            "steps": self.steps,
            "cfg_scale": self.cfg_scale,
            "width": self.width,
            "height": self.height,
            "sampler_name": self.sampler_name,
            "scheduler": self.scheduler,
            "seed": self.seed,
            "batch_size": self.batch_size,
            "n_iter": self.n_iter,
        }


@dataclass(slots=True)
class ReferenceImage:
    # Reference images are calibration aids for Qwen, not additional images to score.
    label: str
    path: str
    purpose: str = ""

    @classmethod
    def from_value(cls, index: int, value: Any) -> "ReferenceImage":
        if isinstance(value, str):
            return cls(label=f"reference_{index:02d}", path=value)
        if isinstance(value, dict):
            path = str(value.get("path") or "").strip()
            if not path:
                raise ValueError(f"Reference image {index} is missing a path.")
            return cls(
                label=str(value.get("label") or f"reference_{index:02d}"),
                path=path,
                purpose=str(value.get("purpose") or ""),
            )
        raise TypeError(f"Reference image {index} must be a string or object.")

    def to_dict(self) -> dict[str, str]:
        return {"label": self.label, "path": self.path, "purpose": self.purpose}


@dataclass(slots=True)
class TestCase:
    id: str
    name: str
    prompt: str
    criteria: list[Criterion]
    settings: dict[str, Any] = field(default_factory=dict)
    category: str = ""
    purpose: str = ""
    reference_images: list[ReferenceImage] = field(default_factory=list)
    reference_instruction: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "TestCase":
        test_id = str(data["id"])
        criteria = [Criterion.from_value(index, value) for index, value in enumerate(data.get("criteria", []), start=1)]
        return cls(
            id=test_id,
            name=str(data.get("name") or test_id),
            prompt=str(data["prompt"]),
            criteria=criteria,
            settings=dict(data.get("settings", {})),
            category=str(data.get("category", "")),
            purpose=str(data.get("purpose", "")),
            reference_images=[
                ReferenceImage.from_value(index, value)
                for index, value in enumerate(data.get("reference_images", []), start=1)
            ],
            reference_instruction=str(data.get("reference_instruction", "")),
            metadata=dict(data.get("metadata", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "prompt": self.prompt,
            "criteria": [criterion.to_dict() for criterion in self.criteria],
            "settings": self.settings,
            "category": self.category,
            "purpose": self.purpose,
            "reference_images": [reference.to_dict() for reference in self.reference_images],
            "reference_instruction": self.reference_instruction,
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class TestSuite:
    suite_id: str
    name: str
    checkpoints: list[CheckpointProfile]
    lora_profiles: list[LoraProfile]
    defaults: GenerationSettings
    tests: list[TestCase]
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "TestSuite":
        suite_id = str(data["suite_id"])
        lora_profiles = [LoraProfile.from_mapping(item) for item in data.get("lora_profiles", [])]
        if not lora_profiles:
            lora_profiles = [LoraProfile(id="none")]
        return cls(
            suite_id=suite_id,
            name=str(data.get("name") or suite_id),
            checkpoints=[CheckpointProfile.from_value(item) for item in data.get("checkpoints", [])],
            lora_profiles=lora_profiles,
            defaults=GenerationSettings.from_mapping(data.get("defaults")),
            tests=[TestCase.from_mapping(item) for item in data.get("tests", [])],
            metadata=dict(data.get("metadata", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "suite_id": self.suite_id,
            "name": self.name,
            "checkpoints": [checkpoint.to_dict() for checkpoint in self.checkpoints],
            "lora_profiles": [profile.to_dict() for profile in self.lora_profiles],
            "defaults": self.defaults.to_dict(),
            "tests": [test.to_dict() for test in self.tests],
            "metadata": self.metadata,
        }


def _slug(value: str) -> str:
    normalized = "".join(ch.lower() if ch.isalnum() else "_" for ch in value)
    parts = [part for part in normalized.split("_") if part]
    return "_".join(parts) or "checkpoint"
