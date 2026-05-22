from __future__ import annotations

import csv
import json
import math
import random
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import joblib
import numpy as np

from ..config import settings
from ..taxonomy import CANONICAL_PAYMENT_RAILS, canonicalize_payment_rail, payment_rail_label
from .model_artifact import (
    ModelArtifactError,
    copy_artifact_bundle,
    discover_artifact_sources,
    load_artifact_manifest,
    validate_artifact_bundle,
)
from .rolling_state import MemoryRollingState, RollingFeatures

if TYPE_CHECKING:
    import shap
    from xgboost import XGBClassifier


class FraudModelTrainingError(RuntimeError):
    pass


class FraudScorer:
    artifact_version = "v3"
    payment_formats = list(CANONICAL_PAYMENT_RAILS)
    feature_names = [
        "amount_log",
        "sender_velocity_1h",
        "receiver_velocity_1h",
        "pair_velocity_24h",
        "sender_unique_counterparties_24h",
        "amount_ratio_to_sender_avg",
        "hour_of_day",
        "is_cross_bank",
        "is_self_transfer",
        "is_cross_currency",
        *[f"fmt_{name}" for name in payment_formats],
    ]
    feature_labels = {
        "amount_log": "Amount scale",
        "sender_velocity_1h": "Sender velocity",
        "receiver_velocity_1h": "Receiver velocity",
        "pair_velocity_24h": "Pair velocity",
        "sender_unique_counterparties_24h": "Counterparty spread",
        "amount_ratio_to_sender_avg": "Amount vs sender average",
        "hour_of_day": "Hour of day",
        "is_cross_bank": "Cross-bank movement",
        "is_self_transfer": "Self-transfer pattern",
        "is_cross_currency": "Cross-currency movement",
        **{f"fmt_{name}": payment_rail_label(name) for name in payment_formats},
    }

    def __init__(self) -> None:
        self.mode = settings.model_mode.lower()
        self.bundle_id = settings.locked_model_bundle or f"{self.mode}_{self.artifact_version}"
        self.manifest = load_artifact_manifest(settings.artifact_manifest_path) if settings.artifact_manifest_path.exists() else {}
        if settings.enforce_artifact_manifest and not self.manifest:
            raise FraudModelTrainingError(
                f"Artifact manifest enforcement is enabled but no manifest exists at {settings.artifact_manifest_path}."
            )
        self.model_dir = settings.artifact_dir / "fraud_model" / self.bundle_id
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.model_path = self.model_dir / "xgb_model.joblib"
        self.meta_path = self.model_dir / "metadata.json"
        self.background_path = self.model_dir / "background.npy"
        self.cache_path = self.model_dir / "feature_cache.npz"
        self.cache_meta_path = self.model_dir / "feature_cache_meta.json"
        self.metadata: dict[str, Any] = {}
        self.background = np.empty((0, len(self.feature_names)), dtype=np.float32)
        self._explanation_cache: dict[tuple[float, ...], list[dict[str, float]]] = {}
        self.model = self._load_or_train_model()
        self.explainer: shap.TreeExplainer | None = None

    @staticmethod
    def _normalize_payment_format(value: str) -> str:
        return canonicalize_payment_rail(value)

    @staticmethod
    def _model_params(scale_pos_weight: float = 1.0) -> dict[str, Any]:
        return {
            "n_estimators": 120,
            "max_depth": 5,
            "learning_rate": 0.08,
            "subsample": 0.9,
            "colsample_bytree": 0.8,
            "min_child_weight": 4,
            "reg_lambda": 1.0,
            "max_delta_step": 2,
            "scale_pos_weight": scale_pos_weight,
            "objective": "binary:logistic",
            "eval_metric": "logloss",
            "random_state": 42,
        }

    def _artifact_bundle_exists(self) -> bool:
        return self.model_path.exists() and self.meta_path.exists() and self.background_path.exists()

    def _feature_cache_exists(self) -> bool:
        return self.cache_path.exists() and self.cache_meta_path.exists()

    def _ensure_locked_bundle(self) -> dict[str, Any]:
        if self.manifest:
            manifest_bundle = str(self.manifest.get("bundle_id") or "")
            if manifest_bundle and manifest_bundle != self.bundle_id:
                raise FraudModelTrainingError(
                    f"Configured model bundle {self.bundle_id} does not match approved manifest bundle {manifest_bundle}."
                )

        try:
            report = validate_artifact_bundle(self.model_dir, self.manifest)
            self.metadata["artifact_validation"] = report
            return report
        except ModelArtifactError:
            pass

        for candidate in discover_artifact_sources(self.bundle_id, settings.approved_artifact_source, settings.base_dir):
            if candidate == self.model_dir or not candidate.exists():
                continue
            try:
                validate_artifact_bundle(candidate, self.manifest)
            except ModelArtifactError:
                continue
            copy_artifact_bundle(candidate, self.model_dir, self.manifest)
            report = validate_artifact_bundle(self.model_dir, self.manifest)
            self.metadata["artifact_validation"] = report
            return report

        raise FraudModelTrainingError(
            f"Locked artifact bundle {self.bundle_id} is missing or invalid in {self.model_dir}. "
            "Run the artifact prewarm step before starting demo or dev mode."
        )

    def _load_or_train_model(self) -> Any:
        from xgboost import XGBClassifier

        if settings.rebuild_model_artifacts:
            for path in [self.model_path, self.meta_path, self.background_path, self.cache_path, self.cache_meta_path]:
                if path.exists():
                    path.unlink()

        if settings.enforce_artifact_manifest:
            self._ensure_locked_bundle()
        elif not self._artifact_bundle_exists():
            if not settings.allow_artifact_autotrain:
                self._ensure_locked_bundle()
            if not self._artifact_bundle_exists():
                if self._feature_cache_exists():
                    x, y, cache_metadata = self._load_feature_cache()
                else:
                    x, y, cache_metadata = self._build_training_rows(settings.ibm_aml_dataset_path)
                    self._persist_feature_cache(x, y, cache_metadata)
                self._train_and_persist(x, y, cache_metadata)

        model = joblib.load(self.model_path)
        self.metadata = json.loads(self.meta_path.read_text())
        self.background = np.load(self.background_path)
        if settings.enforce_artifact_manifest:
            self.metadata["artifact_validation"] = validate_artifact_bundle(self.model_dir, self.manifest)
        return model

    def _ensure_explainer(self) -> Any | None:
        if self.explainer is not None:
            return self.explainer
        try:
            import shap

            background = self.background if len(self.background) else None
            self.explainer = shap.TreeExplainer(
                self.model,
                data=background,
                model_output="probability",
                feature_perturbation="interventional" if background is not None else "tree_path_dependent",
            )
        except Exception:
            self.explainer = None
        return self.explainer

    def _sampling_config(self) -> dict[str, int | None]:
        if self.mode == "full":
            return {"row_limit": None, "negative_cap": 60000}
        return {
            "row_limit": settings.benchmark_row_cap,
            "negative_cap": settings.benchmark_negative_cap,
        }

    def _count_labels(self, dataset_path: Path, row_limit: int | None = None) -> dict[str, Any]:
        counts = {"0": 0, "1": 0}
        rail_counts = {rail: {"0": 0, "1": 0} for rail in self.payment_formats}
        with dataset_path.open(newline="", encoding="utf-8") as handle:
            reader = csv.reader(handle)
            next(reader)
            for row_index, row in enumerate(reader, start=1):
                label = row[-1]
                rail = self._normalize_payment_format(row[9])
                counts[label] += 1
                if rail not in rail_counts:
                    rail_counts[rail] = {"0": 0, "1": 0}
                rail_counts[rail][label] += 1
                if row_limit and row_index >= row_limit:
                    break
        return {"total": counts, "by_rail": rail_counts}

    @staticmethod
    def _iter_ibm_rows(dataset_path: Path, row_limit: int | None = None):
        with dataset_path.open(newline="", encoding="utf-8") as handle:
            reader = csv.reader(handle)
            next(reader)
            for row_index, row in enumerate(reader, start=1):
                yield {
                    "timestamp": datetime.strptime(row[0], "%Y/%m/%d %H:%M"),
                    "from_bank": row[1],
                    "from_account": row[2],
                    "to_bank": row[3],
                    "to_account": row[4],
                    "amount_received": float(row[5]),
                    "receiving_currency": row[6],
                    "amount_paid": float(row[7]),
                    "payment_currency": row[8],
                    "payment_format": row[9],
                    "is_laundering": int(row[10]),
                }
                if row_limit and row_index >= row_limit:
                    break

    def _row_to_event(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "account_id": f"{row['from_bank']}::{row['from_account']}",
            "counterparty_id": f"{row['to_bank']}::{row['to_account']}",
            "amount": row["amount_paid"],
            "payment_format": row["payment_format"],
            "timestamp": row["timestamp"],
            "from_bank": row["from_bank"],
            "to_bank": row["to_bank"],
            "payment_currency": row["payment_currency"],
            "receiving_currency": row["receiving_currency"],
        }

    def _build_training_rows(self, dataset_path: Path) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
        if not dataset_path.exists():
            raise FraudModelTrainingError(f"Research dataset not found at {dataset_path}")

        sampling = self._sampling_config()
        row_limit = sampling["row_limit"]
        start_time = time.perf_counter()
        label_profile = self._count_labels(dataset_path, row_limit=row_limit)
        count_elapsed = time.perf_counter() - start_time
        label_counts = label_profile["total"]
        rail_label_counts = label_profile["by_rail"]
        positive_rows = label_counts["1"]
        negative_rows = label_counts["0"]
        if positive_rows == 0:
            raise FraudModelTrainingError("Research dataset sample does not contain positive laundering labels.")

        negative_cap = int(sampling["negative_cap"] or 60000)
        negative_keep_probability_by_rail: dict[str, float] = {}
        for rail, counts in rail_label_counts.items():
            rail_positive_rows = counts["1"]
            rail_negative_rows = counts["0"]
            if rail_negative_rows == 0:
                negative_keep_probability_by_rail[rail] = 0.0
                continue
            if rail_positive_rows > 0:
                target_negative_sample = min(max(rail_positive_rows * 12, 400), negative_cap, rail_negative_rows)
            else:
                target_negative_sample = min(400, negative_cap, rail_negative_rows)
            negative_keep_probability_by_rail[rail] = min(
                1.0,
                target_negative_sample / max(rail_negative_rows, 1),
            )

        rng = random.Random(42)
        state = MemoryRollingState()
        feature_rows: list[list[float]] = []
        labels: list[int] = []
        timestamps: list[datetime] = []

        feature_start = time.perf_counter()
        for row in self._iter_ibm_rows(dataset_path, row_limit=row_limit):
            event = self._row_to_event(row)
            rolling = state.record(
                account_id=event["account_id"],
                counterparty_id=event["counterparty_id"],
                amount=event["amount"],
                payment_format=event["payment_format"],
                timestamp=event["timestamp"],
                from_bank=event["from_bank"],
                to_bank=event["to_bank"],
            )
            vector = self.make_vector(event, rolling)
            label = row["is_laundering"]
            rail_keep_probability = negative_keep_probability_by_rail.get(
                self._normalize_payment_format(event["payment_format"]),
                0.0,
            )
            if label == 1 or rng.random() < rail_keep_probability:
                feature_rows.append([vector[name] for name in self.feature_names])
                labels.append(label)
                timestamps.append(event["timestamp"])
        feature_elapsed = time.perf_counter() - feature_start

        if not feature_rows:
            raise FraudModelTrainingError("Training feature extraction produced no rows.")

        order = np.argsort(np.array(timestamps, dtype="datetime64[m]"))
        x = np.asarray(feature_rows, dtype=np.float32)[order]
        y = np.asarray(labels, dtype=np.int32)[order]
        split_index = int(len(y) * 0.8)
        if split_index <= 0 or split_index >= len(y):
            raise FraudModelTrainingError("Chronological split produced an invalid train/test partition.")

        metadata = {
            "artifact_version": self.artifact_version,
            "mode": self.mode,
            "source_dataset": str(dataset_path),
            "payment_rail_taxonomy": list(self.payment_formats),
            "row_limit": row_limit,
            "source_label_counts": label_counts,
            "source_label_counts_by_rail": rail_label_counts,
            "sampled_rows": int(len(y)),
            "sampled_positive_rows": int((y == 1).sum()),
            "sampled_negative_rows": int((y == 0).sum()),
            "negative_keep_probability_by_rail": {
                rail: round(probability, 6)
                for rail, probability in negative_keep_probability_by_rail.items()
            },
            "feature_names": self.feature_names,
            "split_index": split_index,
            "timings": {
                "label_count_s": round(count_elapsed, 3),
                "feature_cache_build_s": round(feature_elapsed, 3),
            },
        }
        return x, y, metadata

    def _persist_feature_cache(self, x: np.ndarray, y: np.ndarray, metadata: dict[str, Any]) -> None:
        np.savez_compressed(self.cache_path, x=x, y=y)
        self.cache_meta_path.write_text(json.dumps(metadata, indent=2))

    def _load_feature_cache(self) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
        cache = np.load(self.cache_path)
        metadata = json.loads(self.cache_meta_path.read_text())
        return cache["x"], cache["y"], metadata

    def _benchmark_shap_sizes(self, model: Any, x_train: np.ndarray) -> dict[str, dict[str, float]]:
        import shap

        timings: dict[str, dict[str, float]] = {}
        for size in (32, 64, 128):
            if len(x_train) < size:
                continue
            background = x_train[:size]
            start = time.perf_counter()
            explainer = shap.TreeExplainer(
                model,
                data=background,
                model_output="probability",
                feature_perturbation="interventional",
            )
            init_elapsed = time.perf_counter() - start
            start = time.perf_counter()
            _ = explainer(x_train[:1], check_additivity=False)
            call_elapsed = time.perf_counter() - start
            timings[str(size)] = {
                "init_s": round(init_elapsed, 4),
                "call_s": round(call_elapsed, 4),
            }
        return timings

    def _train_and_persist(self, x: np.ndarray, y: np.ndarray, metadata: dict[str, Any]) -> None:
        from sklearn.metrics import average_precision_score, roc_auc_score
        from xgboost import XGBClassifier

        split_index = int(metadata["split_index"])
        x_train, x_test = x[:split_index], x[split_index:]
        y_train, y_test = y[:split_index], y[split_index:]
        scale_pos_weight = max(float((y_train == 0).sum()) / max((y_train == 1).sum(), 1), 1.0)

        model = XGBClassifier(**self._model_params(scale_pos_weight=scale_pos_weight))
        fit_start = time.perf_counter()
        model.fit(x_train, y_train)
        fit_elapsed = time.perf_counter() - fit_start

        predict_start = time.perf_counter()
        prob_train = model.predict_proba(x_train)[:, 1]
        prob_test = model.predict_proba(x_test)[:, 1]
        predict_elapsed = time.perf_counter() - predict_start

        background_size = min(settings.shap_background_size, len(x_train))
        background = x_train[:background_size]
        shap_timings = self._benchmark_shap_sizes(model, x_train)

        metadata["metrics"] = {
            "train_auc": round(float(roc_auc_score(y_train, prob_train)), 4),
            "test_auc": round(float(roc_auc_score(y_test, prob_test)), 4),
            "train_average_precision": round(float(average_precision_score(y_train, prob_train)), 4),
            "test_average_precision": round(float(average_precision_score(y_test, prob_test)), 4),
            "train_size": int(len(y_train)),
            "test_size": int(len(y_test)),
        }
        metadata["background_size"] = int(background_size)
        metadata["shap_benchmarks"] = shap_timings
        metadata.setdefault("timings", {})
        metadata["timings"]["fit_s"] = round(fit_elapsed, 3)
        metadata["timings"]["predict_s"] = round(predict_elapsed, 3)

        joblib.dump(model, self.model_path)
        self.meta_path.write_text(json.dumps(metadata, indent=2))
        np.save(self.background_path, background)

    def make_vector(self, event: dict[str, Any], rolling: RollingFeatures) -> dict[str, float]:
        amount = float(event["amount"])
        payment_currency = event.get("payment_currency", "")
        receiving_currency = event.get("receiving_currency", "")
        normalized_format = self._normalize_payment_format(rolling.payment_format or event.get("payment_format", ""))

        vector = {
            "amount_log": round(math.log1p(max(amount, 0.0)), 6),
            "sender_velocity_1h": float(rolling.sender_velocity_1h),
            "receiver_velocity_1h": float(rolling.receiver_velocity_1h),
            "pair_velocity_24h": float(rolling.pair_velocity_24h),
            "sender_unique_counterparties_24h": float(rolling.sender_unique_counterparties_24h),
            "amount_ratio_to_sender_avg": float(rolling.amount_ratio_to_sender_avg),
            "hour_of_day": float(rolling.hour_of_day),
            "is_cross_bank": float(rolling.is_cross_bank),
            "is_self_transfer": float(rolling.is_self_transfer),
            "is_cross_currency": float(bool(payment_currency and receiving_currency and payment_currency != receiving_currency)),
        }
        for name in self.payment_formats:
            vector[f"fmt_{name}"] = 1.0 if normalized_format == name else 0.0
        return vector

    def _fallback_contributions(self, ordered: np.ndarray) -> list[dict[str, float]]:
        from xgboost import DMatrix

        booster = self.model.get_booster()
        contrib = booster.predict(DMatrix(ordered), pred_contribs=True)[0]
        rows = []
        for idx, name in enumerate(self.feature_names):
            impact = float(contrib[idx] * 100)
            rows.append(
                {
                    "feature": name,
                    "label": self.feature_labels.get(name, name),
                    "impact": round(impact, 3),
                    "value": round(float(ordered[0][idx]), 4),
                }
            )
        rows.sort(key=lambda item: abs(item["impact"]), reverse=True)
        return rows[:6]

    def explain(self, vector: dict[str, float]) -> list[dict[str, float]]:
        key = tuple(round(float(vector[name]), 6) for name in self.feature_names)
        cached = self._explanation_cache.get(key)
        if cached is not None:
            return cached

        ordered = np.array([[vector[name] for name in self.feature_names]], dtype=np.float32)
        try:
            explainer = self._ensure_explainer()
            if explainer is None:
                rows = self._fallback_contributions(ordered)
            else:
                explanation = explainer(ordered, check_additivity=False)
                shap_values = np.array(explanation.values)[0]
                rows = []
                for idx, name in enumerate(self.feature_names):
                    impact = float(shap_values[idx] * 100)
                    rows.append(
                        {
                            "feature": name,
                            "label": self.feature_labels.get(name, name),
                            "impact": round(impact, 3),
                            "value": round(float(ordered[0][idx]), 4),
                        }
                    )
                rows.sort(key=lambda item: abs(item["impact"]), reverse=True)
                rows = rows[:6]
        except Exception:
            rows = self._fallback_contributions(ordered)

        self._explanation_cache[key] = rows
        return rows

    def score(self, vector: dict[str, float]) -> tuple[float, list[dict[str, float]]]:
        ordered = np.array([[vector[name] for name in self.feature_names]], dtype=np.float32)
        probability = float(self.model.predict_proba(ordered)[0][1])
        score = round(probability * 100, 2)
        return score, self.explain(vector)

    def warmup(self) -> dict[str, Any]:
        vector = {name: 0.0 for name in self.feature_names}
        score, explanation = self.score(vector)
        return {
            "bundleId": self.bundle_id,
            "modelPath": str(self.model_path),
            "sourceDataset": self.metadata.get("source_dataset", ""),
            "score": score,
            "topFeatures": [row["feature"] for row in explanation[:3]],
            "artifactValidation": self.metadata.get("artifact_validation"),
        }
