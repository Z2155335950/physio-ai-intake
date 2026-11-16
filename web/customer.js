const state = {};

const elements = {
  authView: document.querySelector("#auth-view"),
  portalView: document.querySelector("#portal-view"),
  loginTab: document.querySelector("#login-tab"),
  registerTab: document.querySelector("#register-tab"),
  resetTab: document.querySelector("#reset-tab"),
  loginForm: document.querySelector("#login-form"),
  registerForm: document.querySelector("#register-form"),
  resetForm: document.querySelector("#reset-form"),
  privacyLoading: document.querySelector("#privacy-loading"),
  privacyContent: document.querySelector("#privacy-content"),
  privacyPurpose: document.querySelector("#privacy-purpose"),
  privacyRetention: document.querySelector("#privacy-retention"),
  privacyDeletionRule: document.querySelector("#privacy-deletion-rule"),
  privacyContact: document.querySelector("#privacy-contact"),
  privacyVersion: document.querySelector("#privacy-version"),
  privacyConsent: document.querySelector("#privacy-consent"),
  authError: document.querySelector("#auth-error"),
  portalName: document.querySelector("#portal-name"),
  portalPhone: document.querySelector("#portal-phone"),
  portalRemaining: document.querySelector("#portal-remaining"),
  portalCourse: document.querySelector("#portal-course"),
  portalAppointments: document.querySelector("#portal-appointments"),
  portalFollowups: document.querySelector("#portal-followups"),
  portalVisits: document.querySelector("#portal-visits"),
  scheduleDate: document.querySelector("#portal-schedule-date"),
  scheduleList: document.querySelector("#portal-schedule"),
  portalHandoutDetails: document.querySelector("#portal-handout-details"),
  portalHandoutLoading: document.querySelector("#portal-handout-loading"),
  portalHandoutContent: document.querySelector("#portal-handout-content"),
  portalLogout: document.querySelector("#portal-logout"),
  portalAccountStatus: document.querySelector("#portal-account-status"),
  portalPasswordForm: document.querySelector("#portal-password-form"),
  portalUnbindForm: document.querySelector("#portal-unbind-form"),
  portalDeletionForm: document.querySelector("#portal-deletion-form"),
  toast: document.querySelector("#portal-toast"),
};

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function showToast(message) {
  elements.toast.textContent = message;
  elements.toast.classList.add("show");
  window.clearTimeout(showToast.timeout);
  showToast.timeout = window.setTimeout(
    () => elements.toast.classList.remove("show"),
    3500,
  );
}

async function request(url, options = {}) {
  const response = await fetch(url, options);
  if (response.status === 204) return null;
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || `请求失败（${response.status}）`);
  }
  return payload;
}

function switchAuth(tab) {
  const login = tab === "login";
  const register = tab === "register";
  const reset = tab === "reset";
  elements.loginTab.classList.toggle("active", login);
  elements.registerTab.classList.toggle("active", register);
  elements.resetTab.classList.toggle("active", reset);
  elements.loginForm.classList.toggle("is-hidden", !login);
  elements.registerForm.classList.toggle("is-hidden", !register);
  elements.resetForm.classList.toggle("is-hidden", !reset);
  elements.authError.textContent = "";
}

async function loadPrivacyPolicy() {
  const submit = elements.registerForm.querySelector('[type="submit"]');
  elements.privacyConsent.disabled = true;
  submit.disabled = true;
  try {
    const policy = await request("/api/portal/privacy-policy");
    elements.privacyPurpose.textContent = policy.purpose;
    elements.privacyRetention.textContent = policy.retention;
    elements.privacyDeletionRule.textContent = policy.deletion_rule;
    elements.privacyContact.textContent = policy.contact || "尚未配置";
    elements.privacyVersion.textContent = `隐私说明版本：${policy.version}`;
    elements.privacyLoading.classList.add("is-hidden");
    elements.privacyContent.classList.remove("is-hidden");
    elements.privacyConsent.disabled = !policy.registration_enabled;
    submit.disabled = !policy.registration_enabled;
    if (!policy.registration_enabled) {
      elements.authError.textContent =
        policy.unavailable_reason || "当前暂不能注册顾客账号";
    }
  } catch (error) {
    elements.privacyLoading.textContent = `隐私说明加载失败：${error.message}`;
  }
}

function empty(message) {
  return `<div class="portal-empty">${escapeHtml(message)}</div>`;
}

function localDateValue() {
  const now = new Date();
  const offset = now.getTimezoneOffset();
  return new Date(now.getTime() - offset * 60000)
    .toISOString()
    .slice(0, 10);
}

function formatPortalTime(value) {
  return new Date(value).toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

async function loadPortalSchedule() {
  const scheduleDate = elements.scheduleDate.value;
  if (!scheduleDate) return;
  elements.scheduleList.innerHTML =
    '<div class="portal-empty">正在读取理疗师日程…</div>';
  try {
    const schedule = await request(
      `/api/portal/schedule?schedule_date=${encodeURIComponent(scheduleDate)}`,
    );
    if (!schedule.slots.length) {
      elements.scheduleList.innerHTML = empty("当天理疗师尚未开放预约时段");
      return;
    }
    elements.scheduleList.innerHTML = schedule.slots
      .map((slot) => {
        const own = slot.is_own ? " own" : "";
        const label = slot.is_own
          ? "您的预约"
          : slot.status === "available"
            ? "可预约"
            : slot.status === "booked"
              ? "已预约"
              : slot.status === "completed"
                ? "已完成"
              : "不可预约";
        return `
          <div class="portal-slot ${slot.status}${own}">
            <strong>${escapeHtml(formatPortalTime(slot.start_at))}–${escapeHtml(
              formatPortalTime(slot.end_at),
            )}</strong>
            <span>${escapeHtml(label)}</span>
          </div>
        `;
      })
      .join("");
  } catch (error) {
    elements.scheduleList.innerHTML = empty(error.message);
  }
}

function renderPortal(data) {
  state.data = data;
  elements.authView.classList.add("is-hidden");
  elements.portalView.classList.remove("is-hidden");
  elements.portalName.textContent = `${data.customer_name}，您好，祝您早日康复`;
  elements.portalPhone.textContent = `登记手机：${data.phone_masked}`;
  elements.portalRemaining.textContent = String(data.remaining_sessions);
  elements.portalCourse.textContent = data.selected_course || "未选择疗程";
  elements.portalAccountStatus.textContent =
    data.latest_deletion_request_status === "pending"
      ? "资料删除申请已提交，等待理疗师处理"
      : data.latest_deletion_request_status === "rejected"
        ? "上次资料删除申请未获同意，可联系门店了解原因"
        : "修改密码、解绑或申请删除资料";

  elements.portalAppointments.innerHTML = data.appointments.length
    ? data.appointments
        .map(
          (item) => `
            <article class="portal-card">
              <strong>${escapeHtml(
                new Date(item.scheduled_at).toLocaleString("zh-CN", {
                  month: "2-digit",
                  day: "2-digit",
                  hour: "2-digit",
                  minute: "2-digit",
                  hour12: false,
                }),
              )}</strong>
              <p>${escapeHtml(item.service_item || "门店养护服务")} · ${
                item.status === "scheduled"
                  ? "已预约"
                  : item.status === "completed"
                    ? "已完成"
                    : escapeHtml(item.status)
              }</p>
              ${item.note ? `<p>${escapeHtml(item.note)}</p>` : ""}
            </article>
          `,
        )
        .join("")
    : empty("暂无预约安排");

  elements.portalFollowups.innerHTML = data.followups.length
    ? data.followups
        .map(
          (item) => `
            <article class="portal-card">
              <strong>${escapeHtml(item.due_date)}</strong>
              <p>${escapeHtml(item.note || "请按约回复门店")}</p>
            </article>
          `,
        )
        .join("")
    : empty("暂无待复诊安排");

  elements.portalVisits.innerHTML = data.recent_visits.length
    ? data.recent_visits
        .map(
          (item) => `
            <details class="portal-visit">
              <summary>
                <strong>${escapeHtml(item.visit_date)}</strong>
                <span>${escapeHtml(item.chief_complaint)}</span>
              </summary>
              <div class="portal-visit-body">
                <div>
                  <small>本次类型</small>
                  <p>${escapeHtml(item.visit_type)} · 使用 ${escapeHtml(
                    item.sessions_used,
                  )} 次</p>
                </div>
                <div>
                  <small>本次反馈</small>
                  <p>${escapeHtml(item.chief_complaint)}</p>
                </div>
                <div>
                  <small>养护建议</small>
                  <p>${escapeHtml(item.care_plan || "请按门店现场告知执行")}</p>
                </div>
              </div>
            </details>
          `,
        )
        .join("")
    : empty("暂无接诊摘要");

  if (!elements.scheduleDate.value) {
    elements.scheduleDate.value = localDateValue();
  }
  loadPortalSchedule();
}

async function loadPortal() {
  try {
    const data = await request("/api/portal/me");
    renderPortal(data);
  } catch {
    elements.portalView.classList.add("is-hidden");
    elements.authView.classList.remove("is-hidden");
  }
}

elements.loginTab.addEventListener("click", () => switchAuth("login"));
elements.registerTab.addEventListener("click", () => switchAuth("register"));
elements.resetTab.addEventListener("click", () => switchAuth("reset"));

elements.loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  elements.authError.textContent = "";
  const data = Object.fromEntries(new FormData(elements.loginForm));
  try {
    await request("/api/portal/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    await loadPortal();
  } catch (error) {
    elements.authError.textContent = error.message;
  }
});

elements.registerForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  elements.authError.textContent = "";
  const data = Object.fromEntries(new FormData(elements.registerForm));
  if (!elements.privacyConsent.checked) {
    elements.authError.textContent = "请先阅读并同意个人信息处理说明";
    return;
  }
  data.privacy_consent = true;
  try {
    await request("/api/portal/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    await loadPortal();
  } catch (error) {
    elements.authError.textContent = error.message;
  }
});

elements.resetForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  elements.authError.textContent = "";
  const data = Object.fromEntries(new FormData(elements.resetForm));
  const phone = data.phone;
  try {
    await request("/api/portal/password/reset", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    elements.resetForm.reset();
    switchAuth("login");
    elements.loginForm.elements.phone.value = phone;
    elements.loginForm.elements.password.focus();
    showToast("密码已重置，请使用新密码登录");
  } catch (error) {
    elements.authError.textContent = error.message;
  }
});

elements.portalLogout.addEventListener("click", async () => {
  await request("/api/portal/logout", { method: "POST" }).catch(() => {});
  window.location.reload();
});

elements.portalPasswordForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const submit = elements.portalPasswordForm.querySelector('[type="submit"]');
  submit.disabled = true;
  try {
    const data = Object.fromEntries(
      new FormData(elements.portalPasswordForm),
    );
    await request("/api/portal/password/change", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    elements.portalPasswordForm.reset();
    showToast("密码已修改，其他设备上的登录已退出");
  } catch (error) {
    showToast(error.message);
  } finally {
    submit.disabled = false;
  }
});

elements.portalUnbindForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (
    !window.confirm(
      "确认解绑顾客网页账号？账号会立即退出，但门店接诊档案仍会保留。之后需要理疗师重新生成邀请码才能绑定。",
    )
  ) {
    return;
  }
  const submit = elements.portalUnbindForm.querySelector('[type="submit"]');
  submit.disabled = true;
  try {
    const data = Object.fromEntries(
      new FormData(elements.portalUnbindForm),
    );
    await request("/api/portal/unbind", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    window.location.reload();
  } catch (error) {
    showToast(error.message);
    submit.disabled = false;
  }
});

elements.portalDeletionForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (
    !window.confirm(
      "确认申请删除个人资料？理疗师同意后会清除网页账号、接诊、预约、复诊、养护说明和客户身份资料，且无法撤销。",
    )
  ) {
    return;
  }
  const submit = elements.portalDeletionForm.querySelector('[type="submit"]');
  submit.disabled = true;
  try {
    const data = Object.fromEntries(
      new FormData(elements.portalDeletionForm),
    );
    await request("/api/portal/data-deletion-requests", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    elements.portalDeletionForm.reset();
    elements.portalAccountStatus.textContent =
      "资料删除申请已提交，等待理疗师处理";
    showToast("删除申请已提交，请等待理疗师核验");
  } catch (error) {
    showToast(error.message);
  } finally {
    submit.disabled = false;
  }
});

elements.scheduleDate.addEventListener("change", loadPortalSchedule);

elements.portalHandoutDetails.addEventListener("toggle", async () => {
  if (!elements.portalHandoutDetails.open || state.handoutLoaded) return;
  try {
    const draft = await request("/api/portal/handout");
    elements.portalHandoutContent.textContent = draft.content;
    elements.portalHandoutLoading.classList.add("is-hidden");
    state.handoutLoaded = true;
  } catch (error) {
    elements.portalHandoutLoading.textContent = "读取失败，请稍后重试";
    showToast(error.message);
  }
});

loadPrivacyPolicy();
loadPortal();

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/service-worker.js?v=6").catch(() => {});
  });
}
