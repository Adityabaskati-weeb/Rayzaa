from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.api.rayzaa_api.config import settings
from apps.api.rayzaa_api.services.fraud import FraudScorer
from apps.api.rayzaa_api.services.model_artifact import copy_artifact_bundle, validate_artifact_bundle


def main() -> None:
    scorer = FraudScorer()
    report = scorer.warmup()
    approved_source_seeded = False
    approved_source = Path(settings.approved_artifact_source) if settings.approved_artifact_source else None
    if approved_source and scorer.manifest:
        validate_artifact_bundle(scorer.model_dir, scorer.manifest)
        approved_source_valid = approved_source.exists()
        if approved_source_valid:
            try:
                validate_artifact_bundle(approved_source, scorer.manifest)
            except Exception:
                approved_source_valid = False
        if not approved_source_valid:
            copy_artifact_bundle(scorer.model_dir, approved_source, scorer.manifest)
            approved_source_seeded = True
    report.update(
        {
            "artifactDir": str(settings.artifact_dir),
            "manifestPath": str(settings.artifact_manifest_path),
            "approvedArtifactSource": str(approved_source) if approved_source else "",
            "approvedArtifactSourceSeeded": approved_source_seeded,
            "allowAutotrain": settings.allow_artifact_autotrain,
            "enforceManifest": settings.enforce_artifact_manifest,
        }
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
