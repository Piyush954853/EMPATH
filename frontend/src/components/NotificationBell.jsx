import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import "./NotificationBell.css";

const API_URL = "http://127.0.0.1:8000";
const MAX_VISIBLE_NOTIFICATIONS = 12;

function storageKeyFor(user) {
  const userId = user?.id ?? user?.user_id ?? user?.username ?? "current-user";
  return `empath_notification_read_ids_${String(userId)}`;
}

function readIdsFromStorage(key) {
  try {
    const value = JSON.parse(localStorage.getItem(key) || "[]");
    return Array.isArray(value) ? value.map(String) : [];
  } catch {
    return [];
  }
}

function alertTime(value) {
  if (!value) return "Time unavailable";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Time unavailable";

  const seconds = Math.max(0, Math.floor((Date.now() - date.getTime()) / 1000));
  if (seconds < 30) return "Just now";
  if (seconds < 60 * 60) return `${Math.floor(seconds / 60)} min ago`;
  if (seconds < 24 * 60 * 60) return `${Math.floor(seconds / 3600)} hr ago`;
  return date.toLocaleString();
}

function priorityClass(priority) {
  const value = String(priority || "low").toLowerCase();
  if (["critical", "high", "medium", "low"].includes(value)) return value;
  return "low";
}

export default function NotificationBell({ token, user, onOpenAlert }) {
  const storageKey = useMemo(() => storageKeyFor(user), [user?.id, user?.user_id, user?.username]);
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [isOpen, setIsOpen] = useState(false);
  const [readIds, setReadIds] = useState(() => readIdsFromStorage(storageKey));
  const rootRef = useRef(null);

  const loadAlerts = useCallback(async () => {
    if (!token) {
      setAlerts([]);
      setLoading(false);
      return;
    }

    try {
      const response = await fetch(`${API_URL}/alerts`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      let data = null;
      try {
        data = await response.json();
      } catch {
        data = null;
      }

      if (!response.ok) {
        throw new Error(data?.detail || data?.message || `Request failed (${response.status})`);
      }

      const accessibleAlerts = Array.isArray(data) ? data : [];
      const actionableAlerts = accessibleAlerts
        .filter((alert) => alert && (alert.status === "active" || alert.status === "acknowledged"))
        .sort((a, b) => new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime());

      setAlerts(actionableAlerts);
      setError("");
    } catch (fetchError) {
      console.error("EMPATH notification refresh failed:", fetchError);
      setError(fetchError instanceof Error ? fetchError.message : "Unable to load notifications.");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    setReadIds(readIdsFromStorage(storageKey));
  }, [storageKey]);

  useEffect(() => {
    if (!token) return undefined;

    loadAlerts();
    const intervalId = window.setInterval(() => {
      loadAlerts();
    }, 5000);

    return () => window.clearInterval(intervalId);
  }, [token, loadAlerts]);

  useEffect(() => {
    const handleOutsideClick = (event) => {
      if (rootRef.current && !rootRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };

    const handleEscape = (event) => {
      if (event.key === "Escape") setIsOpen(false);
    };

    document.addEventListener("mousedown", handleOutsideClick);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handleOutsideClick);
      document.removeEventListener("keydown", handleEscape);
    };
  }, []);

  const readIdSet = useMemo(() => new Set(readIds.map(String)), [readIds]);
  const unreadCount = alerts.reduce((count, alert) => count + (readIdSet.has(String(alert.id)) ? 0 : 1), 0);
  const visibleAlerts = alerts.slice(0, MAX_VISIBLE_NOTIFICATIONS);

  const markAsRead = useCallback((alertId) => {
    const id = String(alertId);
    if (readIds.includes(id)) return;
    const next = [...readIds, id].slice(-500);
    setReadIds(next);
    try {
      localStorage.setItem(storageKey, JSON.stringify(next));
    } catch (storageError) {
      console.warn("Could not save EMPATH notification read state:", storageError);
    }
  }, [storageKey, readIds]);

  const markAllAsRead = () => {
    const next = [...new Set([...readIds, ...alerts.map((alert) => String(alert.id))])].slice(-500);
    setReadIds(next);
    try {
      localStorage.setItem(storageKey, JSON.stringify(next));
    } catch (storageError) {
      console.warn("Could not save EMPATH notification read state:", storageError);
    }
  };

  const handleAlertClick = (alert) => {
    markAsRead(alert.id);
    setIsOpen(false);
    if (typeof onOpenAlert === "function") onOpenAlert(alert);
  };

  return (
    <div className="empath-notification-root" ref={rootRef}>
      <button
        className="empath-notification-trigger"
        type="button"
        onClick={() => setIsOpen((current) => !current)}
        aria-label={unreadCount > 0 ? `Notifications, ${unreadCount} unread alerts` : "Notifications"}
        aria-expanded={isOpen}
        aria-haspopup="dialog"
        title="Notifications"
      >
        <svg viewBox="0 0 24 24" aria-hidden="true" className="empath-bell-icon">
          <path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" />
          <path d="M10 21h4" />
        </svg>
        {unreadCount > 0 && (
          <span className="empath-notification-count">
            {unreadCount > 99 ? "99+" : unreadCount}
          </span>
        )}
      </button>

      {isOpen && (
        <section className="empath-notification-panel" role="dialog" aria-label="Alert notifications">
          <div className="empath-notification-panel-header">
            <div>
              <h2>Notifications</h2>
              <p>Active safety alerts available to your account</p>
            </div>
            <button
              type="button"
              className="empath-notification-close"
              onClick={() => setIsOpen(false)}
              aria-label="Close notifications"
            >
              ×
            </button>
          </div>

          {unreadCount > 0 && (
            <div className="empath-notification-toolbar">
              <span>{unreadCount} unread</span>
              <button type="button" onClick={markAllAsRead}>Mark all as read</button>
            </div>
          )}

          {loading ? (
            <div className="empath-notification-state">Loading alerts…</div>
          ) : error && alerts.length === 0 ? (
            <div className="empath-notification-state empath-notification-error">
              Notifications could not be loaded. {error}
              <button type="button" onClick={loadAlerts}>Try again</button>
            </div>
          ) : visibleAlerts.length === 0 ? (
            <div className="empath-notification-state">
              <span className="empath-notification-empty-icon">✓</span>
              <strong>You’re all caught up</strong>
              <span>No active or acknowledged alerts right now.</span>
            </div>
          ) : (
            <div className="empath-notification-list">
              {visibleAlerts.map((alert) => {
                const isRead = readIdSet.has(String(alert.id));
                return (
                  <button
                    type="button"
                    className={`empath-notification-item${isRead ? " is-read" : " is-unread"}`}
                    key={alert.id}
                    onClick={() => handleAlertClick(alert)}
                  >
                    <span className={`empath-notification-severity ${priorityClass(alert.priority)}`} />
                    <span className="empath-notification-item-body">
                      <span className="empath-notification-item-heading">
                        <strong>{alert.title || `Safety alert #${alert.id}`}</strong>
                        {!isRead && <span className="empath-notification-unread-dot" aria-label="Unread" />}
                      </span>
                      <span className="empath-notification-message">
                        {alert.message || "Staff review is required."}
                      </span>
                      <span className="empath-notification-item-meta">
                        <span className={`empath-notification-priority ${priorityClass(alert.priority)}`}>
                          {String(alert.priority || "low").toUpperCase()}
                        </span>
                        <span>Alert #{alert.id}</span>
                        {alert.event_id != null && <span>Event #{alert.event_id}</span>}
                        <span>{alertTime(alert.created_at)}</span>
                      </span>
                    </span>
                    <svg className="empath-notification-arrow" viewBox="0 0 24 24" aria-hidden="true">
                      <path d="m9 18 6-6-6-6" />
                    </svg>
                  </button>
                );
              })}
            </div>
          )}

          {alerts.length > MAX_VISIBLE_NOTIFICATIONS && (
            <div className="empath-notification-footer">
              Showing the latest {MAX_VISIBLE_NOTIFICATIONS} active alerts.
            </div>
          )}
          <div className="empath-notification-panel-footer">
            Refreshes automatically every 5 seconds
          </div>
        </section>
      )}
    </div>
  );
}
