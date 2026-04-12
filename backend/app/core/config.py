from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[3]
BACKEND_DIR = ROOT_DIR / "backend"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "AI 模拟面试平台"
    app_version: str = "0.1.0"
    debug: bool = True
    api_prefix: str = "/api/v1"
    secret_key: str = Field(default="dev-secret-key-change-me", min_length=16)
    access_token_expire_minutes: int = 1440
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = "123456"
    mysql_db: str = "interview"
    database_url: str | None = None

    redis_url: str = "redis://localhost:6379/0"
    milvus_uri: str = "http://localhost:19530"
    milvus_token: str = ""
    milvus_collection: str = "interview_kb_chunks"

    qwen_base_url: str = Field(
        default="https://dashscope.aliyuncs.com",
        validation_alias=AliasChoices(
            "QWEN_BASE_URL",
            "LLM_BASE_URL",
            "EMBEDDING_BASE_URL",
            "SPEECH_BASE_URL",
            "TTS_BASE_URL",
        ),
    )
    qwen_api_key: str = Field(
        default="",
        validation_alias=AliasChoices(
            "QWEN_API_KEY",
            "LLM_API_KEY",
            "EMBEDDING_API_KEY",
            "SPEECH_API_KEY",
            "TTS_API_KEY",
            "MIMO_API_KEY",
        ),
    )
    qwen_llm_model: str = Field(
        default="qwen-plus",
        validation_alias=AliasChoices("QWEN_LLM_MODEL", "LLM_MODEL"),
    )
    qwen_embedding_model: str = Field(
        default="text-embedding-v3",
        validation_alias=AliasChoices("QWEN_EMBEDDING_MODEL", "EMBEDDING_MODEL"),
    )
    qwen_embedding_dimension: int = Field(
        default=512,
        validation_alias=AliasChoices("QWEN_EMBEDDING_DIMENSION", "EMBEDDING_DIMENSION"),
    )
    qwen_asr_model: str = Field(
        default="qwen3-asr-flash",
        validation_alias=AliasChoices("QWEN_ASR_MODEL", "SPEECH_MODEL"),
    )
    qwen_tts_model: str = Field(
        default="qwen3-tts-flash",
        validation_alias=AliasChoices("QWEN_TTS_MODEL", "TTS_MODEL"),
    )
    qwen_tts_voice: str = Field(
        default="Cherry",
        validation_alias=AliasChoices("QWEN_TTS_VOICE", "TTS_VOICE"),
    )
    qwen_tts_language: str = Field(
        default="Chinese",
        validation_alias=AliasChoices("QWEN_TTS_LANGUAGE", "TTS_LANGUAGE"),
    )
    tts_format: str = "wav"

    default_question_count: int = 7
    min_question_count: int = 3
    max_question_count: int = 7
    dynamic_interview_min_questions: int = 3
    dynamic_interview_max_questions: int = 7
    dynamic_interview_early_reject_score: float = 30.0
    dynamic_interview_early_accept_score: float = 75.0
    dynamic_interview_min_questions_for_accept: int = 5
    dynamic_interview_low_value_gain_threshold: float = 0.2
    retrieval_top_k: int = 6
    interview_context_turns: int = 3
    fast_question_flow: bool = True
    llm_timeout_seconds: float = 20.0
    allow_rebuild_on_request: bool = False

    # ---- 持续语音面试模式配置 ----
    continuous_mode_enabled: bool = True
    silence_short_pause_ms: int = 800
    silence_medium_pause_ms: int = 2000
    silence_long_pause_ms: int = 5000
    silence_extended_ms: int = 8000
    silence_prompt_interval_ms: int = 8000   # 两次提醒之间最小间隔
    max_silence_reminders: int = 3           # 每道题最大提醒次数
    answer_min_speech_ms: int = 2000         # 判断结束前需要的最低语音时长
    boundary_check_debounce_ms: int = 500    # 边界检测防抖

    upload_dir_name: str = "var/uploads"
    content_source_dir_name: str = "data/content_source"
    runtime_corpus_dir_name: str = "data/runtime_corpus"
    build_artifacts_dir_name: str = "data/build_artifacts"
    log_dir_name: str = "var/logs"
    log_level: str = "INFO"
    log_retention_days: int = 14

    @field_validator("debug", mode="before")
    @classmethod
    def normalize_debug_flag(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on", "debug", "dev", "development"}:
                return True
            if normalized in {"0", "false", "no", "off", "release", "prod", "production"}:
                return False
        return value

    @field_validator("qwen_base_url", mode="before")
    @classmethod
    def normalize_qwen_base_url(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = value.strip().rstrip("/")
        if not normalized:
            return "https://dashscope.aliyuncs.com"
        for suffix in (
            "/compatible-mode/v1",
            "/api/v1/services/aigc/multimodal-generation/generation",
            "/api/v1",
        ):
            if normalized.endswith(suffix):
                return normalized[: -len(suffix)]
        return normalized

    @computed_field
    @property
    def effective_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_db}?charset=utf8mb4"
        )

    @computed_field
    @property
    def data_dir(self) -> Path:
        return ROOT_DIR / "data"

    @computed_field
    @property
    def upload_dir(self) -> Path:
        return ROOT_DIR / self.upload_dir_name

    @computed_field
    @property
    def content_source_dir(self) -> Path:
        return ROOT_DIR / self.content_source_dir_name

    @computed_field
    @property
    def runtime_corpus_dir(self) -> Path:
        return ROOT_DIR / self.runtime_corpus_dir_name

    @computed_field
    @property
    def build_artifacts_dir(self) -> Path:
        return ROOT_DIR / self.build_artifacts_dir_name

    @computed_field
    @property
    def log_dir(self) -> Path:
        return ROOT_DIR / self.log_dir_name

    @property
    def llm_api_key(self) -> str:
        return self.qwen_api_key

    @property
    def llm_base_url(self) -> str:
        return f"{self.qwen_base_url}/compatible-mode/v1"

    @property
    def llm_model(self) -> str:
        return self.qwen_llm_model

    @property
    def llm_provider(self) -> str:
        return "qwen"

    @property
    def embedding_api_key(self) -> str:
        return self.qwen_api_key

    @property
    def embedding_base_url(self) -> str:
        return f"{self.qwen_base_url}/compatible-mode/v1"

    @property
    def embedding_model(self) -> str:
        return self.qwen_embedding_model

    @property
    def embedding_dimension(self) -> int:
        return self.qwen_embedding_dimension

    @property
    def embedding_provider(self) -> str:
        return "qwen"

    @property
    def speech_api_key(self) -> str:
        return self.qwen_api_key

    @property
    def speech_base_url(self) -> str:
        return f"{self.qwen_base_url}/compatible-mode/v1"

    @property
    def speech_model(self) -> str:
        return self.qwen_asr_model

    @property
    def tts_api_key(self) -> str:
        return self.qwen_api_key

    @property
    def tts_base_url(self) -> str:
        return f"{self.qwen_base_url}/api/v1/services/aigc/multimodal-generation/generation"

    @property
    def tts_model(self) -> str:
        return self.qwen_tts_model

    @property
    def tts_voice(self) -> str:
        return self.qwen_tts_voice

    @property
    def tts_provider(self) -> str:
        return "qwen"

    @property
    def tts_language(self) -> str:
        return self.qwen_tts_language

    @property
    def llm_ready(self) -> bool:
        return bool(self.llm_api_key.strip()) and bool(self.llm_model.strip())

    @property
    def embedding_ready(self) -> bool:
        return bool(self.embedding_api_key.strip()) and bool(self.embedding_model.strip())

    @property
    def speech_ready(self) -> bool:
        return (
            bool(self.speech_api_key.strip())
            and bool(self.speech_base_url.strip())
            and bool(self.speech_model.strip())
        )

    @property
    def tts_ready(self) -> bool:
        return (
            bool(self.tts_api_key.strip())
            and bool(self.tts_base_url.strip())
            and bool(self.tts_model.strip())
            and bool(self.tts_voice.strip())
            and bool(self.tts_language.strip())
            and bool(self.tts_format.strip())
        )

    @property
    def immersive_voice_interview_ready(self) -> bool:
        return self.llm_ready and self.speech_ready and self.tts_ready


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    (settings.upload_dir / "audio").mkdir(parents=True, exist_ok=True)
    (settings.upload_dir / "resumes").mkdir(parents=True, exist_ok=True)
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    return settings
