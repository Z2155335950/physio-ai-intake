(() => {
  const body = document.body;
  const menuButton = document.querySelector("#mobile-menu-button");
  const closeButton = document.querySelector("#mobile-nav-close");
  const scrim = document.querySelector("#mobile-nav-scrim");
  const desktopSwitch = document.querySelector("#mobile-desktop-switch");
  const sidebar = document.querySelector(".sidebar");

  if (!menuButton || !closeButton || !scrim || !sidebar) return;

  const setMenuOpen = (open) => {
    body.classList.toggle("mobile-menu-open", open);
    menuButton.setAttribute("aria-expanded", String(open));
    sidebar.setAttribute("aria-hidden", String(!open));
  };

  menuButton.addEventListener("click", () => {
    setMenuOpen(!body.classList.contains("mobile-menu-open"));
  });
  closeButton.addEventListener("click", () => setMenuOpen(false));
  scrim.addEventListener("click", () => setMenuOpen(false));

  document
    .querySelectorAll(
      "#open-dashboard, #open-pdf-intake, #open-appointment-management, #open-backups, #open-portal-admin, #open-staff-management, #staff-logout",
    )
    .forEach((button) => {
      button.addEventListener("click", () => setMenuOpen(false));
    });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") setMenuOpen(false);
  });

  desktopSwitch?.addEventListener("click", () => {
    window.location.replace("/?view=desktop");
  });

  window.matchMedia("(min-width: 901px)").addEventListener("change", (event) => {
    if (event.matches) setMenuOpen(false);
  });

  setMenuOpen(false);
})();
