/* =========================================================
   Library Management System — Main JS
   Responsibilities:
   - Confirm dialogs for destructive actions
   - Live table search/filter
   - Tab navigation (librarian dashboard)
   ========================================================= */

"use strict";

// ---------------------------------------------------------------------------
// Confirm dialogs — data-confirm attribute on forms
// ---------------------------------------------------------------------------
document.addEventListener("submit", (e) => {
  const msg = e.target.dataset.confirm;
  if (msg && !window.confirm(msg)) {
    e.preventDefault();
  }
});

// ---------------------------------------------------------------------------
// Live table search
// Filter rows whose cells include the search term (case-insensitive).
// Usage: <input data-filter-target="#myTable">
// ---------------------------------------------------------------------------
document.querySelectorAll("[data-filter-target]").forEach((input) => {
  const targetSelector = input.dataset.filterTarget;
  const table = document.querySelector(targetSelector);
  if (!table) return;

  input.addEventListener("input", () => {
    const term = input.value.trim().toLowerCase();
    table.querySelectorAll("tbody tr:not(.empty-row)").forEach((row) => {
      const text = row.textContent.toLowerCase();
      row.style.display = term === "" || text.includes(term) ? "" : "none";
    });
  });
});

// ---------------------------------------------------------------------------
// Tab navigation (librarian dashboard)
// ---------------------------------------------------------------------------
const tabButtons = document.querySelectorAll("[data-tab]");
const tabPanels  = document.querySelectorAll("[data-panel]");

function activateTab(tabId) {
  tabButtons.forEach((btn) => {
    const active = btn.dataset.tab === tabId;
    btn.classList.toggle("tab-active", active);
    btn.setAttribute("aria-selected", active);
  });
  tabPanels.forEach((panel) => {
    panel.hidden = panel.dataset.panel !== tabId;
  });
  // Persist in sessionStorage so refresh restores the same tab
  sessionStorage.setItem("activeTab", tabId);
}

if (tabButtons.length > 0) {
  tabButtons.forEach((btn) => {
    btn.addEventListener("click", () => activateTab(btn.dataset.tab));
  });
  // Restore from session or default to first tab
  const saved = sessionStorage.getItem("activeTab");
  const first = tabButtons[0]?.dataset.tab;
  activateTab(saved && document.querySelector(`[data-tab="${saved}"]`) ? saved : first);
}

// ---------------------------------------------------------------------------
// Flash auto-dismiss after 6 seconds
// ---------------------------------------------------------------------------
setTimeout(() => {
  document.querySelectorAll(".flash").forEach((el) => {
    el.style.transition = "opacity .4s";
    el.style.opacity    = "0";
    setTimeout(() => el.remove(), 400);
  });
}, 6000);