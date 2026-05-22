from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.api.rayzaa_api.config import settings
from apps.api.rayzaa_api.services.fraud import FraudScorer


def main() -> None:
    started = time.perf_counter()
    scorer = FraudScorer()
    init_elapsed = time.perf_counter() - started

    vector = {name: 0.0 for name in scorer.feature_names}
    started = time.perf_counter()
    score, explanation = scorer.score(vector)
    explain_elapsed = time.perf_counter() - started

    report = {
        "artifact_dir": str(settings.artifact_dir),
        "bundle_id": scorer.bundle_id,
        "mode": settings.model_mode,
        "background_size": settings.shap_background_size,
        "init_s": round(init_elapsed, 3),
        "first_score_s": round(explain_elapsed, 3),
        "score": score,
        "top_features": [row["feature"] for row in explanation[:3]],
        "metadata": scorer.metadata,
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
