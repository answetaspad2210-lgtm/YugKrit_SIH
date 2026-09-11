/* YugKrit - main.js: shared UI behavior used across every page */

document.addEventListener("DOMContentLoaded", function () {
  initSidebarToggle();
  initDropdowns();
  initFlashToasts();
  initModalTriggers();
  initTabs();
  initHeroSlideshow();
  initPasswordToggles();
  initMultiSelects();
  initIndustrySubsectors();
});

function initPasswordToggles() {
  document.querySelectorAll('input[type="password"]').forEach((input) => {
    if (input.closest(".password-field")) return;
    const wrapper = document.createElement("div");
    wrapper.className = "password-field";
    input.parentNode.insertBefore(wrapper, input);
    wrapper.appendChild(input);
    const button = document.createElement("button");
    button.type = "button";
    button.className = "password-toggle";
    button.setAttribute("aria-label", "Show password");
    button.setAttribute("data-password-toggle", "");
    button.innerHTML = '<i class="fa-solid fa-eye"></i>';
    wrapper.appendChild(button);
  });
  document.querySelectorAll("[data-password-toggle]").forEach((button) => {
    button.addEventListener("click", () => {
      const input = button.parentElement.querySelector("input");
      if (!input) return;
      const visible = input.type === "text";
      input.type = visible ? "password" : "text";
      button.setAttribute("aria-label", visible ? "Show password" : "Hide password");
      const icon = button.querySelector("i");
      if (icon) icon.className = visible ? "fa-solid fa-eye" : "fa-solid fa-eye-slash";
    });
  });
}

function initMultiSelects() {
  document.querySelectorAll("[data-multi-select]").forEach((wrapper) => {
    const search = wrapper.querySelector(".multi-select-search");
    const select = wrapper.querySelector("[data-chip-select]");
    const chips = wrapper.querySelector(".selected-chips");
    if (!select || !chips) return;

    function render() {
      chips.innerHTML = "";
      Array.from(select.selectedOptions).forEach((option) => {
        const chip = document.createElement("span");
        chip.className = "selection-chip";
        chip.textContent = option.text;
        const remove = document.createElement("button");
        remove.type = "button";
        remove.setAttribute("aria-label", `Remove ${option.text}`);
        remove.innerHTML = "&times;";
        remove.addEventListener("click", () => {
          option.selected = false;
          render();
        });
        chip.appendChild(remove);
        chips.appendChild(chip);
      });
    }

    // Make each mouse click toggle one option without requiring Ctrl/Cmd.
    select.addEventListener("mousedown", (event) => {
      const option = event.target.closest("option");
      if (!option) return;
      event.preventDefault();
      select.focus();
      option.selected = !option.selected;
      select.dispatchEvent(new Event("change", { bubbles: true }));
    });
    select.addEventListener("change", render);
    if (search) {
      search.addEventListener("input", () => {
        const query = search.value.toLowerCase();
        Array.from(select.options).forEach((option) => {
          option.hidden = Boolean(query) && !option.text.toLowerCase().includes(query);
        });
      });
    }
    render();
  });
}

function initIndustrySubsectors() {
  const sector = document.querySelector("[data-sector-select]");
  const subsector = document.querySelector("[data-subsector-select]");
  if (!sector || !subsector || !window.industrySubsectors) return;
  function render() {
    const values = window.industrySubsectors[sector.value] || [];
    subsector.innerHTML = '<option value="">Select sub-sector</option>';
    values.forEach((value) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = value;
      subsector.appendChild(option);
    });
  }
  sector.addEventListener("change", render);
  render();
}

function initHeroSlideshow() {
  const slideshow = document.querySelector("[data-slideshow]");
  if (!slideshow) return;
  const slides = [...slideshow.querySelectorAll("[data-slide]")];
  if (slides.length < 2) return;
  let current = 0;
  let timer;

  function show(index) {
    current = (index + slides.length) % slides.length;
    slides.forEach((slide, i) => {
      const active = i === current;
      slide.classList.toggle("is-active", active);
      slide.setAttribute("aria-hidden", String(!active));
    });
  }

  function restart() {
    window.clearInterval(timer);
    timer = window.setInterval(() => show(current + 1), 3000);
  }

  current = slides.findIndex((slide) => slide.classList.contains("is-active"));
  show(current >= 0 ? current : 0);
  restart();
}

function initSidebarToggle() {
  const hamburger = document.querySelector(".hamburger");
  const sidebar = document.querySelector(".sidebar");
  const overlay = document.querySelector(".sidebar-overlay");
  if (!hamburger || !sidebar) return;

  function open() {
    sidebar.classList.add("open");
    overlay && overlay.classList.add("open");
  }
  function close() {
    sidebar.classList.remove("open");
    overlay && overlay.classList.remove("open");
  }
  hamburger.addEventListener("click", () => {
    sidebar.classList.contains("open") ? close() : open();
  });
  overlay && overlay.addEventListener("click", close);
}

function initDropdowns() {
  document.querySelectorAll("[data-dropdown-toggle]").forEach((btn) => {
    const targetId = btn.getAttribute("data-dropdown-toggle");
    const menu = document.getElementById(targetId);
    if (!menu) return;
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      document.querySelectorAll(".dropdown-menu.open").forEach((m) => {
        if (m !== menu) m.classList.remove("open");
      });
      menu.classList.toggle("open");
    });
  });
  document.addEventListener("click", (e) => {
    document.querySelectorAll(".dropdown-menu.open").forEach((m) => {
      if (!m.contains(e.target)) m.classList.remove("open");
    });
  });
}

function initFlashToasts() {
  document.querySelectorAll(".toast").forEach((toast) => {
    setTimeout(() => {
      toast.style.transition = "opacity .3s ease";
      toast.style.opacity = "0";
      setTimeout(() => toast.remove(), 300);
    }, 5000);
  });
}

function initModalTriggers() {
  document.querySelectorAll("[data-modal-open]").forEach((btn) => {
    const id = btn.getAttribute("data-modal-open");
    btn.addEventListener("click", () => {
      const modal = document.getElementById(id);
      if (modal) modal.classList.add("open");
    });
  });
  document.querySelectorAll("[data-modal-close]").forEach((btn) => {
    btn.addEventListener("click", () => {
      btn.closest(".modal-backdrop").classList.remove("open");
    });
  });
  document.querySelectorAll(".modal-backdrop").forEach((backdrop) => {
    backdrop.addEventListener("click", (e) => {
      if (e.target === backdrop) backdrop.classList.remove("open");
    });
  });
}

function initTabs() {
  document.querySelectorAll("[data-tabs]").forEach((tabGroup) => {
    const links = tabGroup.querySelectorAll(".tab-link");
    links.forEach((link) => {
      link.addEventListener("click", (e) => {
        if (link.hasAttribute("href") && link.getAttribute("href").startsWith("?")) {
          return; // server-rendered tab navigation, let it navigate
        }
        e.preventDefault();
        const targetSelector = link.getAttribute("data-tab-target");
        links.forEach((l) => l.classList.remove("active"));
        link.classList.add("active");
        document.querySelectorAll(targetSelector ? `[data-tab-panel]` : null).forEach(() => {});
        if (targetSelector) {
          document.querySelectorAll("[data-tab-panel]").forEach((panel) => {
            panel.style.display = panel.id === targetSelector.replace("#", "") ? "block" : "none";
          });
        }
      });
    });
  });
}

function showToast(message, type) {
  const container = document.querySelector(".flash-container") || (() => {
    const c = document.createElement("div");
    c.className = "flash-container";
    document.body.appendChild(c);
    return c;
  })();
  const toast = document.createElement("div");
  toast.className = `toast ${type || "info"}`;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 5000);
}
