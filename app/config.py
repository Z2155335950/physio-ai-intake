from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """Load a small, dependency-free subset of .env syntax."""
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv(PROJECT_ROOT / ".env")


def _project_path(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else (PROJECT_ROOT / path).resolve()


@dataclass(frozen=True, slots=True)
class Settings:
    project_root: Path
    llm_provider: str
    llm_api_key: str
    llm_base_url: str
    llm_model: str
    llm_connect_timeout_seconds: float
    llm_read_timeout_seconds: float
    llm_max_output_tokens: int
    llm_circuit_failure_threshold: int
    llm_circuit_cooldown_seconds: int
    llm_send_pii: bool
    knowledge_dir: Path
    knowledge_policy_file: Path
    system_prompt_file: Path
    customer_db_path: Path
    tool_audit_db_path: Path
    tool_actor_id: str
    low_session_threshold: int
    risk_lookback_days: int
    backup_dir: Path | None
    backup_auto_enabled: bool
    backup_auto_password: str
    backup_retention_days: int
    backup_restore_ttl_minutes: int
    privacy_policy_version: str
    privacy_purpose: str
    privacy_retention: str
    privacy_deletion_rule: str
    privacy_contact: str
    staff_access_password: str
    staff_admin_username: str
    portal_cookie_secure: bool
    max_history_messages: int
    knowledge_top_k: int

    @property
    def llm_configured(self) -> bool:
        if self.llm_provider == "demo":
            return True
        return bool(
            self.llm_provider in {"openai-compatible", "deepseek"}
            and self.llm_api_key
            and self.llm_base_url
            and self.llm_model
        )


def get_settings() -> Settings:
    llm_provider = os.getenv("LLM_PROVIDER", "demo").strip().lower()
    customer_db_path = _project_path(
        os.getenv("CUSTOMER_DB_PATH", "./data/customer_memory.sqlite3")
    )
    backup_dir_value = os.getenv("BACKUP_DIR", "").strip()
    backup_retention_days = max(
        1, int(os.getenv("BACKUP_RETENTION_DAYS", "30"))
    )
    default_privacy_deletion_rule = (
        "可联系下方门店隐私联系人申请查询、更正、导出或删除个人资料。"
        "身份核验后会删除顾客账号、隐私同意记录、客户档案、接诊、预约、复诊和养护说明；"
        f"系统内加密备份副本最迟在 {backup_retention_days} 天备份保留期结束后清理，"
        "另行导出的介质由门店按同一期限销毁并留痕。"
    )
    default_base_url = (
        "https://api.deepseek.com/v1"
        if llm_provider == "deepseek"
        else "https://api.openai.com/v1"
    )
    default_model = "deepseek-chat" if llm_provider == "deepseek" else ""
    return Settings(
        project_root=PROJECT_ROOT,
        llm_provider=llm_provider,
        llm_api_key=os.getenv("LLM_API_KEY", "").strip(),
        llm_base_url=os.getenv(
            "LLM_BASE_URL", default_base_url
        ).strip(),
        llm_model=os.getenv("LLM_MODEL", default_model).strip(),
        llm_connect_timeout_seconds=float(
            os.getenv("LLM_CONNECT_TIMEOUT_SECONDS", "8")
        ),
        llm_read_timeout_seconds=float(
            os.getenv("LLM_READ_TIMEOUT_SECONDS", "30")
        ),
        llm_max_output_tokens=max(
            100, int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "1800"))
        ),
        llm_circuit_failure_threshold=max(
            1, int(os.getenv("LLM_CIRCUIT_FAILURE_THRESHOLD", "3"))
        ),
        llm_circuit_cooldown_seconds=max(
            5, int(os.getenv("LLM_CIRCUIT_COOLDOWN_SECONDS", "300"))
        ),
        llm_send_pii=os.getenv("LLM_SEND_PII", "false").strip().lower()
        in {"1", "true", "yes", "on"},
        knowledge_dir=_project_path(os.getenv("KNOWLEDGE_DIR", "./data/knowledge")),
        knowledge_policy_file=_project_path(
            os.getenv("KNOWLEDGE_POLICY_FILE", "./data/knowledge_policy.json")
        ),
        system_prompt_file=_project_path(
            os.getenv("SYSTEM_PROMPT_FILE", "./data/system_prompt.md")
        ),
        customer_db_path=customer_db_path,
        tool_audit_db_path=_project_path(
            os.getenv("TOOL_AUDIT_DB_PATH", "./data/tool_audit.sqlite3")
        ),
        tool_actor_id=os.getenv("TOOL_ACTOR_ID", "local-therapist").strip(),
        low_session_threshold=max(
            0, int(os.getenv("LOW_SESSION_THRESHOLD", "2"))
        ),
        risk_lookback_days=max(1, int(os.getenv("RISK_LOOKBACK_DAYS", "30"))),
        backup_dir=(
            _project_path(backup_dir_value) if backup_dir_value else None
        ),
        backup_auto_enabled=os.getenv(
            "BACKUP_AUTO_ENABLED", "true"
        ).strip().lower()
        in {"1", "true", "yes", "on"},
        backup_auto_password=os.getenv("BACKUP_AUTO_PASSWORD", ""),
        backup_retention_days=backup_retention_days,
        backup_restore_ttl_minutes=max(
            1, int(os.getenv("BACKUP_RESTORE_TTL_MINUTES", "10"))
        ),
        privacy_policy_version=os.getenv(
            "PRIVACY_POLICY_VERSION", "2026-11-15-v1"
        ).strip(),
        privacy_purpose=os.getenv(
            "PRIVACY_PURPOSE",
            (
                "用于建立和管理客户档案，安排预约、接诊与复诊，"
                "提供顾客网页查询，并用于加密备份、安全审计和服务质量改进；"
            "不用于广告营销。启用 AI 录入且经门店授权时，"
            "仅向模型发送去除姓名、电话和地址后的必要文本。"
            ),
        ).strip(),
        privacy_retention=os.getenv(
            "PRIVACY_RETENTION",
            (
                "在服务期间及最后一次业务联系后 3 年内保存；"
                "到期后删除或匿名化。法律法规、监管或争议处理另有要求时，"
                "按要求延长保存。"
            ),
        ).strip(),
        privacy_deletion_rule=os.getenv(
            "PRIVACY_DELETION_RULE", default_privacy_deletion_rule
        ).strip(),
        privacy_contact=os.getenv("PRIVACY_CONTACT", "").strip(),
        staff_access_password=os.getenv("STAFF_ACCESS_PASSWORD", ""),
        staff_admin_username=os.getenv("STAFF_ADMIN_USERNAME", "admin").strip(),
        portal_cookie_secure=os.getenv(
            "PORTAL_COOKIE_SECURE", "false"
        ).strip().lower()
        in {"1", "true", "yes", "on"},
        max_history_messages=max(2, int(os.getenv("MAX_HISTORY_MESSAGES", "12"))),
        knowledge_top_k=max(1, int(os.getenv("KNOWLEDGE_TOP_K", "4"))),
    )

