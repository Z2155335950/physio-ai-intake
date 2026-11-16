const state = {
  sessionId: localStorage.getItem("therapy_session_id") || null,
  activeCustomerId: localStorage.getItem("therapy_customer_id") || null,
  currentView: "dashboard",
  customers: [],
  customerDetail: null,
  editingCustomerId: null,
  pendingVisit: null,
  pendingRestore: null,
  pendingPdfDraft: null,
  currentInvite: null,
  currentPortalRecovery: null,
  appointmentDate: "",
  appointmentSelectedSlotId: null,
  appointmentSelectedCustomerId: null,
  appointmentSchedule: null,
  staffSession: null,
  dashboard: null,
  busy: false,
  lastSources: [],
  initialWelcomeHtml: "",
};

const elements = {
  shell: document.querySelector(".workspace"),
  form: document.querySelector("#chat-form"),
  input: document.querySelector("#message-input"),
  send: document.querySelector("#send-button"),
  messages: document.querySelector("#messages"),
  welcome: document.querySelector("#welcome-card"),
  openDashboard: document.querySelector("#open-dashboard"),
  openAppointmentManagement: document.querySelector("#open-appointment-management"),
  openBackups: document.querySelector("#open-backups"),
  openPortalAdmin: document.querySelector("#open-portal-admin"),
  openPdfIntake: document.querySelector("#open-pdf-intake"),
  openStaffManagement: document.querySelector("#open-staff-management"),
  staffLogout: document.querySelector("#staff-logout"),
  staffSessionLabel: document.querySelector("#staff-session-label"),
  dashboardOpenAppointments: document.querySelector("#dashboard-open-appointments"),
  dashboardOpenBackups: document.querySelector("#dashboard-open-backups"),
  dashboardOpenPdfIntake: document.querySelector("#dashboard-open-pdf-intake"),
  topbarDashboard: document.querySelector("#topbar-dashboard"),
  topbarAppointments: document.querySelector("#topbar-appointments"),
  dashboardView: document.querySelector("#dashboard-view"),
  appointmentManagementView: document.querySelector("#appointment-management-view"),
  chatPanel: document.querySelector("#chat-panel"),
  viewTitle: document.querySelector("#view-title"),
  viewEyebrow: document.querySelector("#view-eyebrow"),
  refreshDashboard: document.querySelector("#refresh-dashboard"),
  startConsultation: document.querySelector("#start-consultation"),
  quickCustomerSearch: document.querySelector("#quick-customer-search"),
  quickSearchResults: document.querySelector("#quick-search-results"),
  dashboardDate: document.querySelector("#dashboard-date"),
  metricAppointments: document.querySelector("#metric-appointments"),
  metricFollowups: document.querySelector("#metric-followups"),
  metricSessions: document.querySelector("#metric-sessions"),
  metricRisks: document.querySelector("#metric-risks"),
  dashboardAppointments: document.querySelector("#dashboard-appointments"),
  dashboardFollowups: document.querySelector("#dashboard-followups"),
  dashboardRisks: document.querySelector("#dashboard-risks"),
  dashboardSessions: document.querySelector("#dashboard-sessions"),
  dashboardRecent: document.querySelector("#dashboard-recent"),
  knowledgeForm: document.querySelector("#knowledge-search-form"),
  knowledgeInput: document.querySelector("#knowledge-search-input"),
  knowledgeButton: document.querySelector("#knowledge-search-button"),
  knowledgeResults: document.querySelector("#knowledge-results"),
  sourcePanel: document.querySelector("#source-panel"),
  sourceList: document.querySelector("#source-list"),
  sourceCount: document.querySelector("#source-count"),
  toggleSources: document.querySelector("#toggle-sources"),
  closeSources: document.querySelector("#close-sources"),
  statusDot: document.querySelector("#status-dot"),
  runtimeLabel: document.querySelector("#runtime-label"),
  runtimeMeta: document.querySelector("#runtime-meta"),
  openCustomers: document.querySelector("#open-customers"),
  activeCustomerName: document.querySelector("#active-customer-name"),
  customerDialog: document.querySelector("#customer-dialog"),
  closeCustomers: document.querySelector("#close-customers"),
  mobileCustomerSwitch: document.querySelector("#mobile-customer-switch"),
  customerSearch: document.querySelector("#customer-search"),
  customerList: document.querySelector("#customer-list"),
  newCustomer: document.querySelector("#new-customer"),
  customerEmpty: document.querySelector("#customer-empty"),
  profileForm: document.querySelector("#profile-form"),
  profileFormTitle: document.querySelector("#profile-form-title"),
  cancelProfile: document.querySelector("#cancel-profile"),
  customerDetail: document.querySelector("#customer-detail"),
  customerAvatar: document.querySelector("#customer-avatar"),
  customerDetailName: document.querySelector("#customer-detail-name"),
  customerDetailType: document.querySelector("#customer-detail-type"),
  customerDetailMeta: document.querySelector("#customer-detail-meta"),
  customerDetailNotes: document.querySelector("#customer-detail-notes"),
  customerDetailHealth: document.querySelector("#customer-detail-health"),
  customerDetailHistory: document.querySelector("#customer-detail-history"),
  customerDetailCourse: document.querySelector("#customer-detail-course"),
  customerDetailRemaining: document.querySelector("#customer-detail-remaining"),
  customerDetailHealthFull: document.querySelector("#customer-detail-health-full"),
  customerDetailHistoryFull: document.querySelector("#customer-detail-history-full"),
  quickRiskCard: document.querySelector("#quick-risk-card"),
  customerDetailRisk: document.querySelector("#customer-detail-risk"),
  customerLastComplaint: document.querySelector("#customer-last-complaint"),
  customerLastFeedback: document.querySelector("#customer-last-feedback"),
  quickDangerCard: document.querySelector("#quick-danger-card"),
  customerDangerSignal: document.querySelector("#customer-danger-signal"),
  editProfile: document.querySelector("#edit-profile"),
  newInvestigation: document.querySelector("#new-investigation"),
  investigationForm: document.querySelector("#investigation-form"),
  cancelInvestigation: document.querySelector("#cancel-investigation"),
  investigationList: document.querySelector("#investigation-list"),
  visitConfirmation: document.querySelector("#visit-confirmation"),
  confirmPreviousSessions: document.querySelector("#confirm-previous-sessions"),
  confirmUsedSessions: document.querySelector("#confirm-used-sessions"),
  confirmRemainingSessions: document.querySelector("#confirm-remaining-sessions"),
  confirmFollowupDate: document.querySelector("#confirm-followup-date"),
  confirmVisitType: document.querySelector("#confirm-visit-type"),
  confirmChiefComplaint: document.querySelector("#confirm-chief-complaint"),
  confirmVisit: document.querySelector("#confirm-visit"),
  cancelConfirmVisit: document.querySelector("#cancel-confirm-visit"),
  followupSection: document.querySelector("#followup-section"),
  followupList: document.querySelector("#followup-list"),
  appointmentScheduleForm: document.querySelector("#appointment-schedule-form"),
  saveAppointmentSchedule: document.querySelector("#save-appointment-schedule"),
  refreshAppointmentPage: document.querySelector("#refresh-appointment-page"),
  appointmentSelectedDate: document.querySelector("#appointment-selected-date"),
  appointmentPageSlots: document.querySelector("#appointment-page-slots"),
  appointmentBookingEmpty: document.querySelector("#appointment-booking-empty"),
  appointmentBookingPanel: document.querySelector("#appointment-booking-panel"),
  appointmentBookingTime: document.querySelector("#appointment-booking-time"),
  appointmentCustomerSearch: document.querySelector("#appointment-customer-search"),
  appointmentCustomerPicker: document.querySelector("#appointment-customer-picker"),
  appointmentServiceItem: document.querySelector("#appointment-service-item"),
  appointmentNote: document.querySelector("#appointment-note"),
  bookAppointment: document.querySelector("#book-appointment"),
  appointmentExisting: document.querySelector("#appointment-existing"),
  appointmentExistingName: document.querySelector("#appointment-existing-name"),
  appointmentExistingMeta: document.querySelector("#appointment-existing-meta"),
  appointmentExistingNote: document.querySelector("#appointment-existing-note"),
  appointmentExistingActions: document.querySelector("#appointment-existing-actions"),
  completePageAppointment: document.querySelector("#complete-page-appointment"),
  cancelPageAppointment: document.querySelector("#cancel-page-appointment"),
  appointmentDayList: document.querySelector("#appointment-day-list"),
  appointmentSection: document.querySelector("#appointment-section"),
  appointmentList: document.querySelector("#appointment-list"),
  copyCustomerScript: document.querySelector("#copy-customer-script"),
  editCustomerHandout: document.querySelector("#edit-customer-handout"),
  handoutDialog: document.querySelector("#handout-dialog"),
  handoutForm: document.querySelector("#handout-form"),
  handoutEditorState: document.querySelector("#handout-editor-state"),
  closeHandoutEditor: document.querySelector("#close-handout-editor"),
  resetHandout: document.querySelector("#reset-handout"),
  copyHandout: document.querySelector("#copy-handout"),
  createPortalInvite: document.querySelector("#create-portal-invite"),
  inviteDialog: document.querySelector("#invite-dialog"),
  closeInvite: document.querySelector("#close-invite"),
  inviteCode: document.querySelector("#invite-code"),
  inviteLink: document.querySelector("#invite-link"),
  copyInvite: document.querySelector("#copy-invite"),
  copyPortalLink: document.querySelector("#copy-portal-link"),
  toggleOptionalFields: document.querySelector("#toggle-optional-fields"),
  pdfIntakeDialog: document.querySelector("#pdf-intake-dialog"),
  closePdfIntake: document.querySelector("#close-pdf-intake"),
  pdfIntakeFile: document.querySelector("#pdf-intake-file"),
  pdfIntakeTarget: document.querySelector("#pdf-intake-target"),
  parsePdfIntake: document.querySelector("#parse-pdf-intake"),
  pdfIntakeStatus: document.querySelector("#pdf-intake-status"),
  pdfIntakePreview: document.querySelector("#pdf-intake-preview"),
  pdfIntakeMeta: document.querySelector("#pdf-intake-meta"),
  pdfIntakeWarnings: document.querySelector("#pdf-intake-warnings"),
  pdfSourceText: document.querySelector("#pdf-source-text"),
  pdfKnowledgeAssistance: document.querySelector(
    "#pdf-knowledge-assistance",
  ),
  pdfIntakeForm: document.querySelector("#pdf-intake-form"),
  pdfCustomerFieldset: document.querySelector("#pdf-customer-fieldset"),
  confirmPdfIntake: document.querySelector("#confirm-pdf-intake"),
  pdfEditHistoryList: document.querySelector("#pdf-edit-history-list"),
  refreshPdfEditHistory: document.querySelector("#refresh-pdf-edit-history"),
  pdfPreferenceCandidates: document.querySelector(
    "#pdf-preference-candidates",
  ),
  pdfPendingClinicRules: document.querySelector(
    "#pdf-pending-clinic-rules",
  ),
  pdfActivePreferences: document.querySelector("#pdf-active-preferences"),
  refreshPdfPreferences: document.querySelector("#refresh-pdf-preferences"),
  backupDialog: document.querySelector("#backup-dialog"),
  staffLoginDialog: document.querySelector("#staff-login-dialog"),
  staffLoginForm: document.querySelector("#staff-login-form"),
  staffLoginError: document.querySelector("#staff-login-error"),
  staffManagementDialog: document.querySelector("#staff-management-dialog"),
  closeStaffManagement: document.querySelector("#close-staff-management"),
  staffAccountForm: document.querySelector("#staff-account-form"),
  staffAccountList: document.querySelector("#staff-account-list"),
  staffAuditList: document.querySelector("#staff-audit-list"),
  loginAttemptList: document.querySelector("#login-attempt-list"),
  refreshStaffAccounts: document.querySelector("#refresh-staff-accounts"),
  refreshStaffAudit: document.querySelector("#refresh-staff-audit"),
  refreshLoginAttempts: document.querySelector("#refresh-login-attempts"),
  portalAdminDialog: document.querySelector("#portal-admin-dialog"),
  closePortalAdmin: document.querySelector("#close-portal-admin"),
  portalAccountSearch: document.querySelector("#portal-account-search"),
  portalAccountList: document.querySelector("#portal-account-list"),
  portalDeletionList: document.querySelector("#portal-deletion-list"),
  refreshPortalAccounts: document.querySelector("#refresh-portal-accounts"),
  refreshDeletionRequests: document.querySelector("#refresh-deletion-requests"),
  portalRecoveryResult: document.querySelector("#portal-recovery-result"),
  portalRecoveryCode: document.querySelector("#portal-recovery-code"),
  portalRecoveryExpiry: document.querySelector("#portal-recovery-expiry"),
  copyPortalRecoveryCode: document.querySelector("#copy-portal-recovery-code"),
  closeBackups: document.querySelector("#close-backups"),
  backupPassword: document.querySelector("#backup-password"),
  exportExcel: document.querySelector("#export-excel"),
  excelStatus: document.querySelector("#excel-status"),
  exportBackup: document.querySelector("#export-backup"),
  backupStatus: document.querySelector("#backup-status"),
  backupMaintenanceStatus: document.querySelector("#backup-maintenance-status"),
  runBackupMaintenance: document.querySelector("#run-backup-maintenance"),
  refreshBackups: document.querySelector("#refresh-backups"),
  backupList: document.querySelector("#backup-list"),
  restoreFile: document.querySelector("#restore-file"),
  restorePassword: document.querySelector("#restore-password"),
  previewRestore: document.querySelector("#preview-restore"),
  restorePreview: document.querySelector("#restore-preview"),
  restoreCountCustomers: document.querySelector("#restore-count-customers"),
  restoreCountVisits: document.querySelector("#restore-count-visits"),
  restoreCountAppointments: document.querySelector("#restore-count-appointments"),
  restoreCountFollowups: document.querySelector("#restore-count-followups"),
  restoreWarning: document.querySelector("#restore-warning"),
  confirmRestore: document.querySelector("#confirm-restore"),
  toast: document.querySelector("#toast"),
  offlineBanner: document.querySelector("#offline-banner"),
};

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderInline(value) {
  return escapeHtml(value)
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/`(.+?)`/g, "<code>$1</code>");
}

function renderMarkdown(value) {
  const paragraphs = String(value)
    .split(/\n{2,}/)
    .map((block) => {
      const lines = block.split("\n");
      if (lines.every((line) => /^\s*[-*]\s+/.test(line))) {
        const items = lines
          .map((line) => `<li>${renderInline(line.replace(/^\s*[-*]\s+/, ""))}</li>`)
          .join("");
        return `<ul>${items}</ul>`;
      }
      return `<p>${lines.map(renderInline).join("<br>")}</p>`;
    });
  return paragraphs.join("");
}

function showToast(message) {
  elements.toast.textContent = message;
  elements.toast.classList.add("show");
  window.clearTimeout(showToast.timeout);
  showToast.timeout = window.setTimeout(
    () => elements.toast.classList.remove("show"),
    4200,
  );
}

function showOfflineBanner(message = "") {
  elements.offlineBanner.classList.remove("is-hidden");
  const detail = elements.offlineBanner.querySelector("span");
  if (message) detail.textContent = message;
}

function updateNetworkStatus() {
  if (!navigator.onLine) {
    showOfflineBanner(
      "客户档案、接诊记录和本地知识检索仍可正常使用。",
    );
  } else {
    elements.offlineBanner.classList.add("is-hidden");
  }
}

function formatDashboardDate(value) {
  const [year, month, day] = String(value).split("-").map(Number);
  const date = new Date(year, month - 1, day);
  return date.toLocaleDateString("zh-CN", {
    year: "numeric",
    month: "long",
    day: "numeric",
    weekday: "long",
  });
}

function formatScheduledTime(value) {
  if (!value) return "";
  return new Date(value).toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function lastVisitText(customer) {
  const visit = customer.last_visit;
  if (!visit) return "暂无接诊记录";
  return `${visit.visit_date} · ${visit.chief_complaint}`;
}

function renderWorkbenchList(container, customers, mode) {
  if (!customers?.length) {
    const emptyText = {
      appointments: "今天暂无预约，可从客户档案中安排。",
      followups: "暂无到期复诊任务。",
      sessions: "暂无剩余次数不足的客户。",
      risks: "近 30 天没有新的风险标记。",
      recent: "完成一次接诊后，这里会出现摘要。",
    }[mode];
    container.innerHTML = `<div class="workbench-empty">${emptyText}</div>`;
    return;
  }

  container.innerHTML = customers
    .map((customer) => {
      const risk = customer.risk_label
        ? `<span class="workbench-risk">${escapeHtml(customer.risk_label)}</span>`
        : "";
      const time =
        mode === "appointments"
          ? `<span class="workbench-time">${escapeHtml(
              formatScheduledTime(customer.scheduled_at),
            )}</span>`
          : "";
      const details = [];
      if (mode === "appointments" && customer.appointment_service) {
        details.push(customer.appointment_service);
      }
      if (mode === "followups" && customer.followup_due_date) {
        details.push(`复诊日 ${customer.followup_due_date}`);
      }
      if (customer.selected_course) {
        details.push(customer.selected_course);
      }
      details.push(`剩余 ${customer.remaining_sessions ?? 0} 次`);
      if (customer.phone) details.push(customer.phone);

      return `
        <button class="workbench-customer" type="button"
          data-customer-id="${escapeHtml(customer.customer_id)}">
          <span class="workbench-avatar">${escapeHtml(customer.name.slice(0, 1))}</span>
          <span class="workbench-customer-copy">
            <span class="workbench-customer-top">
              <strong>${escapeHtml(customer.name)}</strong>
              ${time || risk}
            </span>
            <span class="workbench-customer-meta">
              ${details.map((item) => `<span>${escapeHtml(item)}</span>`).join("")}
            </span>
            <p class="workbench-customer-last">
              上次接诊：${escapeHtml(lastVisitText(customer))}
            </p>
          </span>
        </button>
      `;
    })
    .join("");
}

function renderDashboard(data) {
  state.dashboard = data;
  elements.dashboardDate.textContent =
    `${formatDashboardDate(data.as_of)} · 按当前客户档案实时汇总`;
  elements.metricAppointments.textContent = String(data.appointment_count);
  elements.metricFollowups.textContent = String(data.followup_count);
  elements.metricSessions.textContent = String(data.low_session_count);
  elements.metricRisks.textContent = String(data.risk_customer_count);
  renderWorkbenchList(
    elements.dashboardAppointments,
    data.today_appointments,
    "appointments",
  );
  renderWorkbenchList(
    elements.dashboardFollowups,
    data.due_followups,
    "followups",
  );
  renderWorkbenchList(
    elements.dashboardSessions,
    data.low_session_customers,
    "sessions",
  );
  renderWorkbenchList(elements.dashboardRisks, data.risk_customers, "risks");
  renderWorkbenchList(
    elements.dashboardRecent,
    data.recent_visits,
    "recent",
  );
}

async function loadDashboard() {
  try {
    const data = await apiRequest("/api/dashboard/today");
    renderDashboard(data);
  } catch (error) {
    showToast(error instanceof Error ? error.message : "读取今日工作台失败");
  }
}

async function searchIntegratedKnowledge() {
  const query = elements.knowledgeInput.value.trim();
  if (!query) {
    showToast("请输入要检索的知识关键词");
    return;
  }
  elements.knowledgeButton.disabled = true;
  elements.knowledgeButton.textContent = "检索中…";
  elements.knowledgeResults.innerHTML =
    '<div class="workbench-empty">正在检索本地门店知识…</div>';
  try {
    const response = await apiRequest("/api/knowledge/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, limit: 4 }),
    });
    const sourcesHtml = response.sources.length
      ? `
        <div class="knowledge-source-grid">
          ${response.sources
            .map(
              (source) => `
                <article class="knowledge-source-card">
                  <span class="authority-badge level-${escapeHtml(
                    (source.authority_level || "D").toLowerCase(),
                  )}">${escapeHtml(source.authority_level)} · ${escapeHtml(
                    source.authority_label,
                  )}</span>
                  <strong>${escapeHtml(source.title)}</strong>
                  <small>${escapeHtml(source.source)}</small>
                  <p>${escapeHtml(source.excerpt)}</p>
                </article>
              `,
            )
            .join("")}
        </div>
      `
      : "";
    const conflictHtml = response.knowledge_conflicts?.length
      ? `<div class="conflict-note"><strong>来源存在条件差异</strong>${response.knowledge_conflicts
          .map(
            (item) =>
              `<span>${escapeHtml(item.topic)}：优先 ${escapeHtml(
                item.preferred_source,
              )}（${escapeHtml(item.preferred_authority)} 级）</span>`,
          )
          .join("")}</div>`
      : "";
    elements.knowledgeResults.innerHTML = `
      <article class="knowledge-answer">
        <div class="answer-topline">
          <strong>本地知识检索结果</strong>
          <span class="memory-chip">${response.sources.length} 个来源</span>
        </div>
        <div class="answer-body">${renderMarkdown(response.reply)}</div>
        ${conflictHtml}
      </article>
      ${sourcesHtml}
    `;
  } catch (error) {
    elements.knowledgeResults.innerHTML = `
      <div class="workbench-empty">${escapeHtml(
        error instanceof Error ? error.message : "知识检索失败",
      )}</div>
    `;
  } finally {
    elements.knowledgeButton.disabled = false;
    elements.knowledgeButton.textContent = "检索知识";
  }
}

function showView(view) {
  state.currentView = view;
  const isDashboard = view === "dashboard";
  const isAppointments = view === "appointments";
  const isChat = view === "chat";
  elements.dashboardView.classList.toggle("is-hidden", !isDashboard);
  elements.appointmentManagementView.classList.toggle(
    "is-hidden",
    !isAppointments,
  );
  elements.chatPanel.classList.toggle("is-hidden", !isChat);
  elements.toggleSources.classList.toggle("is-hidden", !isChat);
  elements.openDashboard.classList.toggle("active", isDashboard);
  elements.openAppointmentManagement.classList.toggle(
    "active",
    isAppointments,
  );
  elements.shell.classList.remove("sources-open");
  elements.viewTitle.textContent = isDashboard
    ? "今日工作台"
    : isAppointments
      ? "预约管理"
      : "本地知识库";
  elements.viewEyebrow.textContent = isDashboard
    ? "坤元骨道 · 门店工作台"
    : isAppointments
      ? "门店预约与排班"
      : "本地知识检索";
  if (isDashboard) {
    loadDashboard();
  } else if (isAppointments) {
    openAppointmentManagement();
  } else if (isChat) {
    elements.input.focus();
  }
}

async function copyText(text) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.append(textarea);
  textarea.select();
  const copied = document.execCommand("copy");
  textarea.remove();
  if (!copied) throw new Error("浏览器不支持自动复制");
}

async function copyCustomerScript() {
  if (!state.activeCustomerId) {
    showToast("请先选择客户");
    return;
  }
  try {
    const draft = await apiRequest(
      `/api/customers/${encodeURIComponent(
        state.activeCustomerId,
      )}/customer-script`,
    );
    await copyText(draft.content);
    showToast("顾客版话术已复制，可直接粘贴到微信");
  } catch (error) {
    showToast(error instanceof Error ? error.message : "生成顾客话术失败");
  }
}

async function createPortalInvite() {
  if (!state.activeCustomerId) {
    showToast("请先选择客户");
    return;
  }
  try {
    const invite = await apiRequest(
      `/api/customers/${encodeURIComponent(
        state.activeCustomerId,
      )}/portal-invite`,
      { method: "POST" },
    );
    state.currentInvite = invite;
    elements.inviteCode.textContent = invite.invite_code;
    elements.inviteLink.textContent = `${window.location.origin}/customer/`;
    elements.inviteDialog.showModal();
  } catch (error) {
    showToast(error instanceof Error ? error.message : "生成邀请码失败");
  }
}

async function openHandoutEditor() {
  if (!state.activeCustomerId) {
    showToast("请先选择客户");
    return;
  }
  try {
    const draft = await apiRequest(
      `/api/customers/${encodeURIComponent(
        state.activeCustomerId,
      )}/handout`,
    );
    elements.handoutForm.elements.title.value = draft.title;
    elements.handoutForm.elements.content.value = draft.content;
    elements.handoutEditorState.textContent = draft.is_customized
      ? "当前为人工修改版本，保存后顾客网页会实时读取。"
      : "当前为根据最近接诊自动生成的版本。";
    elements.handoutDialog.showModal();
  } catch (error) {
    showToast(error instanceof Error ? error.message : "生成养护说明失败");
  }
}

function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

async function loadBackupList() {
  try {
    const backups = await apiRequest("/api/backups");
    if (!backups.length) {
      elements.backupList.innerHTML =
        '<div class="workbench-empty">还没有备份，可点击“一键导出”立即创建。</div>';
      return;
    }
    elements.backupList.innerHTML = backups
      .map(
        (backup) => `
          <div class="backup-item">
            <div class="backup-item-copy">
              <strong>${backup.kind === "daily" ? "每日自动备份" : "手动备份"}</strong>
              <small>${escapeHtml(
                new Date(backup.created_at).toLocaleString("zh-CN"),
              )} · ${escapeHtml(formatFileSize(backup.size_bytes))} · ${
                backup.encrypted ? "有密码保护" : "普通备份文件"
              }</small>
            </div>
            <a class="outline-button"
              href="/api/backups/${encodeURIComponent(
                backup.filename,
              )}/download">下载这份备份</a>
          </div>
        `,
      )
      .join("");
  } catch (error) {
    showToast(error instanceof Error ? error.message : "读取备份列表失败");
  }
}

async function runBackupMaintenance() {
  elements.runBackupMaintenance.disabled = true;
  elements.backupMaintenanceStatus.textContent = "正在清理过期文件…";
  try {
    const report = await apiRequest("/api/backups/maintenance", {
      method: "POST",
    });
    elements.backupMaintenanceStatus.textContent =
      `清理完成：过期备份 ${report.expired_backups_removed} 个，` +
      `临时文件 ${report.temp_files_removed} 个，` +
      `释放 ${formatFileSize(report.bytes_reclaimed)}。`;
    await loadBackupList();
  } catch (error) {
    elements.backupMaintenanceStatus.textContent =
      error instanceof Error ? error.message : "清理失败";
  } finally {
    elements.runBackupMaintenance.disabled = false;
  }
}

async function openBackupDialog() {
  if (state.staffSession?.role !== "admin") {
    showToast("只有管理员可以备份、恢复或导出完整数据");
    return;
  }
  if (!elements.backupDialog.open) {
    elements.backupDialog.showModal();
  }
  await loadBackupList();
}

async function exportBackup() {
  const password = elements.backupPassword.value;
  if (password.length < 8) {
    showToast("加密密码至少需要 8 个字符");
    return;
  }
  elements.exportBackup.disabled = true;
  elements.backupStatus.textContent = "正在整理全部资料，请稍等…";
  try {
    const response = await fetch("/api/backups/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.detail || "导出备份失败");
    }
    const blob = await response.blob();
    const disposition = response.headers.get("Content-Disposition") || "";
    const match = disposition.match(/filename="([^"]+)"/);
    const filename = match?.[1] || "physio-backup.physio-backup";
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    document.body.append(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(link.href);
    elements.backupStatus.textContent =
      "AES-GCM 加密备份已完成并开始下载。请同时妥善保管密码和文件。";
    await loadBackupList();
  } catch (error) {
    elements.backupStatus.textContent =
      error instanceof Error ? error.message : "导出备份失败";
  } finally {
    elements.exportBackup.disabled = false;
  }
}

async function exportTherapistExcel() {
  elements.exportExcel.disabled = true;
  elements.excelStatus.textContent = "正在整理业务数据表…";
  try {
    const response = await fetch("/api/exports/excel");
    if (response.status === 401) {
      showStaffLogin();
      throw new Error("请先登录理疗师账号");
    }
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.detail || "业务表导出失败");
    }
    const blob = await response.blob();
    const disposition = response.headers.get("Content-Disposition") || "";
    const match = disposition.match(/filename="([^"]+)"/);
    const filename = match?.[1] || "physio-therapist-data.xlsx";
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = filename;
    document.body.append(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(link.href);
    elements.excelStatus.textContent =
      "业务表已导出。该文件只用于查看和统计，不能恢复资料。";
  } catch (error) {
    elements.excelStatus.textContent =
      error instanceof Error ? error.message : "业务表导出失败";
  } finally {
    elements.exportExcel.disabled = false;
  }
}

async function previewRestoreBackup() {
  const file = elements.restoreFile.files?.[0];
  if (!file) {
    showToast("请先选择备份文件");
    return;
  }
  const formData = new FormData();
  formData.append("file", file);
  formData.append("password", elements.restorePassword.value);
  elements.previewRestore.disabled = true;
  try {
    const preview = await apiRequest("/api/backups/restore/preview", {
      method: "POST",
      body: formData,
    });
    state.pendingRestore = preview;
    elements.restoreCountCustomers.textContent = String(preview.customer_count);
    elements.restoreCountVisits.textContent = String(
      preview.investigation_count,
    );
    elements.restoreCountAppointments.textContent = String(
      preview.appointment_count,
    );
    elements.restoreCountFollowups.textContent = String(
      preview.followup_count,
    );
    elements.restoreWarning.textContent =
      `备份检查正常：包含 ${preview.customer_count} 位客户、` +
      `${preview.investigation_count} 条接诊、${preview.appointment_count} 条预约、` +
      `${preview.followup_count} 条复诊。恢复会换回这些资料，` +
      "确认前系统会先自动保存一份当前资料。";
    elements.restorePreview.classList.remove("is-hidden");
  } catch (error) {
    state.pendingRestore = null;
    elements.restorePreview.classList.add("is-hidden");
    showToast(error instanceof Error ? error.message : "验证备份失败");
  } finally {
    elements.previewRestore.disabled = false;
  }
}

async function confirmRestoreBackup() {
  if (!state.pendingRestore) return;
  if (
    !window.confirm(
      "确认恢复这份备份吗？当前资料会先自动备份，然后恢复到所选文件中的内容。",
    )
  ) {
    return;
  }
  elements.confirmRestore.disabled = true;
  try {
    const result = await apiRequest("/api/backups/restore/confirm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ restore_id: state.pendingRestore.restore_id }),
    });
    showToast(
      `恢复完成，共 ${result.customer_count} 位客户。当前资料也已自动保存。`,
    );
    state.pendingRestore = null;
    await new Promise((resolve) => window.setTimeout(resolve, 900));
    window.location.reload();
  } catch (error) {
    showToast(error instanceof Error ? error.message : "恢复备份失败");
  } finally {
    elements.confirmRestore.disabled = false;
  }
}

function renderQuickSearchResults(customers, digits) {
  if (!digits) {
    elements.quickSearchResults.innerHTML = "";
    return;
  }
  if (!customers.length) {
    elements.quickSearchResults.innerHTML =
      '<span class="workbench-empty">没有匹配的后四位</span>';
    return;
  }
  elements.quickSearchResults.innerHTML = customers
    .map(
      (customer) => `
        <button class="quick-search-result" type="button"
          data-customer-id="${escapeHtml(customer.id)}">
          ${escapeHtml(customer.name)} · ${escapeHtml(
            String(customer.phone || "").replace(/\D/g, "").slice(-4),
          )}
        </button>
      `,
    )
    .join("");
}

let quickSearchTimer = null;
async function searchCustomerByPhoneTail(value) {
  const digits = String(value).replace(/\D/g, "").slice(0, 4);
  elements.quickCustomerSearch.value = digits;
  window.clearTimeout(quickSearchTimer);
  if (digits.length < 4) {
    renderQuickSearchResults([], digits);
    return;
  }
  quickSearchTimer = window.setTimeout(async () => {
    try {
      const customers = await apiRequest(
        `/api/customers?q=${encodeURIComponent(digits)}`,
      );
      const matched = customers.filter((customer) =>
        String(customer.phone || "")
          .replace(/\D/g, "")
          .endsWith(digits),
      );
      renderQuickSearchResults(matched, digits);
    } catch (error) {
      showToast(error instanceof Error ? error.message : "查找客户失败");
    }
  }, 180);
}

function setBusy(isBusy) {
  state.busy = isBusy;
  elements.send.disabled = isBusy;
  elements.send.querySelector("span").textContent = isBusy ? "检索中" : "检索";
}

function hideWelcome() {
  document.querySelector("#welcome-card")?.remove();
}

function addUserMessage(text) {
  hideWelcome();
  const message = document.createElement("article");
  message.className = "message user";
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;
  message.append(bubble);
  elements.messages.append(message);
  scrollToBottom();
}

function addTyping() {
  const message = document.createElement("article");
  message.className = "message assistant";
  message.id = "typing-message";
  message.innerHTML = `
    <div class="assistant-mark">理</div>
    <div class="content"><div class="typing"><i></i><i></i><i></i></div></div>
  `;
  elements.messages.append(message);
  scrollToBottom();
}

function removeTyping() {
  document.querySelector("#typing-message")?.remove();
}

function riskLabel(response) {
  if (response.blocked) return { label: "安全拦截", className: "blocked" };
  if (response.risk?.level === "high") return { label: "高风险管理", className: "high" };
  if (response.risk?.level === "caution") {
    return { label: "谨慎评估", className: "caution" };
  }
  return { label: "", className: "none" };
}

function addAssistantMessage(response) {
  const message = document.createElement("article");
  message.className = "message assistant";
  const risk = riskLabel(response);
  const warningHtml = response.warnings?.length
    ? `<div class="warning-note">${response.warnings.map(escapeHtml).join("<br>")}</div>`
    : "";
  const conflictHtml = response.knowledge_conflicts?.length
    ? `<div class="conflict-note"><strong>知识冲突处理</strong>${response.knowledge_conflicts
        .map(
          (conflict) =>
            `<span>${escapeHtml(conflict.topic)}：优先采用 ${
              escapeHtml(conflict.preferred_source)
            }（${escapeHtml(conflict.preferred_authority)} 级）</span>`,
        )
        .join("")}</div>`
    : "";
  const memoryHtml = response.memory_used
    ? `<span class="memory-chip">客户记忆 ${response.memory_hits?.length || 0}</span>`
    : "";
  const degradedHtml = response.degraded
    ? '<span class="degraded-chip">本地备用</span>'
    : "";

  message.innerHTML = `
    <div class="assistant-mark">理</div>
    <div class="content">
      <div class="answer-card">
        <div class="answer-topline">
          <strong>本地门店知识库</strong>
          <span class="risk-chip ${risk.className}">${risk.label}</span>
          ${memoryHtml}
          ${degradedHtml}
        </div>
        <div class="answer-body">${renderMarkdown(response.reply)}</div>
        ${warningHtml}
        ${conflictHtml}
      </div>
      <div class="message-actions">
        <button class="text-action copy-action" type="button">复制回答</button>
        <button class="text-action copy-customer-action" type="button">复制顾客版</button>
        ${
          response.sources?.length
            ? '<button class="text-action view-action" type="button">查看知识来源</button>'
            : ""
        }
        ${
          response.memory_used
            ? '<button class="text-action view-memory-action" type="button">查看客户记忆</button>'
            : ""
        }
      </div>
    </div>
  `;
  elements.messages.append(message);

  message.querySelector(".copy-action").addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(response.reply);
      showToast("回答已复制");
    } catch {
      showToast("复制失败，请手动选择文本");
    }
  });
  message
    .querySelector(".copy-customer-action")
    ?.addEventListener("click", copyCustomerScript);
  message.querySelector(".view-action")?.addEventListener("click", () => {
    renderSources(response.sources);
    openSources();
  });
  message.querySelector(".view-memory-action")?.addEventListener("click", () => {
    openCustomerDialog();
  });

  state.lastSources = response.sources || [];
  if (response.degraded) {
    showOfflineBanner(
      "在线模型暂不可用，本次已使用本地知识检索摘要。网络恢复后新的模型请求会自动恢复在线调用。",
    );
  } else if (navigator.onLine) {
    elements.offlineBanner.classList.add("is-hidden");
  }
  renderSourceCount();
  scrollToBottom();
}

function addErrorMessage(text) {
  const message = document.createElement("article");
  message.className = "message assistant";
  message.innerHTML = `
    <div class="assistant-mark">理</div>
    <div class="content">
      <div class="answer-card">
        <div class="answer-topline"><strong>服务暂不可用</strong></div>
        <div class="answer-body"><p>${escapeHtml(text)}</p></div>
      </div>
    </div>
  `;
  elements.messages.append(message);
  scrollToBottom();
}

function renderSources(sources) {
  if (!sources?.length) {
    elements.sourceList.innerHTML = `
      <div class="source-empty">
        <span>⌁</span>
        <p>本次回答没有命中知识片段。</p>
      </div>
    `;
    return;
  }

  elements.sourceList.innerHTML = sources
    .map(
      (source) => `
        <article class="source-card">
          <div class="source-card-head">
            <span class="source-index">${source.index}</span>
            <strong>${escapeHtml(source.title)}</strong>
          </div>
          <div class="authority-row">
            <span class="authority-badge level-${escapeHtml(
              (source.authority_level || "D").toLowerCase(),
            )}">${escapeHtml(source.authority_level || "D")} · ${escapeHtml(
              source.authority_label || "未分级来源",
            )}</span>
            <small>重排 ${escapeHtml(source.rerank_score ?? source.score)}</small>
          </div>
          <small>${escapeHtml(source.source)}</small>
          <p>${escapeHtml(source.excerpt)}</p>
        </article>
      `,
    )
    .join("");
}

function renderSourceCount() {
  elements.sourceCount.textContent = String(state.lastSources.length || 0);
}

function openSources() {
  elements.shell.classList.add("sources-open");
}

function scrollToBottom() {
  requestAnimationFrame(() => {
    elements.messages.scrollTop = elements.messages.scrollHeight;
  });
}

async function sendMessage(text) {
  const message = String(text || "").trim();
  if (!message || state.busy) return;

  addUserMessage(message);
  elements.input.value = "";
  resizeInput();
  setBusy(true);
  addTyping();

  try {
    const response = await fetch("/api/knowledge/search", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query: message,
        limit: 4,
      }),
    });

    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.detail || `请求失败（${response.status}）`);
    }

    removeTyping();
    addAssistantMessage(payload);
  } catch (error) {
    removeTyping();
    addErrorMessage(
      error instanceof Error ? error.message : "网络连接异常，请稍后重试。",
    );
  } finally {
    setBusy(false);
    elements.input.focus();
  }
}

function resizeInput() {
  elements.input.style.height = "auto";
  elements.input.style.height = `${Math.min(elements.input.scrollHeight, 160)}px`;
}

async function loadHealth() {
  try {
    const response = await fetch("/api/health");
    if (!response.ok) throw new Error("health check failed");
    const data = await response.json();
    elements.statusDot.classList.add("online");
    const aiState =
      data.llm_provider === "demo"
        ? "本地提取"
        : data.llm_configured
          ? "AI 已配置"
          : "AI 未配置";
    elements.runtimeLabel.textContent = "本地模式运行中";
    elements.runtimeMeta.textContent =
      `${data.knowledge_documents} 份知识 · ${data.customer_count || 0} 位客户 · ${aiState}`;
  } catch {
    elements.statusDot.classList.add("error");
    elements.runtimeLabel.textContent = "服务连接失败";
    elements.runtimeMeta.textContent = "请检查后端是否启动";
  }
}

async function apiRequest(url, options = {}) {
  const response = await fetch(url, options);
  if (response.status === 401) {
    showStaffLogin();
    throw new Error("需要理疗师登录");
  }
  if (response.status === 204) return null;
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || `请求失败（${response.status}）`);
  }
  return payload;
}

function showStaffLogin() {
  if (!elements.staffLoginDialog.open) {
    elements.staffLoginDialog.showModal();
  }
}

function applyStaffSession(session) {
  state.staffSession = session;
  const role = session.role || (session.auth_required ? "therapist" : "admin");
  const username = session.username || "local-admin";
  const isAdmin = role === "admin";
  elements.staffSessionLabel.textContent = `操作人：${username} · ${
    role === "admin" ? "管理员" : "理疗师"
  }`;
  elements.openStaffManagement.classList.toggle(
    "is-hidden",
    !isAdmin,
  );
  elements.openBackups.classList.toggle("is-hidden", !isAdmin);
  elements.dashboardOpenBackups.classList.toggle("is-hidden", !isAdmin);
  elements.staffLogout.classList.toggle(
    "is-hidden",
    !session.auth_required,
  );
}

function describeStaffAction(entry) {
  const path = entry.path;
  if (path === "/api/staff/login") return "员工登录";
  if (path === "/api/staff/logout") return "员工退出登录";
  if (path === "/api/pdf-intake/preview") return "解析 PDF 录入草稿";
  if (path === "/api/pdf-intake/confirm") return "确认 PDF 草稿入库";
  if (path.startsWith("/api/staff/accounts")) {
    if (entry.method === "POST") return "新增员工账号";
    if (entry.method === "PATCH") return "修改或停用员工账号";
    return "查看员工账号";
  }
  if (path.startsWith("/api/staff/audit")) return "查看员工操作记录";
  if (path.startsWith("/api/staff/login-attempts")) return "查看失败登录记录";
  if (path.startsWith("/api/backups")) return "备份或恢复数据";
  if (path.startsWith("/api/exports")) return "导出完整 Excel";
  if (path.startsWith("/api/portal-admin/deletion-requests")) {
    return entry.method === "POST" ? "处理顾客资料删除申请" : "查看资料删除申请";
  }
  if (path.startsWith("/api/portal-admin/accounts")) return "查看顾客网页账号";
  if (path.endsWith("/portal-recovery-code")) return "生成顾客密码找回码";
  if (path.endsWith("/portal-account/revoke")) return "撤销顾客网页账号";
  if (path.endsWith("/portal-account/restore")) return "恢复顾客网页账号";
  if (path.includes("/visits/prepare")) return "准备接诊记录";
  if (path.includes("/visits/confirm")) return "确认接诊并扣减次数";
  if (path.includes("/investigations")) {
    return entry.method === "DELETE" ? "删除接诊调查记录" : "修改接诊调查记录";
  }
  if (path.includes("/followups")) return "处理复诊任务";
  if (path.includes("/appointments")) return "处理预约";
  if (path.includes("/schedules")) return "调整门店排班";
  if (path.includes("/handout")) return "修改居家养护说明";
  if (path.includes("/portal-invite")) return "生成顾客网页邀请码";
  if (path === "/api/customers" && entry.method === "POST") return "新增客户";
  if (path.startsWith("/api/customers/") && entry.method === "PATCH") {
    return "修改客户档案";
  }
  if (path.startsWith("/api/customers")) return "查看客户资料";
  if (entry.method === "GET") return "查看资料";
  if (entry.method === "POST") return "新增记录或执行操作";
  if (entry.method === "PATCH" || entry.method === "PUT") return "修改记录";
  if (entry.method === "DELETE") return "删除记录";
  return "业务操作";
}

function renderStaffAccounts(accounts) {
  elements.staffAccountList.innerHTML = accounts.length
    ? accounts
        .map(
          (account) => `
            <div class="staff-account-row">
              <div>
                <strong class="${account.role === "admin" ? "staff-role-admin" : ""}">
                  ${escapeHtml(account.username)}
                </strong>
                <small>${account.role === "admin" ? "管理员" : "普通理疗师"} · ${
                  account.status === "active" ? "启用中" : "已停用"
                } · 最近登录 ${
                  account.last_login_at
                    ? escapeHtml(
                        new Date(account.last_login_at).toLocaleString("zh-CN"),
                      )
                    : "未登录"
                }</small>
              </div>
              <button class="text-button ${
                account.status === "active" ? "danger-text" : ""
              }" type="button"
                data-staff-id="${escapeHtml(account.id)}"
                data-staff-status="${
                  account.status === "active" ? "disabled" : "active"
                }">
                ${account.status === "active" ? "停用账号" : "重新启用"}
              </button>
            </div>
          `,
        )
        .join("")
    : '<div class="workbench-empty">暂无员工账号</div>';
}

async function loadStaffAccounts() {
  try {
    const accounts = await apiRequest("/api/staff/accounts");
    renderStaffAccounts(accounts);
  } catch (error) {
    elements.staffAccountList.innerHTML = `<div class="workbench-empty">${escapeHtml(
      error.message,
    )}</div>`;
  }
}

async function loadStaffAudit() {
  try {
    const entries = await apiRequest("/api/staff/audit?limit=80");
    elements.staffAuditList.innerHTML = entries.length
      ? entries
          .map(
            (entry) => `
              <div class="staff-audit-row">
                <div>
                  <strong>${escapeHtml(entry.staff_username)} · ${escapeHtml(
                    describeStaffAction(entry),
                  )}</strong>
                  <small>${escapeHtml(entry.method)} ${escapeHtml(
                    entry.path,
                  )} · ${entry.staff_role === "admin" ? "管理员" : "理疗师"} · HTTP ${
                    entry.status_code
                  } · ${escapeHtml(
                    new Date(entry.created_at).toLocaleString("zh-CN"),
                  )}</small>
                </div>
              </div>
            `,
          )
          .join("")
      : '<div class="workbench-empty">暂无员工操作记录</div>';
  } catch (error) {
    elements.staffAuditList.innerHTML = `<div class="workbench-empty">${escapeHtml(
      error.message,
    )}</div>`;
  }
}

function loginFailureLabel(reason) {
  return {
    invalid_credentials: "账号或密码错误",
    login_account_blocked: "账号暂时锁定",
    login_ip_blocked: "IP 暂时锁定",
    login_delay: "连续失败，等待重试",
  }[reason] || "登录失败";
}

async function loadLoginAttempts() {
  try {
    const entries = await apiRequest(
      "/api/staff/login-attempts?limit=80&only_failures=true",
    );
    elements.loginAttemptList.innerHTML = entries.length
      ? entries
          .map(
            (entry) => `
              <div class="staff-audit-row">
                <div>
                  <strong>${escapeHtml(entry.account_display)} · ${escapeHtml(
                    loginFailureLabel(entry.failure_reason),
                  )}</strong>
                  <small>
                    ${entry.role === "staff" ? "员工端" : "顾客端"} ·
                    IP ${escapeHtml(entry.ip_address)} ·
                    ${
                      entry.retry_after_seconds
                        ? `等待 ${entry.retry_after_seconds} 秒 · `
                        : ""
                    }
                    ${escapeHtml(
                      new Date(entry.created_at).toLocaleString("zh-CN"),
                    )}
                  </small>
                </div>
              </div>
            `,
          )
          .join("")
      : '<div class="workbench-empty">暂无失败登录记录</div>';
  } catch (error) {
    elements.loginAttemptList.innerHTML = `<div class="workbench-empty">${escapeHtml(
      error instanceof Error ? error.message : "读取失败登录记录失败",
    )}</div>`;
  }
}

async function openStaffManagement() {
  if (!elements.staffManagementDialog.open) {
    elements.staffManagementDialog.showModal();
  }
  await Promise.all([
    loadStaffAccounts(),
    loadStaffAudit(),
    loadLoginAttempts(),
  ]);
}

function portalAccountStatusLabel(status) {
  if (status === "active") return "已绑定";
  if (status === "revoked") return "已撤销";
  if (status === "deleted") return "已注销";
  return "未绑定";
}

function renderPortalAccounts(accounts) {
  elements.portalAccountList.innerHTML = accounts.length
    ? accounts
        .map((account) => {
          const actions = [];
          if (account.status === "active") {
            actions.push(`
              <button class="text-button" type="button"
                data-portal-action="recovery"
                data-customer-id="${escapeHtml(account.customer_id)}">
                生成找回码
              </button>
              <button class="text-button danger-text" type="button"
                data-portal-action="revoke"
                data-customer-id="${escapeHtml(account.customer_id)}">
                撤销账号
              </button>
            `);
          } else if (account.status === "revoked") {
            actions.push(`
              <button class="text-button" type="button"
                data-portal-action="restore"
                data-customer-id="${escapeHtml(account.customer_id)}">
                恢复账号
              </button>
            `);
          }
          const requestLabel = account.pending_deletion_request_id
            ? " · 有待处理删除申请"
            : "";
          return `
            <div class="portal-account-admin-row">
              <div>
                <strong>
                  ${escapeHtml(account.customer_name)}
                  <span class="portal-account-status ${escapeHtml(
                    account.status,
                  )}">${portalAccountStatusLabel(account.status)}</span>
                </strong>
                <small>
                  ${account.login_phone_masked ? `${escapeHtml(
                    account.login_phone_masked,
                  )} · ` : ""}
                  最近登录：${
                    account.last_login_at
                      ? escapeHtml(
                          new Date(account.last_login_at).toLocaleString("zh-CN"),
                        )
                      : "从未登录"
                  }${requestLabel}
                </small>
              </div>
              ${
                actions.length
                  ? `<div class="portal-account-actions">${actions.join("")}</div>`
                  : ""
              }
            </div>
          `;
        })
        .join("")
    : '<div class="workbench-empty">没有匹配的顾客账号</div>';
}

async function loadPortalAccounts() {
  const query = elements.portalAccountSearch.value.trim();
  try {
    const accounts = await apiRequest(
      `/api/portal-admin/accounts?q=${encodeURIComponent(query)}`,
    );
    renderPortalAccounts(accounts);
  } catch (error) {
    elements.portalAccountList.innerHTML = `<div class="workbench-empty">${escapeHtml(
      error instanceof Error ? error.message : "读取顾客账号失败",
    )}</div>`;
  }
}

function renderDeletionRequests(requests) {
  elements.portalDeletionList.innerHTML = requests.length
    ? requests
        .map(
          (request) => `
            <div class="portal-deletion-admin-row">
              <div>
                <strong>${escapeHtml(request.customer_name)}</strong>
                <small>
                  ${escapeHtml(request.login_phone_masked || "账号已解除")} ·
                  ${escapeHtml(
                    new Date(request.requested_at).toLocaleString("zh-CN"),
                  )}
                  ${request.reason ? `<br>原因：${escapeHtml(request.reason)}` : ""}
                </small>
              </div>
              <div class="portal-account-actions">
                <button class="text-button danger-text" type="button"
                  data-deletion-action="approve"
                  data-request-id="${escapeHtml(request.id)}">
                  同意并注销资料
                </button>
                <button class="text-button" type="button"
                  data-deletion-action="reject"
                  data-request-id="${escapeHtml(request.id)}">
                  拒绝申请
                </button>
              </div>
            </div>
          `,
        )
        .join("")
    : '<div class="workbench-empty">暂无待处理资料删除申请</div>';
}

async function loadDeletionRequests() {
  try {
    const requests = await apiRequest(
      "/api/portal-admin/deletion-requests?status=pending",
    );
    renderDeletionRequests(requests);
  } catch (error) {
    elements.portalDeletionList.innerHTML = `<div class="workbench-empty">${escapeHtml(
      error instanceof Error ? error.message : "读取删除申请失败",
    )}</div>`;
  }
}

async function openPortalAdmin() {
  state.currentPortalRecovery = null;
  elements.portalRecoveryCode.textContent = "";
  elements.portalRecoveryExpiry.textContent = "";
  elements.portalRecoveryResult.classList.add("is-hidden");
  if (!elements.portalAdminDialog.open) {
    elements.portalAdminDialog.showModal();
  }
  await Promise.all([loadPortalAccounts(), loadDeletionRequests()]);
}

function renderActiveCustomer() {
  const customer = state.customers.find(
    (item) => item.id === state.activeCustomerId,
  );
  elements.activeCustomerName.textContent = customer?.name || "未绑定";
  elements.openCustomers.classList.toggle("active", Boolean(customer));
}

function renderCustomerList(query = "") {
  const normalized = query.trim().toLowerCase();
  const customers = state.customers.filter((customer) => {
    if (!normalized) return true;
    return [customer.name, customer.phone, customer.notes].some((value) =>
      String(value || "").toLowerCase().includes(normalized),
    );
  });

  const clearItem = `
    <button class="customer-list-item ${state.activeCustomerId ? "" : "active"}"
      type="button" data-customer-id="">
      <span class="customer-list-avatar">普</span>
      <span class="customer-list-copy">
        <strong>普通咨询</strong>
        <small>不绑定客户记忆</small>
      </span>
    </button>
  `;
  const customerItems = customers
    .map(
      (customer) => `
        <button class="customer-list-item ${
          customer.id === state.activeCustomerId ? "active" : ""
        }" type="button" data-customer-id="${escapeHtml(customer.id)}">
          <span class="customer-list-avatar">${escapeHtml(customer.name.slice(0, 1))}</span>
          <span class="customer-list-copy">
            <strong>${escapeHtml(customer.name)}</strong>
            <small>${escapeHtml(customer.phone || "未留电话")} · 剩余 ${
              escapeHtml(customer.remaining_sessions ?? 0)
            } 次</small>
          </span>
        </button>
      `,
    )
    .join("");
  elements.customerList.innerHTML =
    clearItem +
    (customerItems || '<div class="customer-list-empty">暂无匹配客户</div>');
}

async function loadCustomers(query = "", maintainActive = true) {
  try {
    const customers = await apiRequest(
      `/api/customers?q=${encodeURIComponent(query)}`,
    );
    state.customers = customers;
    if (
      !query &&
      maintainActive &&
      state.activeCustomerId &&
      !customers.some((customer) => customer.id === state.activeCustomerId)
    ) {
      state.activeCustomerId = null;
      localStorage.removeItem("therapy_customer_id");
    }
    renderCustomerList(query);
    renderActiveCustomer();
    if (!elements.appointmentBookingPanel.classList.contains("is-hidden")) {
      renderAppointmentCustomerPicker();
    }
  } catch (error) {
    showToast(error instanceof Error ? error.message : "读取客户档案失败");
  }
}

function renderPdfTargetOptions() {
  if (!elements.pdfIntakeTarget) return;
  const current = elements.pdfIntakeTarget.value;
  elements.pdfIntakeTarget.innerHTML = [
    '<option value="">新客户</option>',
    ...state.customers.map(
      (customer) =>
        `<option value="${escapeHtml(customer.id)}">${escapeHtml(
          customer.name,
        )}${customer.phone ? ` · ${escapeHtml(customer.phone.slice(-4))}` : ""}</option>`,
    ),
  ].join("");
  if (
    current &&
    state.customers.some((customer) => customer.id === current)
  ) {
    elements.pdfIntakeTarget.value = current;
  }
  updatePdfCustomerMode();
}

function updatePdfCustomerMode() {
  const usesExistingCustomer = Boolean(elements.pdfIntakeTarget?.value);
  if (!elements.pdfCustomerFieldset) return;
  elements.pdfCustomerFieldset.disabled = usesExistingCustomer;
  elements.pdfCustomerFieldset.querySelector("legend").textContent =
    usesExistingCustomer ? "客户资料（使用现有客户）" : "客户资料";
}

async function openPdfIntakeDialog() {
  if (!elements.pdfIntakeDialog.open) {
    elements.pdfIntakeDialog.showModal();
  }
  await loadCustomers("", true);
  renderPdfTargetOptions();
  elements.pdfIntakeTarget.value = state.activeCustomerId || "";
  updatePdfCustomerMode();
  loadPdfEditHistory();
  loadPdfPreferences();
}

function formatEditCategory(category) {
  return (
    {
      expression_style: "表达习惯",
      customer_fact: "客户事实",
      clinic_rule: "门店规则",
      medical_judgment: "医疗判断",
    }[category] || "待确认"
  );
}

async function loadPdfEditHistory() {
  if (!elements.pdfEditHistoryList) return;
  elements.pdfEditHistoryList.textContent = "正在读取修改样本…";
  try {
    const records = await apiRequest(
      "/api/pdf-intake/edit-history?limit=20",
    );
    if (!records.length) {
      elements.pdfEditHistoryList.innerHTML =
        '<p class="pdf-edit-history-empty">还没有人工修改样本。确认一份经过修改的 PDF 草稿后，这里会显示字段级差异。</p>';
      return;
    }
    elements.pdfEditHistoryList.innerHTML = records
      .map((record) => {
        const time = record.created_at
          ? new Date(record.created_at).toLocaleString("zh-CN", {
              hour12: false,
            })
          : "";
        const edits = record.edits
          .map(
            (edit) => `
              <div class="pdf-field-edit">
                <div class="pdf-field-edit-head">
                  <strong>${escapeHtml(edit.label)}</strong>
                  <span class="edit-category edit-category-${escapeHtml(
                    edit.category,
                  )}">${escapeHtml(formatEditCategory(edit.category))}</span>
                </div>
                <div class="pdf-edit-values">
                  <div><span>AI 原值</span><p>${escapeHtml(
                    edit.before || "（空）",
                  )}</p></div>
                  <div><span>最终值</span><p>${escapeHtml(
                    edit.after || "（空）",
                  )}</p></div>
                </div>
              </div>
            `,
          )
          .join("");
        return `
          <details class="pdf-edit-record">
            <summary>
              <span>${escapeHtml(record.file_name)}</span>
              <strong>${record.edits.length} 个字段有修改</strong>
              <small>${escapeHtml(record.changed_by)} · ${escapeHtml(time)}</small>
            </summary>
            <div class="pdf-edit-record-body">${edits}</div>
          </details>
        `;
      })
      .join("");
  } catch (error) {
    elements.pdfEditHistoryList.innerHTML = `<p class="pdf-edit-history-empty">${escapeHtml(
      error instanceof Error ? error.message : "读取修改样本失败",
    )}</p>`;
  }
}

function renderPreferenceExamples(examples) {
  if (!examples?.length) return "";
  return `
    <details class="pdf-preference-examples">
      <summary>查看 ${examples.length} 条修改示例</summary>
      ${examples
        .map(
          (example) => `
            <div class="pdf-preference-example">
              <span>AI 原值</span>
              <p>${escapeHtml(example.before || "（空）")}</p>
              <span>最终值</span>
              <p>${escapeHtml(example.after || "（空）")}</p>
            </div>
          `,
        )
        .join("")}
    </details>
  `;
}

function renderPreferenceOverview(overview) {
  const isAdmin = state.staffSession?.role === "admin";
  elements.pdfPreferenceCandidates.innerHTML = overview.candidates?.length
    ? overview.candidates
        .map(
          (candidate) => `
            <article class="pdf-preference-card">
              <div class="pdf-preference-card-head">
                <div>
                  <strong>${escapeHtml(candidate.field_label)}</strong>
                  <span class="edit-category edit-category-${escapeHtml(
                    candidate.category,
                  )}">${escapeHtml(formatEditCategory(candidate.category))}</span>
                </div>
                <small>同类修改 ${candidate.occurrence_count} 次</small>
              </div>
              <p>${escapeHtml(candidate.proposed_rule)}</p>
              ${renderPreferenceExamples(candidate.examples)}
              <div class="pdf-preference-actions">
                <button class="text-button" type="button"
                  data-preference-action="only_once"
                  data-candidate-id="${escapeHtml(candidate.id)}">仅本次</button>
                <button class="outline-button" type="button"
                  data-preference-action="remember_therapist"
                  data-candidate-id="${escapeHtml(candidate.id)}">记住表达格式</button>
                <button class="outline-button" type="button"
                  data-preference-action="submit_clinic_rule"
                  data-candidate-id="${escapeHtml(candidate.id)}">提交门店管理员确认</button>
              </div>
            </article>
          `,
        )
        .join("")
    : '<p class="pdf-edit-history-empty">暂无达到重复次数的表达类修改。</p>';

  elements.pdfPendingClinicRules.innerHTML = overview.pending_clinic_rules?.length
    ? overview.pending_clinic_rules
        .map(
          (preference) => `
            <article class="pdf-preference-card pending-clinic-rule">
              <div class="pdf-preference-card-head">
                <div>
                  <strong>${escapeHtml(preference.field_label)}</strong>
                  <span class="edit-category edit-category-clinic_rule">门店规则</span>
                </div>
                <small>${isAdmin ? "等待你审核" : "等待管理员审核"}</small>
              </div>
              <p>${escapeHtml(preference.rule_text)}</p>
              ${
                isAdmin
                  ? `<div class="pdf-preference-actions">
                      <button class="outline-button" type="button"
                        data-preference-review="approve"
                        data-preference-id="${escapeHtml(preference.id)}">批准并启用</button>
                      <button class="text-button danger-text" type="button"
                        data-preference-review="reject"
                        data-preference-id="${escapeHtml(preference.id)}">拒绝</button>
                    </div>`
                  : ""
              }
            </article>
          `,
        )
        .join("")
    : '<p class="pdf-edit-history-empty">没有待审核的门店规则。</p>';

  elements.pdfActivePreferences.innerHTML = overview.active_preferences?.length
    ? overview.active_preferences
        .map(
          (preference) => `
            <article class="pdf-preference-card active-preference">
              <div class="pdf-preference-card-head">
                <div>
                  <strong>${escapeHtml(preference.field_label)}</strong>
                  <span class="edit-category ${
                    preference.scope === "clinic"
                      ? "edit-category-clinic_rule"
                      : "edit-category-expression_style"
                  }">${preference.scope === "clinic" ? "门店规则" : "个人偏好"}</span>
                </div>
                <small>已生效</small>
              </div>
              <p>${escapeHtml(preference.rule_text)}</p>
            </article>
          `,
        )
        .join("")
    : '<p class="pdf-edit-history-empty">暂无已生效偏好。在线 AI 配置后，已确认偏好会注入下一次 PDF 提取。</p>';
}

async function loadPdfPreferences() {
  if (!elements.pdfPreferenceCandidates) return;
  elements.pdfPreferenceCandidates.textContent = "正在检查修改样本…";
  elements.pdfPendingClinicRules.textContent = "正在读取待审核规则…";
  elements.pdfActivePreferences.textContent = "正在读取已生效偏好…";
  try {
    const overview = await apiRequest("/api/pdf-intake/preferences");
    renderPreferenceOverview(overview);
  } catch (error) {
    const message = escapeHtml(
      error instanceof Error ? error.message : "读取偏好失败",
    );
    elements.pdfPreferenceCandidates.innerHTML = `<p class="pdf-edit-history-empty">${message}</p>`;
    elements.pdfPendingClinicRules.innerHTML = "";
    elements.pdfActivePreferences.innerHTML = "";
  }
}

async function resolvePdfPreference(candidateId, action) {
  try {
    const overview = await apiRequest(
      `/api/pdf-intake/preferences/candidates/${encodeURIComponent(
        candidateId,
      )}/resolve`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      },
    );
    renderPreferenceOverview(overview);
    showToast(
      action === "remember_therapist"
        ? "个人表达偏好已生效"
        : action === "submit_clinic_rule"
          ? "门店规则已提交管理员确认"
          : "已忽略这条偏好建议",
    );
  } catch (error) {
    showToast(error instanceof Error ? error.message : "处理偏好失败");
  }
}

async function reviewPdfClinicPreference(preferenceId, action) {
  try {
    const overview = await apiRequest(
      `/api/pdf-intake/preferences/${encodeURIComponent(
        preferenceId,
      )}/review`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      },
    );
    renderPreferenceOverview(overview);
    showToast(action === "approve" ? "门店规则已启用" : "门店规则已拒绝");
  } catch (error) {
    showToast(error instanceof Error ? error.message : "审核门店规则失败");
  }
}

function setPdfDraftField(name, value) {
  const field = elements.pdfIntakeForm?.elements?.[name];
  if (field) field.value = value ?? "";
}

function renderPdfKnowledgeAssistance(items) {
  if (!elements.pdfKnowledgeAssistance) return;
  if (!items?.length) {
    elements.pdfKnowledgeAssistance.innerHTML =
      '<p class="pdf-edit-history-empty">本次没有可展示的门店知识结果。</p>';
    return;
  }
  elements.pdfKnowledgeAssistance.innerHTML = items
    .map((item) => {
      const references = item.references?.length
        ? `
          <div class="pdf-knowledge-references">
            ${item.references
              .map(
                (reference) => `
                  <details>
                    <summary>
                      <span>来源 ${reference.index}：${escapeHtml(
                        reference.title,
                      )}</span>
                      <small>${escapeHtml(
                        reference.authority_label,
                      )} · ${escapeHtml(reference.authority_level)} 级</small>
                    </summary>
                    <p>${escapeHtml(reference.source)}</p>
                    <blockquote>${escapeHtml(reference.excerpt)}</blockquote>
                  </details>
                `,
              )
              .join("")}
          </div>
        `
        : "";
      return `
        <article class="pdf-knowledge-card ${item.found ? "" : "knowledge-missing"}">
          <div class="pdf-knowledge-card-head">
            <strong>${escapeHtml(item.label)}</strong>
            <span>${item.found ? `${item.references.length} 个来源` : "知识库未命中"}</span>
          </div>
          <div class="pdf-knowledge-text">${escapeHtml(item.text)}</div>
          ${references}
        </article>
      `;
    })
    .join("");
}

function renderPdfIntakePreview(data) {
  state.pendingPdfDraft = data;
  elements.pdfIntakePreview.classList.remove("is-hidden");
  elements.pdfIntakeMeta.innerHTML = [
    `文件：${escapeHtml(data.file_name)}`,
    `${data.page_count} 页`,
    `${Math.ceil(data.file_size / 1024)} KB`,
    data.extraction_method === "ai" ? "AI 提取" : "本地规则提取",
    `SHA-256 ${escapeHtml(data.sha256.slice(0, 12))}…`,
    ...(data.applied_preferences?.length
      ? [`已应用 ${data.applied_preferences.length} 条偏好`]
      : []),
  ]
    .map((label) => `<span>${label}</span>`)
    .join("");
  elements.pdfIntakeWarnings.innerHTML = (data.warnings || [])
    .map((warning) => `<p>${escapeHtml(warning)}</p>`)
    .join("");
  elements.pdfSourceText.textContent = data.source_text || "未返回原文预览";
  renderPdfKnowledgeAssistance(data.knowledge_assistance || []);

  const customer = data.customer || {};
  setPdfDraftField("customer_name", customer.name);
  setPdfDraftField("customer_phone", customer.phone);
  setPdfDraftField("customer_age", customer.age);
  setPdfDraftField("customer_gender", customer.gender);
  setPdfDraftField("customer_health_issues", customer.health_issues);
  setPdfDraftField("customer_historical_cases", customer.historical_cases);
  setPdfDraftField("customer_selected_course", customer.selected_course);
  setPdfDraftField(
    "customer_remaining_sessions",
    customer.remaining_sessions || 0,
  );

  const visit = data.visit || {};
  [
    "visit_date",
    "visit_type",
    "chief_complaint",
    "symptom_duration",
    "trigger",
    "current_history",
    "medical_history",
    "objective_findings",
    "risk_assessment",
    "care_plan",
    "followup_date",
    "followup_note",
    "followup_notes",
  ].forEach((field) => setPdfDraftField(field, visit[field]));
  elements.pdfIntakeForm.elements.remember_edits.checked = true;

  const confidence = data.field_confidence || {};
  elements.pdfIntakeForm.querySelectorAll(".low-confidence").forEach((label) => {
    label.classList.remove("low-confidence");
  });
  Object.entries(confidence).forEach(([path, score]) => {
    if (Number(score) >= 0.75) return;
    const [section, field] = path.split(".");
    const inputName = section === "customer" ? `customer_${field}` : field;
    const input = elements.pdfIntakeForm.elements[inputName];
    input?.closest("label")?.classList.add("low-confidence");
  });
  elements.pdfIntakeStatus.textContent =
    data.extraction_method === "ai"
      ? "AI 草稿已生成。请对照左侧原文核对标黄字段，确认后才会写入。"
      : "本地草稿已生成。请补充缺失字段，确认后才会写入。";
}

async function parsePdfIntakeFile() {
  const file = elements.pdfIntakeFile.files?.[0];
  if (!file) {
    elements.pdfIntakeStatus.textContent = "请先选择一个 PDF 文件。";
    return;
  }
  state.pendingPdfDraft = null;
  elements.pdfIntakePreview.classList.add("is-hidden");
  elements.parsePdfIntake.disabled = true;
  elements.parsePdfIntake.textContent = "正在解析…";
  elements.pdfIntakeStatus.textContent =
    "正在读取 PDF 文字并生成录入草稿，请稍候。";
  try {
    const formData = new FormData();
    formData.append("file", file);
    const data = await apiRequest("/api/pdf-intake/preview", {
      method: "POST",
      body: formData,
    });
    renderPdfIntakePreview(data);
    elements.pdfIntakePreview.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  } catch (error) {
    elements.pdfIntakePreview.classList.add("is-hidden");
    elements.pdfIntakeStatus.textContent =
      error instanceof Error ? error.message : "PDF 解析失败";
  } finally {
    elements.parsePdfIntake.disabled = false;
    elements.parsePdfIntake.textContent = "解析 PDF";
  }
}

async function submitPdfIntake(event) {
  event.preventDefault();
  if (!state.pendingPdfDraft) {
    elements.pdfIntakeStatus.textContent = "请先解析 PDF。";
    return;
  }
  const targetCustomerId = elements.pdfIntakeTarget.value;
  if (
    !targetCustomerId &&
    !elements.pdfIntakeForm.elements.customer_name.value.trim()
  ) {
    elements.pdfIntakeStatus.textContent = "新客户录入需要填写姓名。";
    elements.pdfIntakeForm.elements.customer_name.focus();
    return;
  }
  const get = (name) =>
    (elements.pdfIntakeForm.elements[name]?.value || "").trim();
  const customer = {
    name: get("customer_name"),
    gender: get("customer_gender"),
    age: get("customer_age"),
    phone: get("customer_phone"),
    occupation: "",
    address: "",
    health_issues: get("customer_health_issues"),
    historical_cases: get("customer_historical_cases"),
    selected_course: get("customer_selected_course"),
    remaining_sessions: Number(get("customer_remaining_sessions") || 0),
    notes: "",
  };
  const visit = {
    visit_date: get("visit_date"),
    visit_type: get("visit_type") || "初诊",
    chief_complaint: get("chief_complaint"),
    symptom_duration: get("symptom_duration"),
    trigger: get("trigger"),
    current_history: get("current_history"),
    medical_history: get("medical_history"),
    women_special: "",
    objective_findings: get("objective_findings"),
    risk_assessment: get("risk_assessment"),
    care_plan: get("care_plan"),
    disclosure: "",
    customer_signature: "",
    therapist_signature: "",
    followup_notes: get("followup_notes"),
    sessions_used: 0,
    followup_date: get("followup_date") || null,
    followup_note: get("followup_note"),
  };
  const payload = {
    draft_id: state.pendingPdfDraft.draft_id,
    customer_id: targetCustomerId || null,
    customer: targetCustomerId ? null : customer,
    visit,
    remember_edits: elements.pdfIntakeForm.elements.remember_edits.checked,
  };
  elements.confirmPdfIntake.disabled = true;
  elements.confirmPdfIntake.textContent = "正在写入…";
  try {
    const result = await apiRequest("/api/pdf-intake/confirm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    state.activeCustomerId = result.customer_id;
    localStorage.setItem("therapy_customer_id", result.customer_id);
    state.pendingPdfDraft = null;
    elements.pdfIntakeDialog.close();
    showToast(
      result.created_customer
        ? `客户和接诊记录已从 PDF 录入${
            result.edit_record_id ? "，修改样本已保存" : ""
          }`
        : `接诊记录已从 PDF 录入现有客户${
            result.edit_record_id ? "，修改样本已保存" : ""
          }`,
    );
    await loadCustomers("", true);
    await loadCustomerDetail(result.customer_id);
    await loadDashboard();
  } catch (error) {
    elements.pdfIntakeStatus.textContent =
      error instanceof Error ? error.message : "PDF 录入失败";
  } finally {
    elements.confirmPdfIntake.disabled = false;
    elements.confirmPdfIntake.textContent = "我核对完成，确认写入";
  }
}

function showCustomerEmpty() {
  elements.customerDialog.classList.remove(
    "mobile-customer-selected",
    "mobile-customer-editing",
  );
  elements.customerEmpty.classList.remove("is-hidden");
  elements.profileForm.classList.add("is-hidden");
  elements.customerDetail.classList.add("is-hidden");
  elements.followupSection.classList.add("is-hidden");
  elements.appointmentSection.classList.add("is-hidden");
  elements.visitConfirmation.classList.add("is-hidden");
}

function showProfileForm(customer = null) {
  elements.customerDialog.classList.remove("mobile-customer-selected");
  elements.customerDialog.classList.add("mobile-customer-editing");
  state.editingCustomerId = customer?.id || null;
  elements.profileForm.reset();
  elements.profileFormTitle.textContent = customer ? "编辑客户资料" : "新建客户";
  if (customer) {
    [
      "name",
      "gender",
      "age",
      "phone",
      "occupation",
      "address",
      "health_issues",
      "historical_cases",
      "selected_course",
      "notes",
    ].forEach((field) => {
      elements.profileForm.elements[field].value = customer[field] || "";
    });
    elements.profileForm.elements.remaining_sessions.value =
      customer.remaining_sessions ?? 0;
  }
  elements.customerEmpty.classList.add("is-hidden");
  elements.customerDetail.classList.add("is-hidden");
  elements.followupSection.classList.add("is-hidden");
  elements.appointmentSection.classList.add("is-hidden");
  elements.visitConfirmation.classList.add("is-hidden");
  elements.profileForm.classList.remove("is-hidden");
  elements.profileForm.elements.name.focus();
}

function formatCustomerMeta(customer) {
  return [
    customer.gender || "性别未记",
    customer.age || "年龄未记",
    customer.phone || "电话未记",
    customer.occupation || "职业未记",
    customer.address || "住址未记",
  ].join(" · ");
}

function renderVisitField(label, value) {
  return value
    ? `<div class="visit-field"><span>${escapeHtml(label)}</span><p>${escapeHtml(
        value,
      )}</p></div>`
    : "";
}

function renderInvestigations(records) {
  if (!records.length) {
    elements.investigationList.innerHTML = `
      <div class="source-empty">
        <span>记</span>
        <p>该客户还没有接诊调查记录。</p>
      </div>
    `;
    return;
  }

  elements.investigationList.innerHTML = records
    .map(
      (record) => `
        <details class="visit-card">
          <summary>
            <span class="visit-date">${escapeHtml(record.visit_date)}</span>
            <span class="visit-type">${escapeHtml(record.visit_type)}</span>
            <strong class="visit-chief">${escapeHtml(record.chief_complaint)}</strong>
            <span class="visit-risk">${escapeHtml(record.risk_assessment || "风险未记录")}</span>
          </summary>
          <div class="visit-detail">
            ${renderVisitField("主诉", record.chief_complaint)}
            ${renderVisitField("持续时长", record.symptom_duration)}
            ${renderVisitField("诱发因素", record.trigger)}
            ${renderVisitField("现病史", record.current_history)}
            ${renderVisitField("既往史", record.medical_history)}
            ${renderVisitField("女性专项", record.women_special)}
            ${renderVisitField("查体记录", record.objective_findings)}
            ${renderVisitField("风险评估", record.risk_assessment)}
            ${renderVisitField("调理方案", record.care_plan)}
            ${renderVisitField("告知登记", record.disclosure)}
            ${renderVisitField("本次扣减", `${record.sessions_used || 0} 次`)}
            ${renderVisitField("下次复诊", record.followup_date || "未设置")}
            ${renderVisitField("复诊提醒", record.followup_note)}
            ${renderVisitField("复诊备注", record.followup_notes)}
            <div class="visit-actions">
              <button class="text-action danger-text delete-visit"
                type="button" data-investigation-id="${escapeHtml(record.id)}">
                删除记录
              </button>
            </div>
          </div>
        </details>
      `,
    )
    .join("");
}

function renderFollowups(followups) {
  if (!followups?.length) {
    elements.followupSection.classList.add("is-hidden");
    elements.followupList.innerHTML = "";
    return;
  }
  elements.followupSection.classList.remove("is-hidden");
  elements.followupList.innerHTML = followups
    .map((task) => {
      const statusLabel = {
        pending: "待复诊",
        deferred: "暂时不来",
        completed:
          task.completion_type === "phone_followup"
            ? "电话回访完成"
            : "已完成复诊",
        cancelled: "任务取消",
      }[task.status] || task.status;
      let actions = "";
      if (task.status === "pending") {
        actions = `
          <div class="followup-actions">
            <button class="text-action" type="button"
              data-followup-id="${escapeHtml(task.id)}"
              data-followup-status="completed"
              data-completion-type="visited">已完成复诊</button>
            <button class="text-action" type="button"
              data-followup-id="${escapeHtml(task.id)}"
              data-followup-status="completed"
              data-completion-type="phone_followup">电话回访完成</button>
            <button class="text-action" type="button"
              data-followup-id="${escapeHtml(task.id)}"
              data-followup-status="deferred">暂时不来</button>
            <button class="text-action danger-text" type="button"
              data-followup-id="${escapeHtml(task.id)}"
              data-followup-status="cancelled">取消任务</button>
          </div>
        `;
      } else if (task.status === "deferred") {
        actions = `
          <div class="followup-actions">
            <button class="text-action" type="button"
              data-followup-id="${escapeHtml(task.id)}"
              data-followup-status="pending">恢复待复诊</button>
            <button class="text-action danger-text" type="button"
              data-followup-id="${escapeHtml(task.id)}"
              data-followup-status="cancelled">取消任务</button>
          </div>
        `;
      }
      return `
        <article class="followup-card">
          <div class="followup-card-head">
            <strong>${escapeHtml(task.due_date)}</strong>
            <span>${escapeHtml(statusLabel)}</span>
          </div>
          <p>${escapeHtml(task.note || "未填写复诊提醒备注")}</p>
          ${
            task.resolution_note
              ? `<p class="followup-resolution">${escapeHtml(
                  task.resolution_note,
                )}</p>`
              : ""
          }
          ${actions}
        </article>
      `;
    })
    .join("");
}

function renderAppointments(appointments) {
  if (!appointments?.length) {
    elements.appointmentSection.classList.add("is-hidden");
    elements.appointmentList.innerHTML = "";
    return;
  }
  elements.appointmentSection.classList.remove("is-hidden");
  elements.appointmentList.innerHTML = appointments
    .map((appointment) => {
      const scheduled = new Date(appointment.scheduled_at);
      const statusLabel = {
        scheduled: "已预约",
        completed: "已完成",
        cancelled: "已取消",
      }[appointment.status] || appointment.status;
      return `
        <article class="appointment-card">
          <strong>${escapeHtml(
            scheduled.toLocaleString("zh-CN", {
              month: "2-digit",
              day: "2-digit",
              hour: "2-digit",
              minute: "2-digit",
              hour12: false,
            }),
          )}</strong>
          <p>${escapeHtml(appointment.service_item || "未指定项目")} · ${escapeHtml(
            statusLabel,
          )}</p>
          ${appointment.note ? `<p>${escapeHtml(appointment.note)}</p>` : ""}
        </article>
      `;
    })
    .join("");
}

function renderCustomerDetail(detail) {
  state.customerDetail = detail;
  const customer = detail.customer;
  elements.customerDialog.classList.remove("mobile-customer-editing");
  elements.customerDialog.classList.add("mobile-customer-selected");
  elements.customerEmpty.classList.add("is-hidden");
  elements.profileForm.classList.add("is-hidden");
  elements.customerDetail.classList.remove("is-hidden");
  elements.customerAvatar.textContent = customer.name.slice(0, 1);
  elements.customerDetailName.textContent = customer.name;
  elements.customerDetailType.textContent =
    customer.id === state.activeCustomerId ? "当前聊天客户" : "客户档案";
  elements.customerDetailMeta.textContent = formatCustomerMeta(customer);
  elements.customerDetailNotes.textContent =
    customer.notes || "暂无客户备注";
  elements.customerDetailHealth.textContent =
    customer.health_issues || "未记录";
  elements.customerDetailHistory.textContent =
    customer.historical_cases || "未记录";
  elements.customerDetailHealthFull.textContent =
    customer.health_issues || "未记录";
  elements.customerDetailHistoryFull.textContent =
    customer.historical_cases || "未记录";
  elements.customerDetailCourse.textContent =
    customer.selected_course || "未选择";
  elements.customerDetailRemaining.textContent =
    `${customer.remaining_sessions ?? 0} 次`;
  const quick = detail.quick_summary || {};
  elements.quickRiskCard.className =
    `quick-clinical-card risk-card level-${quick.major_risk_level || "none"}`;
  elements.customerDetailRisk.textContent =
    quick.major_risk || "未见明确风险记录";
  elements.customerLastComplaint.textContent = quick.last_chief_complaint
    ? `${quick.latest_visit_date || ""} · ${quick.last_chief_complaint}`
    : "暂无接诊主诉";
  elements.customerLastFeedback.textContent =
    quick.last_followup_feedback || "暂无复诊反馈";
  elements.quickDangerCard.classList.toggle(
    "has-danger",
    Boolean(quick.recent_danger_signal),
  );
  elements.customerDangerSignal.textContent = quick.recent_danger_signal
    ? `${quick.danger_signal_date || ""} · ${quick.recent_danger_signal}`
    : "最近记录未见危险信号";
  elements.investigationForm.classList.add("is-hidden");
  elements.visitConfirmation.classList.add("is-hidden");
  renderInvestigations(detail.investigations);
  renderFollowups(detail.followups || []);
  renderAppointments(detail.appointments || []);
}

async function loadCustomerDetail(customerId) {
  if (!customerId) {
    state.customerDetail = null;
    showCustomerEmpty();
    return;
  }
  try {
    const detail = await apiRequest(
      `/api/customers/${encodeURIComponent(customerId)}`,
    );
    renderCustomerDetail(detail);
  } catch (error) {
    state.customerDetail = null;
    showCustomerEmpty();
    showToast(error instanceof Error ? error.message : "读取客户详情失败");
  }
}

function resetConversation(clearInput = true) {
  state.sessionId = null;
  state.lastSources = [];
  localStorage.removeItem("therapy_session_id");
  elements.messages.innerHTML = state.initialWelcomeHtml;
  renderSourceCount();
  if (clearInput) {
    elements.input.value = "";
    resizeInput();
  }
}

async function selectCustomer(customerId) {
  if (state.busy) {
    showToast("请等待当前回答完成后再切换客户");
    return;
  }
  if (customerId === state.activeCustomerId) {
    if (customerId) await loadCustomerDetail(customerId);
    renderCustomerList(elements.customerSearch.value);
    return;
  }

  resetConversation(false);
  state.pendingVisit = null;
  state.activeCustomerId = customerId || null;
  if (state.activeCustomerId) {
    localStorage.setItem("therapy_customer_id", state.activeCustomerId);
  } else {
    localStorage.removeItem("therapy_customer_id");
  }
  renderCustomerList(elements.customerSearch.value);
  renderActiveCustomer();
  if (state.activeCustomerId) {
    await loadCustomerDetail(state.activeCustomerId);
  } else {
    showCustomerEmpty();
  }
}

async function openCustomerDialog() {
  if (!elements.customerDialog.open) {
    elements.customerDialog.showModal();
  }
  await loadCustomers("", true);
  if (state.activeCustomerId) {
    await loadCustomerDetail(state.activeCustomerId);
  } else {
    showCustomerEmpty();
  }
}

function closeCustomerDialog() {
  elements.customerDialog.close();
}

function todayValue() {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function showInvestigationForm() {
  if (!state.activeCustomerId) {
    showToast("请先选择或新建客户");
    return;
  }
  elements.investigationForm.reset();
  elements.investigationForm.elements.visit_date.value = todayValue();
  const remaining =
    state.customerDetail?.customer?.remaining_sessions ?? 0;
  elements.investigationForm.elements.sessions_used.value =
    remaining > 0 ? "1" : "0";
  state.pendingVisit = null;
  elements.visitConfirmation.classList.add("is-hidden");
  elements.investigationForm.classList.remove("show-optional");
  elements.toggleOptionalFields.textContent = "补充更多信息";
  elements.investigationForm.classList.remove("is-hidden");
  elements.investigationForm.elements.chief_complaint.focus();
}

function formatSlotTime(value) {
  return new Date(value).toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

function appointmentDateLabel(value) {
  const [year, month, day] = String(value).split("-").map(Number);
  return new Date(year, month - 1, day).toLocaleDateString("zh-CN", {
    year: "numeric",
    month: "long",
    day: "numeric",
    weekday: "long",
  });
}

function renderAppointmentCustomerPicker() {
  const query = elements.appointmentCustomerSearch.value.trim().toLowerCase();
  const customers = state.customers.filter((customer) => {
    if (!query) return true;
    return [customer.name, customer.phone, customer.selected_course].some(
      (value) => String(value || "").toLowerCase().includes(query),
    );
  });
  elements.appointmentCustomerPicker.innerHTML = customers.length
    ? customers
        .map(
          (customer) => `
            <button class="appointment-customer-option ${
              customer.id === state.appointmentSelectedCustomerId ? "selected" : ""
            }" type="button" data-appointment-customer-id="${escapeHtml(
              customer.id,
            )}">
              <span>${escapeHtml(customer.name.slice(0, 1))}</span>
              <strong>${escapeHtml(customer.name)}</strong>
              <small>${escapeHtml(
                String(customer.phone || "").replace(/\D/g, "").slice(-4) ||
                  "未登记手机",
              )}${customer.selected_course ? ` · ${escapeHtml(customer.selected_course)}` : ""}</small>
            </button>
          `,
        )
        .join("")
    : '<div class="workbench-empty">没有匹配的客户</div>';
  elements.bookAppointment.disabled = !state.appointmentSelectedCustomerId;
}

function renderAppointmentDayList() {
  const appointments = (state.appointmentSchedule?.slots || []).filter(
    (slot) =>
      (slot.status === "booked" || slot.status === "completed") &&
      slot.appointment_id &&
      slot.customer_id,
  );
  elements.appointmentDayList.innerHTML = appointments.length
    ? appointments
        .map((slot) => {
          const status = slot.status === "completed" ? "已完成" : "已预约";
          return `
            <article class="appointment-day-row">
              <div class="appointment-day-time">
                <strong>${escapeHtml(formatSlotTime(slot.start_at))}</strong>
                <small>${escapeHtml(formatSlotTime(slot.end_at))}</small>
              </div>
              <div class="appointment-day-copy">
                <strong>${escapeHtml(slot.customer_name || "客户")}</strong>
                <small>${escapeHtml(slot.service_item || "门店养护服务")} · ${status}</small>
                ${slot.note ? `<p>${escapeHtml(slot.note)}</p>` : ""}
              </div>
              ${
                slot.status === "booked"
                  ? `<div class="appointment-day-actions">
                      <button class="text-button" type="button"
                        data-page-appointment-status="completed"
                        data-customer-id="${escapeHtml(slot.customer_id)}"
                        data-appointment-id="${escapeHtml(slot.appointment_id)}">
                        标记完成
                      </button>
                      <button class="text-button danger-text" type="button"
                        data-page-appointment-status="cancelled"
                        data-customer-id="${escapeHtml(slot.customer_id)}"
                        data-appointment-id="${escapeHtml(slot.appointment_id)}">
                        取消预约
                      </button>
                    </div>`
                  : '<span class="appointment-day-status">已完成</span>'
              }
            </article>
          `;
        })
        .join("")
    : '<div class="workbench-empty">当天还没有已预约客户</div>';
}

function selectAppointmentSlot(slotId) {
  state.appointmentSelectedSlotId = slotId;
  state.appointmentSelectedCustomerId = null;
  elements.appointmentCustomerSearch.value = "";
  elements.appointmentServiceItem.value = "";
  elements.appointmentNote.value = "";
  renderAppointmentPageSchedule(state.appointmentSchedule);
}

function renderAppointmentBookingSelection() {
  const slot = state.appointmentSchedule?.slots.find(
    (item) => item.id === state.appointmentSelectedSlotId,
  );
  if (!slot) {
    elements.appointmentBookingEmpty.classList.remove("is-hidden");
    elements.appointmentBookingPanel.classList.add("is-hidden");
    elements.appointmentExisting.classList.add("is-hidden");
    return;
  }
  if (slot.status === "available") {
    elements.appointmentBookingEmpty.classList.add("is-hidden");
    elements.appointmentExisting.classList.add("is-hidden");
    elements.appointmentBookingPanel.classList.remove("is-hidden");
    elements.appointmentBookingTime.textContent =
      `${formatSlotTime(slot.start_at)}–${formatSlotTime(slot.end_at)}`;
    renderAppointmentCustomerPicker();
    return;
  }
  elements.appointmentBookingEmpty.classList.add("is-hidden");
  elements.appointmentBookingPanel.classList.add("is-hidden");
  elements.appointmentExisting.classList.remove("is-hidden");
  elements.appointmentExistingName.textContent =
    slot.customer_name || (slot.status === "completed" ? "已完成预约" : "已预约客户");
  elements.appointmentExistingMeta.textContent =
    `${formatSlotTime(slot.start_at)}–${formatSlotTime(slot.end_at)} · ` +
    `${slot.service_item || "门店养护服务"} · ${
      slot.status === "completed" ? "已完成" : "已预约"
    }`;
  elements.appointmentExistingNote.textContent =
    slot.note || "没有填写预约备注";
  elements.appointmentExistingActions.classList.toggle(
    "is-hidden",
    slot.status !== "booked",
  );
}

function renderAppointmentPageSchedule(schedule) {
  state.appointmentSchedule = schedule;
  if (!schedule.slots.length) {
    state.appointmentSelectedSlotId = null;
    elements.appointmentPageSlots.innerHTML = `
      <div class="workbench-empty">
        这一天还没有时段。先确认开始、结束时间和间隔，再点击“生成 / 更新时段”。
      </div>
    `;
    elements.appointmentBookingEmpty.classList.remove("is-hidden");
    elements.appointmentBookingPanel.classList.add("is-hidden");
    elements.appointmentExisting.classList.add("is-hidden");
    renderAppointmentDayList();
    return;
  }
  if (
    state.appointmentSelectedSlotId &&
    !schedule.slots.some((slot) => slot.id === state.appointmentSelectedSlotId)
  ) {
    state.appointmentSelectedSlotId = null;
  }
  elements.appointmentPageSlots.innerHTML = schedule.slots
    .map((slot) => {
      const selected = slot.id === state.appointmentSelectedSlotId;
      const detail =
        slot.status === "booked"
          ? slot.customer_name || "已预约"
          : slot.status === "closed"
            ? "已关闭"
            : slot.status === "completed"
              ? "已完成"
            : "可预约";
      const action =
        slot.status === "booked" || slot.status === "completed"
          ? ""
          : `<button class="slot-status-toggle" type="button"
              data-slot-id="${escapeHtml(slot.id)}"
              data-slot-status="${slot.status === "closed" ? "available" : "closed"}">
              ${slot.status === "closed" ? "重新开放" : "关闭此时段"}
            </button>`;
      return `
        <div class="appointment-page-slot-wrap">
          <button class="appointment-slot appointment-page-slot ${
            selected ? "selected" : ""
          } ${slot.status}" type="button"
            data-appointment-slot-id="${escapeHtml(slot.id)}"
            ${slot.status === "closed" ? "disabled" : ""}>
            <strong>${escapeHtml(formatSlotTime(slot.start_at))}–${escapeHtml(
              formatSlotTime(slot.end_at),
            )}</strong>
            <small>${escapeHtml(detail)}</small>
          </button>
          ${action}
        </div>
      `;
    })
    .join("");
  renderAppointmentBookingSelection();
  renderAppointmentDayList();
}

async function loadAppointmentPageSchedule() {
  const scheduleDate = elements.appointmentScheduleForm.elements.schedule_date.value;
  if (!scheduleDate) return;
  state.appointmentDate = scheduleDate;
  elements.appointmentSelectedDate.textContent = appointmentDateLabel(scheduleDate);
  elements.appointmentPageSlots.innerHTML =
    '<div class="workbench-empty">正在读取当天排班…</div>';
  try {
    const schedule = await apiRequest(
      `/api/schedules/${encodeURIComponent(scheduleDate)}`,
    );
    renderAppointmentPageSchedule(schedule);
  } catch (error) {
    elements.appointmentPageSlots.innerHTML = `
      <div class="workbench-empty">${escapeHtml(
        error instanceof Error ? error.message : "读取排班失败",
      )}</div>
    `;
  }
}

async function configureAppointmentPageSchedule() {
  const form = elements.appointmentScheduleForm;
  const payload = {
    schedule_date: form.elements.schedule_date.value,
    start_time: form.elements.start_time.value,
    end_time: form.elements.end_time.value,
    interval_minutes: Number(form.elements.interval_minutes.value),
  };
  elements.saveAppointmentSchedule.disabled = true;
  try {
    const schedule = await apiRequest("/api/schedules/configure", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    state.appointmentSelectedSlotId = null;
    state.appointmentSelectedCustomerId = null;
    state.appointmentDate = payload.schedule_date;
    elements.appointmentSelectedDate.textContent = appointmentDateLabel(
      payload.schedule_date,
    );
    renderAppointmentPageSchedule(schedule);
    showToast("当天时段已更新");
  } catch (error) {
    showToast(error instanceof Error ? error.message : "更新排班失败");
  } finally {
    elements.saveAppointmentSchedule.disabled = false;
  }
}

function openAppointmentManagement() {
  const form = elements.appointmentScheduleForm;
  if (!form.elements.schedule_date.value) {
    form.elements.schedule_date.value = todayValue();
  }
  loadAppointmentPageSchedule();
}

async function updatePageAppointmentStatus(customerId, appointmentId, status) {
  const confirmText =
    status === "completed"
      ? "确认这次预约已经完成？"
      : "确认取消这次预约？取消后会释放该时段。";
  if (!window.confirm(confirmText)) return;
  try {
    await apiRequest(
      `/api/customers/${encodeURIComponent(
        customerId,
      )}/appointments/${encodeURIComponent(appointmentId)}/status`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      },
    );
    showToast(status === "completed" ? "预约已完成" : "预约已取消，时段已释放");
    state.appointmentSelectedSlotId = null;
    await Promise.all([loadAppointmentPageSchedule(), loadDashboard()]);
  } catch (error) {
    showToast(error instanceof Error ? error.message : "更新预约状态失败");
  }
}

function renderVisitConfirmation(proposal) {
  state.pendingVisit = proposal;
  elements.investigationForm.classList.add("is-hidden");
  elements.visitConfirmation.classList.remove("is-hidden");
  elements.confirmPreviousSessions.textContent =
    String(proposal.previous_remaining_sessions);
  elements.confirmUsedSessions.textContent = String(proposal.sessions_used);
  elements.confirmRemainingSessions.textContent =
    String(proposal.proposed_remaining_sessions);
  elements.confirmFollowupDate.textContent =
    proposal.followup_date || "未设置";
  elements.confirmVisitType.textContent =
    `${proposal.visit_date} · ${proposal.visit_type}`;
  elements.confirmChiefComplaint.textContent = proposal.chief_complaint;
  elements.visitConfirmation.scrollIntoView({
    behavior: "smooth",
    block: "center",
  });
}

elements.form.addEventListener("submit", (event) => {
  event.preventDefault();
  sendMessage(elements.input.value);
});

elements.input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    sendMessage(elements.input.value);
  }
});

elements.input.addEventListener("input", resizeInput);

elements.messages.addEventListener("click", (event) => {
  const button = event.target.closest(".prompt-card");
  if (button) {
    const prompt = button.querySelector("strong").textContent;
    elements.input.value = prompt;
    resizeInput();
    sendMessage(prompt);
  }
});

elements.toggleSources.addEventListener("click", () => {
  elements.shell.classList.toggle("sources-open");
  renderSources(state.lastSources);
});

elements.closeSources.addEventListener("click", () => {
  elements.shell.classList.remove("sources-open");
});

elements.openDashboard.addEventListener("click", () => {
  showView("dashboard");
});

elements.openAppointmentManagement.addEventListener("click", () => {
  showView("appointments");
});

elements.topbarDashboard.addEventListener("click", () => {
  showView("dashboard");
});

elements.topbarAppointments.addEventListener("click", () => {
  showView("appointments");
});

elements.openBackups.addEventListener("click", openBackupDialog);
elements.dashboardOpenBackups.addEventListener("click", openBackupDialog);
elements.dashboardOpenAppointments.addEventListener("click", () => {
  showView("appointments");
});
elements.openStaffManagement.addEventListener(
  "click",
  openStaffManagement,
);
elements.closeStaffManagement.addEventListener("click", () => {
  elements.staffManagementDialog.close();
});
elements.staffManagementDialog.addEventListener("click", (event) => {
  if (event.target === elements.staffManagementDialog) {
    elements.staffManagementDialog.close();
  }
});
elements.refreshStaffAccounts.addEventListener("click", loadStaffAccounts);
elements.refreshStaffAudit.addEventListener("click", loadStaffAudit);
elements.refreshLoginAttempts.addEventListener("click", loadLoginAttempts);
elements.staffAccountForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const submit = elements.staffAccountForm.querySelector('[type="submit"]');
  submit.disabled = true;
  try {
    const data = Object.fromEntries(new FormData(elements.staffAccountForm));
    await apiRequest("/api/staff/accounts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    elements.staffAccountForm.reset();
    showToast("员工账号已创建");
    await Promise.all([loadStaffAccounts(), loadStaffAudit()]);
  } catch (error) {
    showToast(error instanceof Error ? error.message : "创建员工失败");
  } finally {
    submit.disabled = false;
  }
});
elements.staffAccountList.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-staff-id]");
  if (!button) return;
  const targetStatus = button.dataset.staffStatus;
  if (
    targetStatus === "disabled" &&
    !window.confirm("确认停用该员工账号？已登录会话会立即失效。")
  ) {
    return;
  }
  button.disabled = true;
  try {
    await apiRequest(
      `/api/staff/accounts/${encodeURIComponent(button.dataset.staffId)}`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: targetStatus }),
      },
    );
    showToast(targetStatus === "disabled" ? "员工账号已停用" : "员工账号已启用");
    await Promise.all([loadStaffAccounts(), loadStaffAudit()]);
  } catch (error) {
    showToast(error instanceof Error ? error.message : "更新员工账号失败");
  } finally {
    button.disabled = false;
  }
});
elements.staffLogout.addEventListener("click", async () => {
  await apiRequest("/api/staff/logout", { method: "POST" }).catch(() => {});
  window.location.reload();
});
elements.openPortalAdmin.addEventListener("click", openPortalAdmin);
elements.closePortalAdmin.addEventListener("click", () => {
  elements.portalAdminDialog.close();
});
elements.portalAdminDialog.addEventListener("click", (event) => {
  if (event.target === elements.portalAdminDialog) {
    elements.portalAdminDialog.close();
  }
});
elements.refreshPortalAccounts.addEventListener("click", loadPortalAccounts);
elements.refreshDeletionRequests.addEventListener("click", loadDeletionRequests);
let portalAccountSearchTimer = null;
elements.portalAccountSearch.addEventListener("input", () => {
  window.clearTimeout(portalAccountSearchTimer);
  portalAccountSearchTimer = window.setTimeout(loadPortalAccounts, 220);
});
elements.portalAccountList.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-portal-action]");
  if (!button) return;
  const action = button.dataset.portalAction;
  const customerId = button.dataset.customerId;
  if (
    action === "revoke" &&
    !window.confirm(
      "确认撤销该顾客的网页账号？顾客会立即退出，之后无法登录，但接诊档案不会删除。",
    )
  ) {
    return;
  }
  if (
    action === "restore" &&
    !window.confirm("确认恢复该顾客的网页账号登录权限？")
  ) {
    return;
  }
  button.disabled = true;
  try {
    if (action === "recovery") {
      const recovery = await apiRequest(
        `/api/customers/${encodeURIComponent(
          customerId,
        )}/portal-recovery-code`,
        { method: "POST" },
      );
      state.currentPortalRecovery = recovery;
      elements.portalRecoveryCode.textContent = recovery.recovery_code;
      elements.portalRecoveryExpiry.textContent = `有效期至 ${new Date(
        recovery.expires_at,
      ).toLocaleString("zh-CN")}`;
      elements.portalRecoveryResult.classList.remove("is-hidden");
      showToast("找回码已生成，请核对顾客身份后交给本人");
    } else {
      const endpoint =
        action === "revoke" ? "revoke" : "restore";
      await apiRequest(
        `/api/customers/${encodeURIComponent(
          customerId,
        )}/portal-account/${endpoint}`,
        { method: "POST" },
      );
      showToast(action === "revoke" ? "顾客账号已撤销" : "顾客账号已恢复");
      await Promise.all([loadPortalAccounts(), loadDeletionRequests()]);
    }
  } catch (error) {
    showToast(error instanceof Error ? error.message : "顾客账号操作失败");
  } finally {
    button.disabled = false;
  }
});
elements.portalDeletionList.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-deletion-action]");
  if (!button) return;
  const action = button.dataset.deletionAction;
  const requestId = button.dataset.requestId;
  const confirmation =
    action === "approve"
      ? "确认同意删除？这会清除网页账号、身份资料、接诊、预约、复诊和养护说明，且无法撤销。旧备份文件不会自动清除。"
      : "确认拒绝这条资料删除申请？";
  if (!window.confirm(confirmation)) return;
  button.disabled = true;
  try {
    const resolved = await apiRequest(
      `/api/portal-admin/deletion-requests/${encodeURIComponent(
        requestId,
      )}/resolve`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, note: "" }),
      },
    );
    if (
      action === "approve" &&
      resolved.customer_id === state.activeCustomerId
    ) {
      state.activeCustomerId = null;
      localStorage.removeItem("therapy_customer_id");
      showCustomerEmpty();
    }
    showToast(action === "approve" ? "顾客资料已注销" : "删除申请已拒绝");
    await Promise.all([
      loadPortalAccounts(),
      loadDeletionRequests(),
      loadCustomers("", true),
      loadDashboard(),
    ]);
  } catch (error) {
    showToast(error instanceof Error ? error.message : "处理删除申请失败");
  } finally {
    button.disabled = false;
  }
});
elements.copyPortalRecoveryCode.addEventListener("click", async () => {
  if (!state.currentPortalRecovery) return;
  try {
    await copyText(state.currentPortalRecovery.recovery_code);
    showToast("找回码已复制");
  } catch (error) {
    showToast(error instanceof Error ? error.message : "复制失败");
  }
});
elements.closeBackups.addEventListener("click", () => {
  elements.backupDialog.close();
});
elements.backupDialog.addEventListener("click", (event) => {
  if (event.target === elements.backupDialog) elements.backupDialog.close();
});
elements.openPdfIntake.addEventListener("click", openPdfIntakeDialog);
elements.dashboardOpenPdfIntake.addEventListener("click", openPdfIntakeDialog);
elements.closePdfIntake.addEventListener("click", () => {
  elements.pdfIntakeDialog.close();
});
elements.pdfIntakeDialog.addEventListener("click", (event) => {
  if (event.target === elements.pdfIntakeDialog) {
    elements.pdfIntakeDialog.close();
  }
});
elements.pdfIntakeTarget.addEventListener("change", updatePdfCustomerMode);
elements.parsePdfIntake.addEventListener("click", parsePdfIntakeFile);
elements.pdfIntakeForm.addEventListener("submit", submitPdfIntake);
elements.refreshPdfEditHistory.addEventListener("click", loadPdfEditHistory);
elements.refreshPdfPreferences.addEventListener("click", loadPdfPreferences);
elements.pdfPreferenceCandidates.addEventListener("click", (event) => {
  const button = event.target.closest("[data-preference-action]");
  if (!button) return;
  button.disabled = true;
  resolvePdfPreference(
    button.dataset.candidateId,
    button.dataset.preferenceAction,
  ).finally(() => {
    button.disabled = false;
  });
});
elements.pdfPendingClinicRules.addEventListener("click", (event) => {
  const button = event.target.closest("[data-preference-review]");
  if (!button) return;
  button.disabled = true;
  reviewPdfClinicPreference(
    button.dataset.preferenceId,
    button.dataset.preferenceReview,
  ).finally(() => {
    button.disabled = false;
  });
});
elements.exportBackup.addEventListener("click", exportBackup);
elements.exportExcel.addEventListener("click", exportTherapistExcel);
elements.refreshBackups.addEventListener("click", loadBackupList);
elements.runBackupMaintenance.addEventListener(
  "click",
  runBackupMaintenance,
);
elements.previewRestore.addEventListener("click", previewRestoreBackup);
elements.confirmRestore.addEventListener("click", confirmRestoreBackup);
elements.restoreFile.addEventListener("change", () => {
  state.pendingRestore = null;
  elements.restorePreview.classList.add("is-hidden");
});

elements.startConsultation.addEventListener("click", () => {
  elements.knowledgeInput.focus();
  document
    .querySelector("#knowledge-hub")
    ?.scrollIntoView({ behavior: "smooth", block: "start" });
});

elements.refreshDashboard.addEventListener("click", loadDashboard);
elements.knowledgeForm.addEventListener("submit", (event) => {
  event.preventDefault();
  searchIntegratedKnowledge();
});

document.querySelectorAll(".metric-card").forEach((card) => {
  card.addEventListener("click", () => {
    document
      .querySelector(`#${card.dataset.scroll}`)
      ?.scrollIntoView({ behavior: "smooth", block: "start" });
  });
});

elements.dashboardView.addEventListener("click", async (event) => {
  const customerCard = event.target.closest(".workbench-customer");
  if (!customerCard) return;
  await selectCustomer(customerCard.dataset.customerId);
  await openCustomerDialog();
});

elements.quickCustomerSearch.addEventListener("input", (event) => {
  searchCustomerByPhoneTail(event.target.value);
});

elements.quickSearchResults.addEventListener("click", async (event) => {
  const result = event.target.closest("[data-customer-id]");
  if (!result) return;
  await selectCustomer(result.dataset.customerId);
  await openCustomerDialog();
});

elements.copyCustomerScript.addEventListener("click", copyCustomerScript);
elements.editCustomerHandout.addEventListener("click", openHandoutEditor);
elements.closeHandoutEditor.addEventListener("click", () => {
  elements.handoutDialog.close();
});
elements.handoutDialog.addEventListener("click", (event) => {
  if (event.target === elements.handoutDialog) elements.handoutDialog.close();
});
elements.copyHandout.addEventListener("click", async () => {
  try {
    await copyText(elements.handoutForm.elements.content.value);
    showToast("养护说明已复制");
  } catch (error) {
    showToast(error.message);
  }
});
elements.resetHandout.addEventListener("click", async () => {
  if (!state.activeCustomerId) return;
  try {
    const draft = await apiRequest(
      `/api/customers/${encodeURIComponent(
        state.activeCustomerId,
      )}/handout`,
      { method: "DELETE" },
    );
    elements.handoutForm.elements.title.value = draft.title;
    elements.handoutForm.elements.content.value = draft.content;
    elements.handoutEditorState.textContent =
      "已恢复为根据最近接诊自动生成的版本。";
    showToast("已恢复自动生成内容");
  } catch (error) {
    showToast(error instanceof Error ? error.message : "恢复失败");
  }
});
elements.handoutForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!state.activeCustomerId) return;
  const submit = elements.handoutForm.querySelector('[type="submit"]');
  submit.disabled = true;
  try {
    const data = Object.fromEntries(new FormData(elements.handoutForm));
    const draft = await apiRequest(
      `/api/customers/${encodeURIComponent(
        state.activeCustomerId,
      )}/handout`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      },
    );
    elements.handoutEditorState.textContent =
      "已保存。顾客网页会立即读取此修改版本。";
    showToast(draft.is_customized ? "养护说明已更新" : "已保存");
  } catch (error) {
    showToast(error instanceof Error ? error.message : "保存失败");
  } finally {
    submit.disabled = false;
  }
});
elements.createPortalInvite.addEventListener("click", createPortalInvite);
elements.closeInvite.addEventListener("click", () => {
  elements.inviteDialog.close();
});
elements.inviteDialog.addEventListener("click", (event) => {
  if (event.target === elements.inviteDialog) elements.inviteDialog.close();
});
elements.copyInvite.addEventListener("click", async () => {
  if (!state.currentInvite) return;
  try {
    await copyText(state.currentInvite.invite_code);
    showToast("邀请码已复制");
  } catch (error) {
    showToast(error.message);
  }
});
elements.copyPortalLink.addEventListener("click", async () => {
  try {
    await copyText(`${window.location.origin}/customer/`);
    showToast("顾客网页链接已复制");
  } catch (error) {
    showToast(error.message);
  }
});
elements.toggleOptionalFields.addEventListener("click", () => {
  const expanded = elements.investigationForm.classList.toggle("show-optional");
  elements.toggleOptionalFields.textContent = expanded
    ? "收起补充信息"
    : "补充更多信息";
});

elements.openCustomers.addEventListener("click", openCustomerDialog);
elements.closeCustomers.addEventListener("click", closeCustomerDialog);
elements.mobileCustomerSwitch?.addEventListener("click", () => {
  elements.customerDialog.classList.remove("mobile-customer-selected");
  elements.customerSearch.focus();
});
elements.customerDialog.addEventListener("click", (event) => {
  if (event.target === elements.customerDialog) closeCustomerDialog();
});

elements.customerList.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-customer-id]");
  if (!button) return;
  await selectCustomer(button.dataset.customerId || null);
});

elements.customerSearch.addEventListener("input", () => {
  renderCustomerList(elements.customerSearch.value);
});

elements.newCustomer.addEventListener("click", () => {
  showProfileForm();
});

elements.editProfile.addEventListener("click", () => {
  if (state.customerDetail) {
    showProfileForm(state.customerDetail.customer);
  }
});

elements.cancelProfile.addEventListener("click", () => {
  if (state.customerDetail) {
    renderCustomerDetail(state.customerDetail);
  } else {
    showCustomerEmpty();
  }
});

elements.profileForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const submit = elements.profileForm.querySelector('[type="submit"]');
  submit.disabled = true;
  try {
    const data = Object.fromEntries(new FormData(elements.profileForm));
    data.remaining_sessions = Number(data.remaining_sessions || 0);
    const customer = await apiRequest(
      state.editingCustomerId
        ? `/api/customers/${encodeURIComponent(state.editingCustomerId)}`
        : "/api/customers",
      {
        method: state.editingCustomerId ? "PATCH" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      },
    );
    showToast(state.editingCustomerId ? "客户资料已更新" : "客户已创建");
    state.editingCustomerId = null;
    await loadCustomers("", false);
    await selectCustomer(customer.id);
    await loadDashboard();
  } catch (error) {
    showToast(error instanceof Error ? error.message : "保存客户资料失败");
  } finally {
    submit.disabled = false;
  }
});

elements.newInvestigation.addEventListener("click", showInvestigationForm);
elements.cancelInvestigation.addEventListener("click", () => {
  elements.investigationForm.classList.add("is-hidden");
});

elements.appointmentScheduleForm.addEventListener(
  "submit",
  async (event) => {
    event.preventDefault();
    await configureAppointmentPageSchedule();
  },
);
elements.appointmentScheduleForm.elements.schedule_date.addEventListener(
  "change",
  loadAppointmentPageSchedule,
);
elements.refreshAppointmentPage.addEventListener(
  "click",
  loadAppointmentPageSchedule,
);
elements.appointmentPageSlots.addEventListener("click", async (event) => {
  const toggle = event.target.closest(".slot-status-toggle");
  if (toggle) {
    try {
      await apiRequest(
        `/api/schedules/slots/${encodeURIComponent(toggle.dataset.slotId)}`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status: toggle.dataset.slotStatus }),
        },
      );
      state.appointmentSelectedSlotId = null;
      await loadAppointmentPageSchedule();
    } catch (error) {
      showToast(error instanceof Error ? error.message : "调整时段失败");
    }
    return;
  }
  const slot = event.target.closest("[data-appointment-slot-id]");
  if (!slot || slot.disabled) return;
  selectAppointmentSlot(slot.dataset.appointmentSlotId);
});

elements.appointmentCustomerSearch.addEventListener(
  "input",
  renderAppointmentCustomerPicker,
);
elements.appointmentCustomerPicker.addEventListener("click", (event) => {
  const button = event.target.closest("[data-appointment-customer-id]");
  if (!button) return;
  state.appointmentSelectedCustomerId = button.dataset.appointmentCustomerId;
  const customer = state.customers.find(
    (item) => item.id === state.appointmentSelectedCustomerId,
  );
  if (!elements.appointmentServiceItem.value && customer?.selected_course) {
    elements.appointmentServiceItem.value = customer.selected_course;
  }
  renderAppointmentCustomerPicker();
});
elements.bookAppointment.addEventListener("click", async () => {
  const slot = state.appointmentSchedule?.slots.find(
    (item) => item.id === state.appointmentSelectedSlotId,
  );
  if (!slot || slot.status !== "available") {
    showToast("请先选择一个可预约时段");
    return;
  }
  if (!state.appointmentSelectedCustomerId) {
    showToast("请选择一个客户");
    return;
  }
  elements.bookAppointment.disabled = true;
  try {
    await apiRequest(
      `/api/customers/${encodeURIComponent(
        state.appointmentSelectedCustomerId,
      )}/appointments/from-slot`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          slot_id: slot.id,
          service_item: elements.appointmentServiceItem.value,
          note: elements.appointmentNote.value,
        }),
      },
    );
    showToast("预约已保存");
    const customerId = state.appointmentSelectedCustomerId;
    state.appointmentSelectedSlotId = null;
    state.appointmentSelectedCustomerId = null;
    elements.appointmentServiceItem.value = "";
    elements.appointmentNote.value = "";
    elements.appointmentCustomerSearch.value = "";
    await Promise.all([loadAppointmentPageSchedule(), loadDashboard()]);
    if (state.activeCustomerId === customerId) {
      await loadCustomerDetail(customerId);
    }
  } catch (error) {
    showToast(error instanceof Error ? error.message : "保存预约失败");
  } finally {
    elements.bookAppointment.disabled = false;
  }
});

elements.completePageAppointment.addEventListener("click", async () => {
  const slot = state.appointmentSchedule?.slots.find(
    (item) => item.id === state.appointmentSelectedSlotId,
  );
  if (!slot?.appointment_id || !slot?.customer_id) return;
  await updatePageAppointmentStatus(
    slot.customer_id,
    slot.appointment_id,
    "completed",
  );
});
elements.cancelPageAppointment.addEventListener("click", async () => {
  const slot = state.appointmentSchedule?.slots.find(
    (item) => item.id === state.appointmentSelectedSlotId,
  );
  if (!slot?.appointment_id || !slot?.customer_id) return;
  await updatePageAppointmentStatus(
    slot.customer_id,
    slot.appointment_id,
    "cancelled",
  );
});
elements.appointmentDayList.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-page-appointment-status]");
  if (!button) return;
  button.disabled = true;
  try {
    await updatePageAppointmentStatus(
      button.dataset.customerId,
      button.dataset.appointmentId,
      button.dataset.pageAppointmentStatus,
    );
  } finally {
    button.disabled = false;
  }
});

elements.followupList.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-followup-status]");
  if (!button || !state.activeCustomerId) return;
  const status = button.dataset.followupStatus;
  let note = "";
  if (status === "deferred" || status === "cancelled") {
    note = window.prompt("可填写备注，留空也可以：", "") || "";
  }
  if (
    status === "cancelled" &&
    !window.confirm("确认取消这个复诊任务？")
  ) {
    return;
  }
  button.disabled = true;
  try {
    await apiRequest(
      `/api/customers/${encodeURIComponent(
        state.activeCustomerId,
      )}/followups/${encodeURIComponent(
        button.dataset.followupId,
      )}/status`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          status,
          completion_type: button.dataset.completionType || null,
          resolution_note: note,
        }),
      },
    );
    showToast("复诊任务状态已更新");
    await loadCustomerDetail(state.activeCustomerId);
    await loadDashboard();
  } catch (error) {
    showToast(error instanceof Error ? error.message : "更新复诊任务失败");
  } finally {
    button.disabled = false;
  }
});

elements.investigationForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!state.activeCustomerId) return;
  const submit = elements.investigationForm.querySelector('[type="submit"]');
  submit.disabled = true;
  try {
    const data = Object.fromEntries(new FormData(elements.investigationForm));
    data.sessions_used = Number(data.sessions_used || 0);
    if (!data.followup_date) delete data.followup_date;
    const proposal = await apiRequest(
      `/api/customers/${encodeURIComponent(
        state.activeCustomerId,
      )}/visits/prepare`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      },
    );
    renderVisitConfirmation(proposal);
  } catch (error) {
    showToast(error instanceof Error ? error.message : "生成接诊确认失败");
  } finally {
    submit.disabled = false;
  }
});

elements.cancelConfirmVisit.addEventListener("click", () => {
  state.pendingVisit = null;
  elements.visitConfirmation.classList.add("is-hidden");
  elements.investigationForm.classList.remove("is-hidden");
});

elements.confirmVisit.addEventListener("click", async () => {
  if (!state.activeCustomerId || !state.pendingVisit) return;
  elements.confirmVisit.disabled = true;
  elements.confirmVisit.textContent = "正在保存…";
  try {
    const result = await apiRequest(
      `/api/customers/${encodeURIComponent(
        state.activeCustomerId,
      )}/visits/confirm`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          confirmation_token: state.pendingVisit.confirmation_token,
        }),
      },
    );
    state.pendingVisit = null;
    elements.visitConfirmation.classList.add("is-hidden");
    showToast(
      `接诊已保存，剩余 ${result.remaining_sessions} 次${
        result.followup_task ? "，复诊任务已创建" : ""
      }`,
    );
    await loadCustomerDetail(state.activeCustomerId);
    await loadCustomers("", true);
    await loadDashboard();
  } catch (error) {
    showToast(error instanceof Error ? error.message : "确认接诊失败");
    state.pendingVisit = null;
    elements.visitConfirmation.classList.add("is-hidden");
    await loadCustomerDetail(state.activeCustomerId);
  } finally {
    elements.confirmVisit.disabled = false;
    elements.confirmVisit.textContent = "我确认，执行并保存";
  }
});

elements.investigationList.addEventListener("click", async (event) => {
  const button = event.target.closest(".delete-visit");
  if (!button || !state.activeCustomerId) return;
  if (!window.confirm("确认删除这条接诊记录？此操作无法撤销。")) return;
  try {
    await apiRequest(
      `/api/customers/${encodeURIComponent(
        state.activeCustomerId,
      )}/investigations/${encodeURIComponent(button.dataset.investigationId)}`,
      { method: "DELETE" },
    );
    showToast("接诊记录已删除");
    await loadCustomerDetail(state.activeCustomerId);
    await loadDashboard();
  } catch (error) {
    showToast(error instanceof Error ? error.message : "删除接诊记录失败");
  }
});

state.initialWelcomeHtml = elements.messages.innerHTML;
window.addEventListener("online", () => {
  updateNetworkStatus();
  showToast("网络已恢复，本地资料和客户功能不受影响");
});
window.addEventListener("offline", updateNetworkStatus);
updateNetworkStatus();
if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/service-worker.js").catch(() => {
      // The application remains usable online if service worker registration fails.
    });
  });
}

elements.staffLoginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  elements.staffLoginError.textContent = "";
  const data = Object.fromEntries(new FormData(elements.staffLoginForm));
  try {
    await apiRequest("/api/staff/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    window.location.reload();
  } catch (error) {
    elements.staffLoginError.textContent =
      error instanceof Error ? error.message : "登录失败";
  }
});

async function bootstrapApp() {
  loadHealth();
  try {
    const session = await apiRequest("/api/staff/session");
    applyStaffSession(session);
    if (session.auth_required && !session.authenticated) {
      showStaffLogin();
      return;
    }
  } catch {
    showStaffLogin();
    return;
  }
  await loadCustomers("", true);
  if (state.activeCustomerId) {
    await loadCustomerDetail(state.activeCustomerId);
  }
  const requestedView = new URLSearchParams(window.location.search).get("view");
  showView(requestedView === "appointments" ? "appointments" : "dashboard");
}

bootstrapApp();

