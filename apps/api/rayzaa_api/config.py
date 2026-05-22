from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class Settings:
    project_name: str = "Rayzaa API"
    api_prefix: str = "/api"
    cors_origin: str = os.getenv("RAYZAA_CORS_ORIGIN", "http://localhost:3000")
    database_url: str = ""
    redis_url: str | None = None
    base_dir: Path = Path(__file__).resolve().parents[3]
    fixture_dir: Path = Path(__file__).resolve().parents[3] / "data" / "fixtures"
    dataset_dir: Path = Path(__file__).resolve().parents[3] / "data" / "processed"
    runtime_dir: Path = Path(os.getenv("RAYZAA_RUNTIME_DIR", Path(tempfile.gettempdir()) / "rayzaa"))
    artifact_dir: Path = Path(os.getenv("RAYZAA_ARTIFACT_DIR", Path(tempfile.gettempdir()) / "rayzaa" / "artifacts"))
    replay_dir: Path = Path(os.getenv("RAYZAA_REPLAY_DIR", Path(tempfile.gettempdir()) / "rayzaa" / "replay"))
    log_dir: Path = Path(os.getenv("RAYZAA_LOG_DIR", Path(tempfile.gettempdir()) / "rayzaa" / "logs"))
    benchmark_dir: Path = Path(os.getenv("RAYZAA_BENCHMARK_DIR", Path(tempfile.gettempdir()) / "rayzaa" / "benchmark"))
    temp_state_dir: Path = Path(os.getenv("RAYZAA_TMP_DIR", Path(tempfile.gettempdir()) / "rayzaa" / "tmp"))
    model_mode: str = os.getenv("RAYZAA_MODEL_MODE", "benchmark")
    shap_background_size: int = int(os.getenv("RAYZAA_SHAP_BACKGROUND_SIZE", "64"))
    benchmark_row_cap: int = int(os.getenv("RAYZAA_BENCHMARK_ROW_CAP", "1000000"))
    benchmark_negative_cap: int = int(os.getenv("RAYZAA_BENCHMARK_NEGATIVE_CAP", "15000"))
    rebuild_model_artifacts: bool = os.getenv("RAYZAA_REBUILD_MODEL_ARTIFACTS", "0") == "1"
    locked_model_bundle: str = os.getenv("RAYZAA_LOCKED_MODEL_BUNDLE", "benchmark_v3")
    allow_artifact_autotrain: bool = os.getenv("RAYZAA_ALLOW_ARTIFACT_AUTOTRAIN", "1") == "1"
    enforce_artifact_manifest: bool = os.getenv("RAYZAA_ENFORCE_ARTIFACT_MANIFEST", "0") == "1"
    approved_artifact_source: str = os.getenv("RAYZAA_APPROVED_ARTIFACT_SOURCE", "")
    artifact_manifest_path: Path = Path(
        os.getenv(
            "RAYZAA_ARTIFACT_MANIFEST",
            Path(__file__).resolve().parents[3] / "docs" / "approved_model_artifact.json",
        )
    )
    demo_flow_lock: bool = os.getenv("RAYZAA_DEMO_FLOW_LOCK", "0") == "1"
    public_app_url: str = os.getenv("RAYZAA_PUBLIC_APP_URL", "http://127.0.0.1:3000")
    public_api_url: str = os.getenv("RAYZAA_PUBLIC_API_URL", "http://127.0.0.1:8000")
    razorpay_key_id: str = os.getenv("RAZORPAY_KEY_ID", "")
    razorpay_key_secret: str = os.getenv("RAZORPAY_KEY_SECRET", "")
    razorpay_webhook_secret: str = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")
    razorpay_account_name: str = os.getenv("RAYZAA_RAZORPAY_ACCOUNT_NAME", "PayEasy Test Checkout")
    razorpay_webhook_event: str = os.getenv("RAYZAA_RAZORPAY_WEBHOOK_EVENT", "payment.captured")
    payeasy_merchant_id: str = os.getenv("RAYZAA_PAYEASY_MERCHANT_ID", "MER-PAYEASY")
    payeasy_counterparty_id: str = os.getenv("RAYZAA_PAYEASY_COUNTERPARTY_ID", "PAYEASY_SETTLEMENT")
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")
    telegram_message_thread_id: str = os.getenv("TELEGRAM_MESSAGE_THREAD_ID", "")
    telegram_min_trust_state: str = os.getenv("RAYZAA_TELEGRAM_MIN_TRUST_STATE", "Fractured")

    def __post_init__(self) -> None:
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.replay_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.benchmark_dir.mkdir(parents=True, exist_ok=True)
        self.temp_state_dir.mkdir(parents=True, exist_ok=True)
        if not self.database_url:
            default_db = self.runtime_dir / "rayzaa.db"
            self.database_url = os.getenv("DATABASE_URL", f"sqlite:///{default_db.as_posix()}")
        if self.redis_url is None:
            self.redis_url = os.getenv("REDIS_URL")

    @property
    def ibm_aml_dataset_path(self) -> Path:
        return Path(os.getenv("RAYZAA_IBM_AML_DATASET", self.dataset_dir / "ibm_aml" / "HI-Small_Trans.csv"))


settings = Settings()
