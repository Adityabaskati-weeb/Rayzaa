from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any


class ModelArtifactError(RuntimeError):
    pass


def load_artifact_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ModelArtifactError(f"Artifact manifest not found at {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ModelArtifactError(f"Artifact manifest at {path} is invalid JSON: {exc}") from exc
    if "bundle_id" not in payload or "files" not in payload:
        raise ModelArtifactError(f"Artifact manifest at {path} is missing required bundle metadata.")
    return payload


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def required_files(manifest: dict[str, Any]) -> list[str]:
    files = manifest.get("files", {})
    return [str(name) for name in files.keys()]


def validate_artifact_bundle(bundle_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    if not bundle_dir.exists():
        raise ModelArtifactError(f"Locked artifact bundle is missing: {bundle_dir}")

    report: dict[str, Any] = {
        "bundleId": manifest["bundle_id"],
        "bundleDir": str(bundle_dir),
        "verifiedFiles": [],
    }
    for file_name, expected in manifest.get("files", {}).items():
        path = bundle_dir / file_name
        if not path.exists():
            raise ModelArtifactError(f"Artifact bundle {bundle_dir} is missing required file {file_name}")
        actual_size = path.stat().st_size
        expected_size = int(expected.get("size", actual_size))
        if actual_size != expected_size:
            raise ModelArtifactError(
                f"Artifact file {path} has size {actual_size}, expected {expected_size}"
            )
        actual_hash = sha256_file(path)
        expected_hash = str(expected.get("sha256", "")).lower()
        if expected_hash and actual_hash.lower() != expected_hash:
            raise ModelArtifactError(
                f"Artifact file {path} failed checksum validation. Expected {expected_hash}, got {actual_hash}"
            )
        report["verifiedFiles"].append(
            {
                "name": file_name,
                "size": actual_size,
                "sha256": actual_hash,
            }
        )
    return report


def write_runtime_manifest(bundle_dir: Path, manifest: dict[str, Any]) -> None:
    bundle_dir.mkdir(parents=True, exist_ok=True)
    (bundle_dir / "artifact_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def copy_artifact_bundle(source_dir: Path, target_dir: Path, manifest: dict[str, Any]) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    for file_name in required_files(manifest):
        shutil.copy2(source_dir / file_name, target_dir / file_name)
    write_runtime_manifest(target_dir, manifest)


def discover_artifact_sources(bundle_id: str, explicit_source: str, workspace_root: Path) -> list[Path]:
    candidates: list[Path] = []
    if explicit_source:
        candidates.append(Path(explicit_source))
    candidates.append(workspace_root / ".runtime" / "benchmark" / "benchmark" / "artifacts" / "fraud_model" / bundle_id)
    candidates.append(Path(tempfile.gettempdir()) / "rayzaa" / "artifacts" / "fraud_model" / bundle_id)

    ordered: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = str(candidate.resolve()) if candidate.exists() else str(candidate)
        if normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(candidate)
    return ordered
