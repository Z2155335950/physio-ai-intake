from __future__ import annotations

import io
import re
from datetime import date, datetime

from pypdf import PdfReader

from app.pdf_intake.models import PdfCustomerDraft, PdfIntakeDraft, PdfVisitDraft


MAX_PDF_BYTES = 10 * 1024 * 1024
MAX_PDF_PAGES = 30
MAX_SOURCE_TEXT = 120_000


class PdfIntakeError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def validate_pdf_upload(file_name: str, content: bytes) -> str:
    safe_name = (file_name or "intake.pdf").replace("\\", "/").split("/")[-1]
    if not safe_name.lower().endswith(".pdf"):
        raise PdfIntakeError("invalid_file_type", "请选择 PDF 文件")
    if not content:
        raise PdfIntakeError("empty_file", "PDF 文件为空")
    if len(content) > MAX_PDF_BYTES:
        raise PdfIntakeError(
            "file_too_large",
            f"PDF 不能超过 {MAX_PDF_BYTES // (1024 * 1024)} MB",
        )
    if not content.lstrip().startswith(b"%PDF-"):
        raise PdfIntakeError("invalid_pdf", "文件不是有效的 PDF")
    return safe_name


def extract_pdf_text(content: bytes) -> tuple[str, int]:
    try:
        reader = PdfReader(io.BytesIO(content), strict=False)
    except Exception as exc:
        raise PdfIntakeError("invalid_pdf", "PDF 文件无法读取") from exc
    if reader.is_encrypted:
        raise PdfIntakeError(
            "encrypted_pdf",
            "暂不支持带密码的 PDF，请先解除密码后再上传",
        )
    page_count = len(reader.pages)
    if page_count == 0:
        raise PdfIntakeError("empty_pdf", "PDF 没有可读取的页面")
    if page_count > MAX_PDF_PAGES:
        raise PdfIntakeError(
            "too_many_pages",
            f"首版最多支持 {MAX_PDF_PAGES} 页 PDF",
        )

    page_texts: list[str] = []
    for index, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        if text.strip():
            page_texts.append(f"--- 第 {index} 页 ---\n{text.strip()}")
    combined = "\n\n".join(page_texts).strip()
    if not combined:
        raise PdfIntakeError(
            "no_text_layer",
            "未读取到 PDF 文字层。当前版本不支持扫描件或纯图片 PDF",
        )
    if len(combined) > MAX_SOURCE_TEXT:
        combined = combined[:MAX_SOURCE_TEXT].rstrip() + "\n\n[后续文本已截断]"
    return combined, page_count


def parse_local_draft(text: str) -> tuple[PdfIntakeDraft, dict[str, float]]:
    compact = text.replace("\u3000", " ").replace("\r\n", "\n").replace("\r", "\n")
    visit_date, visit_confidence = _extract_date(
        compact,
        ("就诊日期", "接诊日期", "日期", "visit date"),
        allow_fallback=True,
    )
    followup_date, followup_confidence = _extract_date(
        compact,
        ("复诊日期", "下次复诊", "followup date"),
        allow_fallback=False,
    )
    phone_match = re.search(r"(?<!\d)(1[3-9]\d{9})(?!\d)", compact)
    age_match = re.search(
        r"(?:年龄\s*[:：]?\s*)?(\d{1,3})\s*岁", compact, flags=re.IGNORECASE
    )
    remaining_match = re.search(
        r"(?:剩余(?:次数|疗程)?|疗程剩余)\s*[:：]?\s*(\d{1,4})\s*次?",
        compact,
    )

    customer = PdfCustomerDraft(
        name=_field(compact, ("姓名", "客户姓名", "患者姓名", "name")),
        gender=_field(compact, ("性别", "gender")),
        age=age_match.group(1) if age_match else _field(compact, ("年龄", "age")),
        phone=phone_match.group(1) if phone_match else _field(compact, ("电话", "手机", "联系电话", "phone")),
        occupation=_field(compact, ("职业", "occupation")),
        address=_field(compact, ("住址", "地址", "address")),
        health_issues=_field(compact, ("现存问题", "健康问题", "主要问题")),
        historical_cases=_field(compact, ("历史病例", "既往病例", "病史摘要")),
        selected_course=_field(compact, ("已选疗程", "疗程", "套餐")),
        remaining_sessions=int(remaining_match.group(1)) if remaining_match else 0,
        notes=_field(compact, ("客户备注", "备注")),
    )
    visit = PdfVisitDraft(
        visit_date=visit_date,
        visit_type=_field(compact, ("就诊类型", "接诊类型", "类型")) or "初诊",
        chief_complaint=_field(compact, ("主诉", "主要诉求", "chief complaint")),
        symptom_duration=_field(compact, ("持续时长", "持续时间", "病程", "duration")),
        trigger=_field(compact, ("诱发因素", "诱因", "trigger")),
        current_history=_field(compact, ("现病史", "current history")),
        medical_history=_field(compact, ("既往史", "medical history")),
        women_special=_field(compact, ("女性专项", "妇科专项")),
        objective_findings=_field(compact, ("查体记录", "查体", "检查结果", "objective findings")),
        risk_assessment=_field(compact, ("风险评估", "风险提示", "禁忌", "risk assessment")),
        care_plan=_field(compact, ("调理方案", "建议方案", "处理方案", "care plan")),
        disclosure=_field(compact, ("告知登记", "告知", "disclosure")),
        customer_signature=_field(compact, ("顾客签字", "客户签字")),
        therapist_signature=_field(compact, ("理疗师签字", "技师签字")),
        followup_notes=_field(compact, ("复诊备注", "复诊记录", "followup notes")),
        sessions_used=0,
        followup_date=followup_date,
        followup_note=_field(compact, ("复诊安排", "复诊说明", "followup note")),
    )

    confidence: dict[str, float] = {}
    for field, value in customer.model_dump().items():
        if value not in ("", 0, None):
            confidence[f"customer.{field}"] = (
                0.98 if field == "phone" and phone_match else 0.9
            )
    for field, value in visit.model_dump().items():
        if value not in ("", 0, None, "初诊"):
            confidence[f"visit.{field}"] = 0.88
    if visit.visit_type == "初诊" and _field(
        compact, ("就诊类型", "接诊类型", "类型")
    ):
        confidence["visit.visit_type"] = 0.82
    if visit_date:
        confidence["visit.visit_date"] = visit_confidence
    if followup_date:
        confidence["visit.followup_date"] = followup_confidence
    return PdfIntakeDraft(customer=customer, visit=visit), confidence


def merge_ai_draft(
    local: PdfIntakeDraft,
    ai_payload: dict,
    ai_confidence: dict[str, float],
    local_confidence: dict[str, float] | None = None,
) -> tuple[PdfIntakeDraft, dict[str, float]]:
    raw_customer = ai_payload.get("customer")
    raw_visit = ai_payload.get("visit")
    if not isinstance(raw_customer, dict) or not isinstance(raw_visit, dict):
        raise ValueError("模型返回缺少 customer 或 visit")

    local_customer = local.customer.model_dump()
    ai_customer = {}
    for field in local_customer:
        cleaned = _clean_value(raw_customer.get(field, ""))
        ai_customer[field] = (
            int(cleaned or 0)
            if field == "remaining_sessions"
            else str(cleaned or "")
        )
    customer_values = {
        field: (
            local_customer[field]
            if local_customer[field] not in ("", 0, None)
            else ai_customer[field]
        )
        for field in local_customer
    }
    try:
        customer_values["remaining_sessions"] = int(
            customer_values.get("remaining_sessions") or 0
        )
    except (TypeError, ValueError):
        customer_values["remaining_sessions"] = 0

    local_visit = local.visit.model_dump(mode="json")
    visit_values: dict = {}
    for field in local_visit:
        value = raw_visit.get(field)
        cleaned = _clean_value(value)
        visit_values[field] = cleaned if cleaned not in ("", None) else local_visit[field]
    visit_values["visit_date"] = visit_values.get("visit_date") or local_visit["visit_date"]
    if not isinstance(visit_values.get("visit_date"), date):
        parsed_visit_date = _parse_date(str(visit_values["visit_date"]))
        visit_values["visit_date"] = parsed_visit_date or local_visit["visit_date"]
    if visit_values.get("followup_date"):
        parsed_followup_date = _parse_date(str(visit_values["followup_date"]))
        visit_values["followup_date"] = parsed_followup_date
    visit_values["sessions_used"] = 0
    try:
        customer = PdfCustomerDraft(**customer_values)
        visit = PdfVisitDraft(**visit_values)
    except Exception as exc:
        raise ValueError(f"模型字段格式不正确: {exc}") from exc
    confidence = dict(local_confidence or {})
    for field, value in customer.model_dump().items():
        if value not in ("", 0, None):
            confidence[f"customer.{field}"] = max(
                0.8, float(ai_confidence.get(f"customer.{field}", 0.8))
            )
    for field, value in visit.model_dump().items():
        if value not in ("", 0, None):
            confidence[f"visit.{field}"] = max(
                0.8, float(ai_confidence.get(f"visit.{field}", 0.8))
            )
    return PdfIntakeDraft(customer=customer, visit=visit), confidence


def _field(text: str, labels: tuple[str, ...]) -> str:
    label_pattern = "|".join(re.escape(label) for label in labels)
    match = re.search(
        rf"(?im)^\s*(?:{label_pattern})\s*[:：]\s*(.+?)\s*$",
        text,
    )
    return match.group(1).strip() if match else ""


def _extract_date(
    text: str, labels: tuple[str, ...], *, allow_fallback: bool
) -> tuple[date | None, float]:
    value = _field(text, labels)
    if not value and not allow_fallback:
        return None, 0.0
    candidates = [value] if value else []
    candidates.extend(re.findall(r"20\d{2}[-/.年]\d{1,2}[-/.月]\d{1,2}日?", text))
    for candidate in candidates:
        parsed = _parse_date(candidate)
        if parsed:
            return parsed, 0.95 if value and candidate == value else 0.78
    fallback = datetime.now().astimezone().date() if allow_fallback else None
    return fallback, 0.0


def _parse_date(value: str) -> date | None:
    normalized = re.sub(r"[年月/.]", "-", value).replace("日", "").strip()
    try:
        year, month, day = (int(part) for part in normalized.split("-")[:3])
        return date(year, month, day)
    except (TypeError, ValueError):
        return None


def _clean_value(value) -> str | int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return ""
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, (dict, list)):
        return ""
    return str(value).strip()
