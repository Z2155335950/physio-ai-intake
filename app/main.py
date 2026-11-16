from __future__ import annotations

import asyncio
import time
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request

from app.auth.models import (
    AuthSession,
    LoginAttempt,
    PortalAccountPasswordInput,
    PortalAccountSnapshot,
    PortalDeletionRequest,
    PortalDeletionRequestInput,
    PortalDeletionResolutionInput,
    PortalHome,
    PortalDaySchedule,
    PortalLoginInput,
    PortalPasswordChangeInput,
    PortalPasswordResetInput,
    PortalPrivacyConsent,
    PortalPrivacyPolicy,
    PortalPrivacyPolicyView,
    PortalRegisterInput,
    PortalRecoveryCode,
    PortalScheduleSlot,
    PortalVisit,
    StaffAccount,
    StaffAccountCreate,
    StaffAccountUpdate,
    StaffActionAudit,
    StaffLoginInput,
)
from app.auth.store import AuthError, PortalAuthStore
from app.backup.models import (
    BackupExportRequest,
    BackupInfo,
    BackupMaintenanceReport,
    RestoreConfirmRequest,
    RestorePreview,
    RestoreResult,
)
from app.backup.service import BackupError, BackupService
from app.config import Settings, get_settings
from app.domain import (
    HealthResponse,
    KnowledgeConflictInfo,
    KnowledgeSearchRequest,
    KnowledgeSearchResponse,
    Source,
)
from app.exports.excel import ExcelExporter
from app.agent.safety import DISCLAIMER
from app.knowledge.base import KnowledgeSearchResult
from app.knowledge.local_markdown import MarkdownKnowledgeBase
from app.llm.base import LLMProvider
from app.llm.demo import DemoProvider
from app.llm.openai_compatible import OpenAICompatibleProvider
from app.llm.resilience import CircuitBreakerLLMProvider
from app.llm.unconfigured import UnconfiguredLLMProvider
from app.memory.base import CustomerNotFoundError, VisitCompletionError
from app.memory.models import (
    AppointmentCreate,
    AppointmentRecord,
    AppointmentSlotRecord,
    AppointmentStatusUpdate,
    DaySchedule,
    CustomerCreate,
    CustomerDetail,
    CustomerHandoutUpdate,
    CustomerMessageDraft,
    CustomerProfile,
    CustomerUpdate,
    InvestigationCreate,
    InvestigationRecord,
    FollowupTask,
    FollowupStatusUpdate,
    ScheduleWindow,
    SlotAppointmentCreate,
    SlotStatusUpdate,
    TodayDashboard,
    VisitCompletionProposal,
    VisitCompletionResult,
)
from app.memory.sqlite_store import SqliteCustomerMemoryStore
from app.pdf_intake.extractor import MAX_PDF_BYTES, PdfIntakeError
from app.pdf_intake.models import (
    PdfIntakeConfirmRequest,
    PdfIntakeConfirmResult,
    PdfIntakeEditRecord,
    PdfIntakePreviewResponse,
    PdfPreferenceOverview,
    PdfPreferenceResolveRequest,
    PdfPreferenceReviewRequest,
)
from app.pdf_intake.service import PdfIntakeService
from app.pdf_intake.store import PdfIntakeStore
from app.tools.audit import SqliteToolAuditStore, ToolAuditStart
from app.tools.base import (
    ToolAuthorizationError,
    ToolBusinessRuleError,
    ToolContext,
    ToolError,
    ToolResourceNotFoundError,
)
from app.tools.factory import (
    DEFAULT_LOCAL_SCOPES,
    LOCAL_THERAPIST_SCOPES,
    build_tool_executor,
)
from app.tools.visits import ConfirmVisitInput


def create_llm(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "demo":
        return DemoProvider()
    if settings.llm_provider in {"openai-compatible", "deepseek"}:
        if not settings.llm_configured:
            return UnconfiguredLLMProvider(settings.llm_provider)
        provider = OpenAICompatibleProvider(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            provider_name=settings.llm_provider,
            connect_timeout_seconds=settings.llm_connect_timeout_seconds,
            read_timeout_seconds=settings.llm_read_timeout_seconds,
            max_output_tokens=settings.llm_max_output_tokens,
        )
        return CircuitBreakerLLMProvider(
            provider,
            failure_threshold=settings.llm_circuit_failure_threshold,
            cooldown_seconds=settings.llm_circuit_cooldown_seconds,
        )
    raise ValueError(f"不支持的 LLM_PROVIDER: {settings.llm_provider}")


def privacy_policy_from_settings(settings: Settings) -> PortalPrivacyPolicy:
    return PortalPrivacyPolicy(
        version=settings.privacy_policy_version.strip(),
        purpose=settings.privacy_purpose.strip(),
        retention=settings.privacy_retention.strip(),
        deletion_rule=settings.privacy_deletion_rule.strip(),
        contact=settings.privacy_contact.strip(),
    )


def privacy_configuration_error(
    policy: PortalPrivacyPolicy,
) -> str | None:
    labels = (
        ("version", "政策版本"),
        ("purpose", "处理用途"),
        ("retention", "保存期限"),
        ("deletion_rule", "删除规则"),
        ("contact", "隐私联系人"),
    )
    missing = [
        label for field, label in labels if not getattr(policy, field)
    ]
    if not missing:
        return None
    return f"隐私说明未完整配置：缺少{'、'.join(missing)}"


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime_settings = settings or get_settings()
    knowledge_base = MarkdownKnowledgeBase.from_directory(
        runtime_settings.knowledge_dir,
        policy_file=runtime_settings.knowledge_policy_file,
    )
    customer_memory = SqliteCustomerMemoryStore(
        runtime_settings.customer_db_path
    )
    auth_store = PortalAuthStore(runtime_settings.customer_db_path)
    auth_store.bootstrap_staff_admin(
        runtime_settings.staff_admin_username,
        runtime_settings.staff_access_password,
    )
    llm = create_llm(runtime_settings)
    pdf_intake_store = PdfIntakeStore(runtime_settings.customer_db_path)
    pdf_intake_service = PdfIntakeService(
        settings=runtime_settings,
        llm=llm,
        store=pdf_intake_store,
        knowledge_base=knowledge_base,
    )
    excel_exporter = ExcelExporter(runtime_settings.customer_db_path)
    tool_audit_store = SqliteToolAuditStore(
        runtime_settings.tool_audit_db_path
    )
    tool_executor = build_tool_executor(
        knowledge_base=knowledge_base,
        customer_memory=customer_memory,
        audit_store=tool_audit_store,
    )
    backup_service = BackupService(
        customer_db_path=runtime_settings.customer_db_path,
        audit_db_path=runtime_settings.tool_audit_db_path,
        backup_dir=(
            runtime_settings.backup_dir
            or runtime_settings.customer_db_path.parent / "backups"
        ),
        automatic_password=runtime_settings.backup_auto_password,
        retention_days=runtime_settings.backup_retention_days,
        restore_ttl_minutes=runtime_settings.backup_restore_ttl_minutes,
    )
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        stop_event = asyncio.Event()
        tasks = [
            asyncio.create_task(
                backup_service.run_maintenance_loop(enabled=stop_event)
            )
        ]
        if (
            runtime_settings.backup_auto_enabled
            and runtime_settings.backup_auto_password
        ):
            tasks.append(
                asyncio.create_task(
                    backup_service.run_daily_loop(
                        password=(
                            runtime_settings.backup_auto_password or None
                        ),
                        enabled=stop_event,
                    )
                )
            )
        yield
        stop_event.set()
        await asyncio.gather(*tasks)

    app = FastAPI(
        title="理疗养护辅助 Agent",
        version="0.1.0",
        description="面向理疗师的门店知识检索与安全辅助框架",
        lifespan=lifespan,
    )
    app.state.settings = runtime_settings
    app.state.knowledge_base = knowledge_base
    app.state.customer_memory = customer_memory
    app.state.auth_store = auth_store
    app.state.llm = llm
    app.state.pdf_intake = pdf_intake_service
    app.state.excel_exporter = excel_exporter
    app.state.tool_executor = tool_executor
    app.state.backup_service = backup_service

    web_dir = runtime_settings.project_root / "web"
    if web_dir.exists():
        app.mount("/static", StaticFiles(directory=web_dir), name="static")

    staff_cookie = "physio_staff_session"
    customer_cookie = "physio_customer_session"

    def client_ip(request: Request) -> str:
        host = request.client.host if request.client else "unknown"
        if host in {"127.0.0.1", "::1", "testclient"}:
            forwarded = request.headers.get("x-forwarded-for", "")
            if forwarded:
                return forwarded.split(",", 1)[0].strip() or host
        return host

    public_api_paths = {
        "/api/health",
        "/api/staff/login",
        "/api/staff/session",
        "/api/portal/login",
        "/api/portal/register",
        "/api/portal/logout",
    }

    @app.middleware("http")
    async def protect_staff_api(request: Request, call_next):
        path = request.url.path
        staff_scoped = (
            path.startswith("/api/")
            and not path.startswith("/api/portal/")
            and path not in public_api_paths
        )
        session: AuthSession | None = None
        if staff_scoped and auth_store.staff_login_required:
            token = request.cookies.get(staff_cookie, "")
            session = await auth_store.resolve_session(token, "staff")
            if session is None:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "需要理疗师登录"},
                )
            admin_only = (
                path.startswith("/api/staff/accounts")
                or path.startswith("/api/staff/audit")
                or path.startswith("/api/staff/login-attempts")
                or path.startswith("/api/backups")
                or path.startswith("/api/exports")
            )
            if admin_only and session.staff_role != "admin":
                return JSONResponse(
                    status_code=403,
                    content={"detail": "该操作仅允许管理员"},
                )
            request.state.staff_session = session
        if staff_scoped and not auth_store.staff_login_required:
            client_host = request.client.host if request.client else ""
            if client_host not in {"127.0.0.1", "::1", "testclient"}:
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": (
                            "尚未创建员工账号，员工接口仅允许本机访问"
                        )
                    },
                )
        response = await call_next(request)
        if staff_scoped and path not in {"/api/staff/session"}:
            account_id = session.account_id if session else None
            username = session.staff_username if session else "local-admin"
            role = session.staff_role if session else "admin"
            await auth_store.record_staff_action(
                staff_account_id=account_id,
                staff_username=username or "unknown",
                staff_role=role or "therapist",
                method=request.method,
                path=path,
                status_code=response.status_code,
            )
        return response

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        index_file = web_dir / "index.html"
        if not index_file.exists():
            raise HTTPException(status_code=404, detail="前端文件不存在")
        return FileResponse(index_file)

    @app.get("/customer", include_in_schema=False)
    @app.get("/customer/", include_in_schema=False)
    async def customer_page() -> FileResponse:
        page = web_dir / "customer.html"
        if not page.exists():
            raise HTTPException(status_code=404, detail="顾客网页不存在")
        return FileResponse(page)

    @app.get("/service-worker.js", include_in_schema=False)
    async def service_worker() -> FileResponse:
        worker_file = web_dir / "service-worker.js"
        if not worker_file.exists():
            raise HTTPException(status_code=404, detail="Service Worker 不存在")
        return FileResponse(
            worker_file,
            media_type="application/javascript",
            headers={"Service-Worker-Allowed": "/"},
        )

    @app.get("/manifest.webmanifest", include_in_schema=False)
    async def web_manifest() -> FileResponse:
        manifest_file = web_dir / "manifest.webmanifest"
        if not manifest_file.exists():
            raise HTTPException(status_code=404, detail="PWA Manifest 不存在")
        return FileResponse(
            manifest_file,
            media_type="application/manifest+json",
        )

    @app.get("/api/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        llm_status = llm.status() if hasattr(llm, "status") else {}
        return HealthResponse(
            status="ok",
            llm_provider=llm.name,
            llm_configured=runtime_settings.llm_configured,
            llm_model=runtime_settings.llm_model,
            knowledge_documents=knowledge_base.document_count,
            knowledge_chunks=knowledge_base.chunk_count,
            customer_count=await customer_memory.count_customers(),
            governed_tool_count=len(tool_executor.registry.definitions()),
            llm_circuit_open=bool(llm_status.get("circuit_open", False)),
            llm_retry_after_seconds=int(
                llm_status.get("retry_after_seconds", 0)
            ),
        )

    @app.post("/api/staff/login")
    async def staff_login(
        request: Request,
        payload: StaffLoginInput,
        response: Response,
    ) -> dict:
        try:
            token = await auth_store.login_staff(
                payload.username,
                payload.password,
                client_ip(request),
            )
        except AuthError as exc:
            raise HTTPException(
                status_code=(
                    429 if exc.retry_after_seconds else 401
                ),
                detail=str(exc),
                headers=(
                    {"Retry-After": str(exc.retry_after_seconds)}
                    if exc.retry_after_seconds
                    else None
                ),
            ) from exc
        response.set_cookie(
            staff_cookie,
            token,
            max_age=12 * 3600,
            httponly=True,
            secure=runtime_settings.portal_cookie_secure,
            samesite="lax",
        )
        session = await auth_store.resolve_session(token, "staff")
        if session:
            await auth_store.record_staff_action(
                staff_account_id=session.account_id,
                staff_username=session.staff_username or payload.username,
                staff_role=session.staff_role or "therapist",
                method="POST",
                path="/api/staff/login",
                status_code=200,
            )
        return {"ok": True}

    @app.get("/api/staff/session")
    async def staff_session(request: Request) -> dict:
        if not auth_store.staff_login_required:
            return {
                "authenticated": True,
                "auth_required": False,
                "username": "local-admin",
                "role": "admin",
            }
        session = await auth_store.resolve_session(
            request.cookies.get(staff_cookie, ""), "staff"
        )
        return {
            "authenticated": session is not None,
            "auth_required": True,
            "username": session.staff_username if session else None,
            "role": session.staff_role if session else None,
        }

    @app.post("/api/staff/logout", status_code=204)
    async def staff_logout(request: Request, response: Response) -> None:
        await auth_store.revoke_session(
            request.cookies.get(staff_cookie, "")
        )
        response.delete_cookie(staff_cookie)

    @app.get(
        "/api/staff/accounts",
        response_model=list[StaffAccount],
    )
    async def list_staff_accounts() -> list[StaffAccount]:
        return await auth_store.list_staff_accounts()

    @app.post(
        "/api/staff/accounts",
        response_model=StaffAccount,
        status_code=201,
    )
    async def create_staff_account(
        payload: StaffAccountCreate,
    ) -> StaffAccount:
        try:
            return await auth_store.create_staff_account(payload)
        except AuthError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.patch(
        "/api/staff/accounts/{account_id}",
        response_model=StaffAccount,
    )
    async def update_staff_account(
        account_id: str, payload: StaffAccountUpdate
    ) -> StaffAccount:
        try:
            return await auth_store.update_staff_account(
                account_id, payload
            )
        except AuthError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get(
        "/api/staff/audit",
        response_model=list[StaffActionAudit],
    )
    async def list_staff_actions(limit: int = 100) -> list[StaffActionAudit]:
        return await auth_store.list_staff_actions(limit)

    @app.get(
        "/api/staff/login-attempts",
        response_model=list[LoginAttempt],
    )
    async def list_login_attempts(
        limit: int = 100,
        only_failures: bool = True,
    ) -> list[LoginAttempt]:
        return await auth_store.list_login_attempts(limit, only_failures)

    async def require_customer_session(request: Request) -> AuthSession:
        session = await auth_store.resolve_session(
            request.cookies.get(customer_cookie, ""), "customer"
        )
        if session is None or not session.customer_id:
            raise HTTPException(status_code=401, detail="请先登录顾客账号")
        return session

    @app.post("/api/portal/register")
    async def portal_register(
        payload: PortalRegisterInput, response: Response
    ) -> dict:
        if not payload.privacy_consent:
            raise HTTPException(
                status_code=400,
                detail="请先阅读并同意个人信息处理说明",
            )
        privacy_policy = privacy_policy_from_settings(runtime_settings)
        configuration_error = privacy_configuration_error(privacy_policy)
        if configuration_error:
            raise HTTPException(
                status_code=503,
                detail=f"{configuration_error}，暂停新用户注册",
            )
        try:
            token = await auth_store.register(
                invite_code=payload.invite_code,
                phone_last4=payload.phone_last4,
                password=payload.password,
                privacy_policy=privacy_policy,
            )
        except AuthError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        response.set_cookie(
            customer_cookie,
            token,
            max_age=30 * 24 * 3600,
            httponly=True,
            secure=runtime_settings.portal_cookie_secure,
            samesite="lax",
        )
        return {"ok": True}

    @app.get(
        "/api/portal/privacy-policy",
        response_model=PortalPrivacyPolicyView,
    )
    async def portal_privacy_policy() -> PortalPrivacyPolicyView:
        policy = privacy_policy_from_settings(runtime_settings)
        configuration_error = privacy_configuration_error(policy)
        return PortalPrivacyPolicyView(
            **policy.model_dump(),
            registration_enabled=configuration_error is None,
            unavailable_reason=(
                None
                if configuration_error is None
                else f"{configuration_error}，暂不能注册顾客账号"
            ),
        )

    @app.get(
        "/api/portal/privacy-consent",
        response_model=PortalPrivacyConsent,
    )
    async def portal_privacy_consent(
        request: Request,
    ) -> PortalPrivacyConsent:
        session = await require_customer_session(request)
        consent = await auth_store.get_latest_privacy_consent(
            session.account_id or ""
        )
        if consent is None:
            raise HTTPException(status_code=404, detail="未找到同意记录")
        return consent

    @app.post("/api/portal/login")
    async def portal_login(
        request: Request,
        payload: PortalLoginInput,
        response: Response,
    ) -> dict:
        try:
            token = await auth_store.login_customer(
                payload.phone,
                payload.password,
                client_ip(request),
            )
        except AuthError as exc:
            raise HTTPException(
                status_code=(
                    429 if exc.retry_after_seconds else 401
                ),
                detail=str(exc),
                headers=(
                    {"Retry-After": str(exc.retry_after_seconds)}
                    if exc.retry_after_seconds
                    else None
                ),
            ) from exc
        response.set_cookie(
            customer_cookie,
            token,
            max_age=30 * 24 * 3600,
            httponly=True,
            secure=runtime_settings.portal_cookie_secure,
            samesite="lax",
        )
        return {"ok": True}

    @app.post("/api/portal/password/reset", status_code=204)
    async def portal_password_reset(
        payload: PortalPasswordResetInput,
        response: Response,
    ) -> None:
        try:
            await auth_store.reset_customer_password(
                payload.phone,
                payload.recovery_code,
                payload.new_password,
            )
        except AuthError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        response.delete_cookie(customer_cookie)

    @app.post("/api/portal/logout", status_code=204)
    async def portal_logout(request: Request, response: Response) -> None:
        await auth_store.revoke_session(
            request.cookies.get(customer_cookie, "")
        )
        response.delete_cookie(customer_cookie)

    @app.post("/api/portal/password/change", status_code=204)
    async def portal_password_change(
        request: Request,
        payload: PortalPasswordChangeInput,
        response: Response,
    ) -> None:
        session = await require_customer_session(request)
        try:
            token = await auth_store.change_customer_password(
                session.account_id or "",
                payload.current_password,
                payload.new_password,
            )
        except AuthError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        response.set_cookie(
            customer_cookie,
            token,
            max_age=30 * 24 * 3600,
            httponly=True,
            secure=runtime_settings.portal_cookie_secure,
            samesite="lax",
        )

    @app.post("/api/portal/unbind", status_code=204)
    async def portal_unbind(
        request: Request,
        payload: PortalAccountPasswordInput,
        response: Response,
    ) -> None:
        session = await require_customer_session(request)
        try:
            await auth_store.unbind_customer_account(
                session.account_id or "",
                payload.current_password,
            )
        except AuthError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        response.delete_cookie(customer_cookie)

    @app.post(
        "/api/portal/data-deletion-requests",
        response_model=PortalDeletionRequest,
        status_code=201,
    )
    async def portal_request_data_deletion(
        request: Request,
        payload: PortalDeletionRequestInput,
    ) -> PortalDeletionRequest:
        session = await require_customer_session(request)
        try:
            return await auth_store.request_customer_data_deletion(
                session.account_id or "",
                payload.current_password,
                payload.reason,
            )
        except AuthError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/portal/me", response_model=PortalHome)
    async def portal_me(request: Request) -> PortalHome:
        session = await require_customer_session(request)
        detail = await customer_memory.get_customer_detail(
            session.customer_id or ""
        )
        phone_digits = "".join(
            char for char in detail.customer.phone if char.isdigit()
        )
        phone_masked = (
            f"*******{phone_digits[-4:]}"
            if len(phone_digits) >= 4
            else "未登记"
        )
        portal_account = await auth_store.get_customer_account(
            session.customer_id or ""
        )
        return PortalHome(
            customer_name=detail.customer.name,
            phone_masked=phone_masked,
            selected_course=detail.customer.selected_course,
            remaining_sessions=detail.customer.remaining_sessions,
            portal_account_status=portal_account.status,
            latest_deletion_request_status=(
                portal_account.latest_deletion_request_status
            ),
            appointments=[
                {
                    "scheduled_at": item.scheduled_at,
                    "service_item": item.service_item,
                    "note": item.note,
                    "status": item.status,
                }
                for item in detail.appointments
                if item.status != "cancelled"
            ],
            followups=[
                {
                    "due_date": item.due_date,
                    "note": item.note,
                    "status": item.status,
                }
                for item in detail.followups
                if item.status == "pending"
            ],
            recent_visits=[
                PortalVisit(
                    visit_date=item.visit_date,
                    visit_type=item.visit_type,
                    chief_complaint=item.chief_complaint,
                    care_plan=item.care_plan,
                    sessions_used=item.sessions_used,
                )
                for item in detail.investigations[:8]
            ],
        )

    @app.get("/api/portal/handout")
    async def portal_handout(
        request: Request,
    ) -> CustomerMessageDraft:
        session = await require_customer_session(request)
        return await customer_memory.get_customer_handout(
            session.customer_id or ""
        )

    @app.get(
        "/api/portal/schedule",
        response_model=PortalDaySchedule,
    )
    async def portal_schedule(
        request: Request, schedule_date: date
    ) -> PortalDaySchedule:
        session = await require_customer_session(request)
        customer_id = session.customer_id or ""
        own_appointments = await customer_memory.list_appointments(customer_id)
        own_slot_ids = {
            appointment.slot_id
            for appointment in own_appointments
            if appointment.slot_id
        }
        schedule = await customer_memory.get_day_schedule(schedule_date)
        return PortalDaySchedule(
            schedule_date=schedule.schedule_date,
            slots=[
                PortalScheduleSlot(
                    start_at=slot.start_at,
                    end_at=slot.end_at,
                    status=slot.status,
                    is_own=slot.id in own_slot_ids,
                )
                for slot in schedule.slots
            ],
        )

    @app.post("/api/customers/{customer_id}/portal-invite")
    async def create_portal_invite(customer_id: str) -> dict:
        try:
            invite = await auth_store.create_invite(customer_id)
        except AuthError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return invite.model_dump(mode="json")

    @app.get(
        "/api/portal-admin/accounts",
        response_model=list[PortalAccountSnapshot],
    )
    async def list_portal_admin_accounts(
        q: str = "",
    ) -> list[PortalAccountSnapshot]:
        return await auth_store.list_customer_accounts(q)

    @app.post(
        "/api/customers/{customer_id}/portal-recovery-code",
        response_model=PortalRecoveryCode,
    )
    async def create_portal_recovery_code(
        customer_id: str,
    ) -> PortalRecoveryCode:
        try:
            return await auth_store.create_customer_recovery_code(customer_id)
        except AuthError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post(
        "/api/customers/{customer_id}/portal-account/revoke",
        response_model=PortalAccountSnapshot,
    )
    async def revoke_portal_account(
        customer_id: str,
    ) -> PortalAccountSnapshot:
        try:
            return await auth_store.revoke_customer_account(customer_id)
        except AuthError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post(
        "/api/customers/{customer_id}/portal-account/restore",
        response_model=PortalAccountSnapshot,
    )
    async def restore_portal_account(
        customer_id: str,
    ) -> PortalAccountSnapshot:
        try:
            return await auth_store.restore_customer_account(customer_id)
        except AuthError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get(
        "/api/portal-admin/deletion-requests",
        response_model=list[PortalDeletionRequest],
    )
    async def list_portal_deletion_requests(
        status: str = "pending",
    ) -> list[PortalDeletionRequest]:
        return await auth_store.list_customer_deletion_requests(status)

    @app.post(
        "/api/portal-admin/deletion-requests/{request_id}/resolve",
        response_model=PortalDeletionRequest,
    )
    async def resolve_portal_deletion_request(
        request_id: str,
        payload: PortalDeletionResolutionInput,
        request: Request,
    ) -> PortalDeletionRequest:
        staff_session = getattr(request.state, "staff_session", None)
        processed_by = (
            staff_session.staff_username
            if staff_session is not None
            else "local-admin"
        )
        try:
            return await auth_store.resolve_customer_deletion_request(
                request_id,
                action=payload.action,
                processed_by=processed_by,
                note=payload.note,
            )
        except AuthError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/exports/excel")
    async def export_therapist_excel() -> Response:
        call_id = str(uuid.uuid4())
        started = time.perf_counter()
        await tool_audit_store.start(
            ToolAuditStart(
                call_id=call_id,
                trace_id=call_id,
                actor_id=runtime_settings.tool_actor_id,
                customer_id=None,
                tool_name="export_therapist_excel",
                side_effect="read",
                input_summary={"scope": "all_therapist_data"},
            )
        )
        try:
            result = await excel_exporter.export()
        except Exception as exc:
            await tool_audit_store.finish(
                call_id,
                status="failed",
                duration_ms=int((time.perf_counter() - started) * 1000),
                output_summary={},
                error_code="excel_export_failed",
                error_message=str(exc),
            )
            raise HTTPException(
                status_code=500, detail="Excel 导出失败"
            ) from exc
        await tool_audit_store.finish(
            call_id,
            status="success",
            duration_ms=int((time.perf_counter() - started) * 1000),
            output_summary={
                "customer_count": result.customer_count,
                "investigation_count": result.investigation_count,
                "appointment_count": result.appointment_count,
                "followup_count": result.followup_count,
            },
        )
        return Response(
            content=result.content,
            media_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
            headers={
                "Content-Disposition": (
                    f'attachment; filename="{result.filename}"'
                )
            },
        )

    @app.get("/api/dashboard/today", response_model=TodayDashboard)
    async def today_dashboard() -> TodayDashboard:
        return await customer_memory.get_today_dashboard(
            datetime.now().astimezone().date(),
            low_session_threshold=runtime_settings.low_session_threshold,
            risk_days=runtime_settings.risk_lookback_days,
        )

    @app.get("/api/backups", response_model=list[BackupInfo])
    async def list_backups() -> list[BackupInfo]:
        return await backup_service.list_backups()

    @app.post(
        "/api/backups/maintenance",
        response_model=BackupMaintenanceReport,
    )
    async def run_backup_maintenance() -> BackupMaintenanceReport:
        return await backup_service.run_maintenance()

    @app.post("/api/backups/export")
    async def export_backup(payload: BackupExportRequest) -> Response:
        try:
            content, info = await backup_service.export_bytes(
                password=payload.password
            )
        except BackupError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return Response(
            content=content,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="{info.filename}"'
                )
            },
        )

    @app.get("/api/backups/{filename}/download")
    async def download_backup(filename: str) -> FileResponse:
        try:
            path = await backup_service.get_backup_path(filename)
        except BackupError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return FileResponse(
            path,
            media_type="application/octet-stream",
            filename=filename,
        )

    @app.post(
        "/api/backups/restore/preview",
        response_model=RestorePreview,
    )
    async def preview_restore(
        file: UploadFile = File(...),
        password: str = Form(default=""),
    ) -> RestorePreview:
        content = await file.read()
        try:
            return await backup_service.preview_restore(
                content, password or None
            )
        except BackupError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post(
        "/api/backups/restore/confirm",
        response_model=RestoreResult,
    )
    async def confirm_restore(
        payload: RestoreConfirmRequest,
    ) -> RestoreResult:
        try:
            return await backup_service.confirm_restore(payload.restore_id)
        except BackupError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post(
        "/api/knowledge/search",
        response_model=KnowledgeSearchResponse,
    )
    async def search_knowledge(
        request: KnowledgeSearchRequest,
    ) -> KnowledgeSearchResponse:
        result = await tool_executor.execute(
            "search_store_knowledge",
            {"query": request.query.strip(), "limit": request.limit},
            ToolContext(
                trace_id=str(uuid.uuid4()),
                actor_id=runtime_settings.tool_actor_id,
                scopes=DEFAULT_LOCAL_SCOPES,
            ),
        )
        if not isinstance(result.data, KnowledgeSearchResult):
            raise HTTPException(status_code=500, detail="知识检索结果异常")
        chunks = result.data.chunks
        if not chunks:
            reply = (
                "该内容不在门店知识库范围内，无法提供参考。"
                f"\n\n{DISCLAIMER}"
            )
        else:
            sections = ["以下内容直接来自本地门店知识库，未经大模型改写："]
            for index, item in enumerate(chunks[:3], start=1):
                content = item.content.strip()
                if len(content) > 700:
                    content = f"{content[:700].rstrip()}…"
                sections.append(
                    f"**来源 {index}：{item.title}**"
                    f"（{item.authority_label}，{item.authority_level} 级）\n"
                    f"{content}\n来源：`{item.source}`"
                )
            reply = "\n\n".join(sections) + f"\n\n{DISCLAIMER}"
        return KnowledgeSearchResponse(
            query=request.query,
            reply=reply,
            sources=[
                Source(
                    index=index,
                    title=item.title,
                    source=item.source,
                    excerpt=(
                        " ".join(item.content.split())[:300]
                        + ("…" if len(" ".join(item.content.split())) > 300 else "")
                    ),
                    score=item.score,
                    authority_level=item.authority_level,
                    authority_rank=item.authority_rank,
                    authority_label=item.authority_label,
                    source_type=item.source_type,
                    retrieval_score=item.retrieval_score,
                    rerank_score=item.rerank_score,
                )
                for index, item in enumerate(chunks, start=1)
            ],
            knowledge_conflicts=[
                KnowledgeConflictInfo(
                    topic=conflict.topic,
                    preferred_source=conflict.preferred_source,
                    preferred_authority=conflict.preferred_authority,
                    involved_sources=list(conflict.involved_sources),
                    resolution=conflict.resolution,
                    conditional=conflict.conditional,
                )
                for conflict in result.data.conflicts
            ],
        )

    @app.get("/api/tools")
    async def list_tools() -> list[dict]:
        return tool_executor.registry.describe()

    @app.post(
        "/api/pdf-intake/preview",
        response_model=PdfIntakePreviewResponse,
    )
    async def preview_pdf_intake(
        request: Request,
        file: UploadFile = File(...),
    ) -> PdfIntakePreviewResponse:
        content = await file.read(MAX_PDF_BYTES + 1)
        session = getattr(request.state, "staff_session", None)
        actor = (
            session.staff_username
            if session is not None
            else "local-admin"
        )
        try:
            return await pdf_intake_service.preview(
                file_name=file.filename or "intake.pdf",
                content=content,
                created_by=actor or "unknown",
            )
        except PdfIntakeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post(
        "/api/pdf-intake/confirm",
        response_model=PdfIntakeConfirmResult,
        status_code=201,
    )
    async def confirm_pdf_intake(
        request: Request,
        payload: PdfIntakeConfirmRequest,
    ) -> PdfIntakeConfirmResult:
        session = getattr(request.state, "staff_session", None)
        actor = (
            session.staff_username
            if session is not None
            else "local-admin"
        )
        try:
            return await pdf_intake_store.confirm(
                payload,
                confirmed_by=actor or "unknown",
            )
        except CustomerNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except PdfIntakeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get(
        "/api/pdf-intake/edit-history",
        response_model=list[PdfIntakeEditRecord],
    )
    async def list_pdf_edit_history(
        limit: int = 20,
    ) -> list[PdfIntakeEditRecord]:
        return await pdf_intake_store.list_recent_edits(limit)

    def pdf_actor(request: Request) -> tuple[str, str]:
        session = getattr(request.state, "staff_session", None)
        if session is None:
            return "local-admin", "admin"
        return (
            session.staff_username or "unknown",
            session.staff_role or "therapist",
        )

    @app.get(
        "/api/pdf-intake/preferences",
        response_model=PdfPreferenceOverview,
    )
    async def get_pdf_preferences(
        request: Request,
    ) -> PdfPreferenceOverview:
        actor, role = pdf_actor(request)
        return await pdf_intake_store.get_preference_overview(
            actor,
            is_admin=role == "admin",
        )

    @app.post(
        "/api/pdf-intake/preferences/candidates/{candidate_id}/resolve",
        response_model=PdfPreferenceOverview,
    )
    async def resolve_pdf_preference_candidate(
        candidate_id: str,
        request: Request,
        payload: PdfPreferenceResolveRequest,
    ) -> PdfPreferenceOverview:
        actor, role = pdf_actor(request)
        try:
            await pdf_intake_store.resolve_preference_candidate(
                candidate_id,
                therapist_id=actor,
                action=payload.action,
                actor=actor,
            )
        except PdfIntakeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return await pdf_intake_store.get_preference_overview(
            actor,
            is_admin=role == "admin",
        )

    @app.post(
        "/api/pdf-intake/preferences/{preference_id}/review",
        response_model=PdfPreferenceOverview,
    )
    async def review_pdf_clinic_preference(
        preference_id: str,
        request: Request,
        payload: PdfPreferenceReviewRequest,
    ) -> PdfPreferenceOverview:
        actor, role = pdf_actor(request)
        if role != "admin":
            raise HTTPException(
                status_code=403,
                detail="门店规则仅允许管理员审核",
            )
        try:
            await pdf_intake_store.review_clinic_preference(
                preference_id,
                action=payload.action,
                approved_by=actor,
            )
        except PdfIntakeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return await pdf_intake_store.get_preference_overview(
            actor,
            is_admin=True,
        )

    @app.get("/api/customers", response_model=list[CustomerProfile])
    async def list_customers(q: str = "") -> list[CustomerProfile]:
        return await customer_memory.list_customers(q)

    @app.post(
        "/api/customers",
        response_model=CustomerProfile,
        status_code=201,
    )
    async def create_customer(payload: CustomerCreate) -> CustomerProfile:
        return await customer_memory.create_customer(payload)

    @app.get(
        "/api/customers/{customer_id}",
        response_model=CustomerDetail,
    )
    async def get_customer(customer_id: str) -> CustomerDetail:
        try:
            return await customer_memory.get_customer_detail(customer_id)
        except CustomerNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.patch(
        "/api/customers/{customer_id}",
        response_model=CustomerProfile,
    )
    async def update_customer(
        customer_id: str, payload: CustomerUpdate
    ) -> CustomerProfile:
        try:
            return await customer_memory.update_customer(customer_id, payload)
        except CustomerNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post(
        "/api/customers/{customer_id}/visits/prepare",
        response_model=VisitCompletionProposal,
    )
    async def prepare_visit_completion(
        customer_id: str, payload: InvestigationCreate
    ) -> VisitCompletionProposal:
        try:
            result = await tool_executor.execute(
                "prepare_visit_completion",
                payload,
                ToolContext(
                    trace_id=str(uuid.uuid4()),
                    actor_id=runtime_settings.tool_actor_id,
                    scopes=LOCAL_THERAPIST_SCOPES,
                    customer_id=customer_id,
                ),
            )
            return result.data
        except CustomerNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ToolResourceNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (VisitCompletionError, ToolBusinessRuleError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ToolAuthorizationError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ToolError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.post(
        "/api/customers/{customer_id}/visits/confirm",
        response_model=VisitCompletionResult,
    )
    async def confirm_visit_completion(
        customer_id: str, payload: ConfirmVisitInput
    ) -> VisitCompletionResult:
        try:
            result = await tool_executor.execute(
                "confirm_visit_completion",
                payload,
                ToolContext(
                    trace_id=str(uuid.uuid4()),
                    actor_id=runtime_settings.tool_actor_id,
                    scopes=LOCAL_THERAPIST_SCOPES,
                    customer_id=customer_id,
                    approval_token=payload.confirmation_token,
                ),
            )
            return result.data
        except CustomerNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ToolResourceNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except (VisitCompletionError, ToolBusinessRuleError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ToolAuthorizationError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ToolError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get(
        "/api/customers/{customer_id}/investigations",
        response_model=list[InvestigationRecord],
    )
    async def list_investigations(
        customer_id: str,
    ) -> list[InvestigationRecord]:
        try:
            return await customer_memory.list_investigations(customer_id)
        except CustomerNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get(
        "/api/customers/{customer_id}/followups",
        response_model=list[FollowupTask],
    )
    async def list_followups(customer_id: str) -> list[FollowupTask]:
        try:
            return await customer_memory.list_followups(customer_id)
        except CustomerNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.patch(
        "/api/customers/{customer_id}/followups/{followup_id}/status",
        response_model=FollowupTask,
    )
    async def update_followup_status(
        customer_id: str,
        followup_id: str,
        payload: FollowupStatusUpdate,
    ) -> FollowupTask:
        try:
            return await customer_memory.update_followup_status(
                customer_id, followup_id, payload
            )
        except CustomerNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except VisitCompletionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post(
        "/api/customers/{customer_id}/appointments",
        response_model=AppointmentRecord,
        status_code=201,
    )
    async def create_appointment(
        customer_id: str, payload: AppointmentCreate
    ) -> AppointmentRecord:
        try:
            result = await tool_executor.execute(
                "schedule_customer_appointment",
                payload,
                ToolContext(
                    trace_id=str(uuid.uuid4()),
                    actor_id=runtime_settings.tool_actor_id,
                    scopes=LOCAL_THERAPIST_SCOPES,
                    customer_id=customer_id,
                ),
            )
            return result.data
        except ToolResourceNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ToolBusinessRuleError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ToolAuthorizationError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ToolError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @app.get(
        "/api/customers/{customer_id}/appointments",
        response_model=list[AppointmentRecord],
    )
    async def list_appointments(
        customer_id: str,
    ) -> list[AppointmentRecord]:
        try:
            return await customer_memory.list_appointments(customer_id)
        except CustomerNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/schedules/{schedule_date}", response_model=DaySchedule)
    async def get_day_schedule(schedule_date: date) -> DaySchedule:
        return await customer_memory.get_day_schedule(schedule_date)

    @app.post("/api/schedules/configure", response_model=DaySchedule)
    async def configure_day_schedule(window: ScheduleWindow) -> DaySchedule:
        try:
            return await customer_memory.configure_day_schedule(window)
        except VisitCompletionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.patch(
        "/api/schedules/slots/{slot_id}",
        response_model=AppointmentSlotRecord,
    )
    async def update_slot_status(
        slot_id: str, payload: SlotStatusUpdate
    ) -> AppointmentSlotRecord:
        try:
            return await customer_memory.update_slot_status(
                slot_id, payload.status
            )
        except VisitCompletionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post(
        "/api/customers/{customer_id}/appointments/from-slot",
        response_model=AppointmentRecord,
        status_code=201,
    )
    async def create_appointment_from_slot(
        customer_id: str, payload: SlotAppointmentCreate
    ) -> AppointmentRecord:
        try:
            return await customer_memory.schedule_customer_slot(
                customer_id, payload
            )
        except CustomerNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except VisitCompletionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.patch(
        "/api/customers/{customer_id}/appointments/{appointment_id}/status",
        response_model=AppointmentRecord,
    )
    async def update_appointment_status(
        customer_id: str,
        appointment_id: str,
        payload: AppointmentStatusUpdate,
    ) -> AppointmentRecord:
        try:
            return await customer_memory.update_appointment_status(
                customer_id, appointment_id, payload.status
            )
        except CustomerNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except VisitCompletionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get(
        "/api/customers/{customer_id}/customer-script",
        response_model=CustomerMessageDraft,
    )
    async def get_customer_script(
        customer_id: str,
    ) -> CustomerMessageDraft:
        try:
            return await customer_memory.get_customer_script(customer_id)
        except CustomerNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get(
        "/api/customers/{customer_id}/handout",
        response_model=CustomerMessageDraft,
    )
    async def get_customer_handout(
        customer_id: str,
    ) -> CustomerMessageDraft:
        try:
            return await customer_memory.get_customer_handout(customer_id)
        except CustomerNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.put(
        "/api/customers/{customer_id}/handout",
        response_model=CustomerMessageDraft,
    )
    async def save_customer_handout(
        customer_id: str, payload: CustomerHandoutUpdate
    ) -> CustomerMessageDraft:
        try:
            return await customer_memory.save_customer_handout(
                customer_id, payload
            )
        except CustomerNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except VisitCompletionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.delete(
        "/api/customers/{customer_id}/handout",
        response_model=CustomerMessageDraft,
    )
    async def reset_customer_handout(
        customer_id: str,
    ) -> CustomerMessageDraft:
        try:
            return await customer_memory.reset_customer_handout(customer_id)
        except CustomerNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.delete(
        "/api/customers/{customer_id}/investigations/{investigation_id}",
        status_code=204,
    )
    async def delete_investigation(
        customer_id: str, investigation_id: str
    ) -> None:
        try:
            deleted = await customer_memory.delete_investigation(
                customer_id, investigation_id
            )
        except CustomerNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        if not deleted:
            raise HTTPException(status_code=404, detail="接诊记录不存在")

    return app


app = create_app()

