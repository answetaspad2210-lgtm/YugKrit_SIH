/* YugKrit - notifications.js: database-backed notification bell behavior */

document.addEventListener("DOMContentLoaded", function () {
  const bell = document.getElementById("notif-bell");
  const menu = document.getElementById("notif-menu");
  const badge = document.getElementById("notif-badge");
  const list = document.getElementById("notification-list");
  const markAllReadBtn = document.getElementById("mark-all-read-btn");

  if (!bell || !menu) return;

  const formatTime = (value) => {
    if (!value) return "Just now";
    try {
      const date = new Date(value);
      return new Intl.DateTimeFormat("en-IN", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }).format(date);
    } catch (error) {
      return "Just now";
    }
  };

  const renderList = (items) => {
    if (!list) return;
    if (!items || items.length === 0) {
      list.innerHTML = '<div class="dropdown-item"><div class="item-title">No new notifications</div><div>You\'re all caught up.</div></div>';
      return;
    }

    list.innerHTML = items.map((item) => `
      <a class="dropdown-item ${item.is_read ? '' : 'unread'}" href="${item.link || '#'}" data-notification-id="${item.id}" data-read-state="${item.is_read}">
        <div class="item-title">${item.title}</div>
        <div>${item.message}</div>
        <div class="item-time">${formatTime(item.created_at)}</div>
      </a>
    `).join("");

    list.querySelectorAll("[data-notification-id]").forEach((link) => {
      link.addEventListener("click", async (event) => {
        const id = Number(link.getAttribute("data-notification-id"));
        const isRead = link.getAttribute("data-read-state") === "true";
        if (!id || isRead) return;
        event.preventDefault();
        try {
          const response = await fetch(`/api/notifications/${id}/read`, { method: "POST", headers: { "Accept": "application/json" } });
          if (response.ok) {
            link.setAttribute("data-read-state", "true");
            link.classList.remove("unread");
            refreshBadge();
            if (link.getAttribute("href") && link.getAttribute("href") !== "#") {
              window.location.href = link.getAttribute("href");
            }
          }
        } catch (error) {
          console.error("Failed to mark notification as read", error);
        }
      });
    });
  };

  const refreshBadge = async () => {
    if (!badge) return;
    try {
      const response = await fetch("/api/notifications/unread-count", { headers: { "Accept": "application/json" } });
      if (!response.ok) return;
      const payload = await response.json();
      const count = Number(payload?.data?.count || 0);
      if (count > 0) {
        badge.hidden = false;
        badge.textContent = count > 99 ? "99+" : String(count);
      } else {
        badge.hidden = true;
        badge.textContent = "0";
      }
    } catch (error) {
      console.error("Unable to refresh notification count", error);
    }
  };

  const refreshNotifications = async () => {
    if (!list) return;
    try {
      const response = await fetch("/api/notifications?limit=8", { headers: { "Accept": "application/json" } });
      if (!response.ok) {
        list.innerHTML = '<div class="dropdown-item"><div class="item-title">Unable to load notifications</div><div>Please try again.</div></div>';
        return;
      }
      const payload = await response.json();
      renderList(payload?.data || []);
      await refreshBadge();
    } catch (error) {
      list.innerHTML = '<div class="dropdown-item"><div class="item-title">Unable to load notifications</div><div>Please try again.</div></div>';
    }
  };

  bell.addEventListener("click", async () => {
    menu.classList.toggle("open");
    if (menu.classList.contains("open")) {
      await refreshNotifications();
    }
  });

  markAllReadBtn?.addEventListener("click", async () => {
    try {
      await fetch("/api/notifications/read-all", { method: "POST", headers: { "Accept": "application/json" } });
      await refreshNotifications();
      await refreshBadge();
    } catch (error) {
      console.error("Failed to mark all notifications as read", error);
    }
  });

  refreshBadge();
  refreshNotifications();
  window.setInterval(refreshBadge, 30000);
});
