import { useCallback, useEffect, useState } from "react";

import "./Monitoring.css";
import LiveWebcam from "./LiveWebcam";

import MultiCameraDashboard from "./MultiCameraDashboard";

const API_URL = "http://127.0.0.1:8000";

// =========================================================

// API HELPERS
// =========================================================

async function requestJson(token, path, options = {}) {
  const headers = new Headers(options.headers || {});
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
  });
  let data = null;
  try {
    data = await response.json();
  } catch {
    data = null;
  }
  if (!response.ok) {
    if (response.status === 401) {
      throw new Error("Your session may have expired. Please sign in again.");
    }
    throw new Error(
      data?.detail ||
      data?.message ||
      `Request failed (${response.status})`,
    );
  }
  return data;
}

async function fetchCameras(token) {
  const data = await requestJson(token, "/cameras");
  return Array.isArray(data) ? data : [];
}

async function fetchEvents(token) {
  const data = await requestJson(token, "/events");
  return Array.isArray(data) ? data : [];
}

async function fetchAlerts(token) {
  const data = await requestJson(token, "/alerts");
  return Array.isArray(data) ? data : [];
}

async function fetchEligibleNurses(token, alertId) {
  const data = await requestJson(
    token,
    `/alerts/${alertId}/eligible-nurses`,
  );
  return Array.isArray(data) ? data : [];
}

async function submitAlertTransfer(token, alertId, toUserId, reason) {
  return requestJson(token, `/alerts/${alertId}/transfer`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      to_user_id: Number(toUserId),
      reason: reason.trim(),
    }),
  });
}

async function fetchAlertHistory(token, alertId) {
  const data = await requestJson(
    token,
    `/alerts/${alertId}/history`,
  );
  return Array.isArray(data) ? data : [];
}

async function updateAlert(token, alertId, action) {
  return requestJson(token, `/alerts/${alertId}/${action}`, {
    method: "POST",
  });
}

async function analyzeVideo(token, file, cameraId) {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("camera_id", String(cameraId));
  return requestJson(token, "/video/analyze", {
    method: "POST",
    body: formData,
  });
}

function getErrorMessage(error, fallback) {
  return error instanceof Error ? error.message : fallback;
}

function formatTime(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "—"
    : date.toLocaleTimeString();
}
// Read AI metadata from either the parsed API field or the legacy JSON column.
// Malformed or missing metadata must never break the Monitoring dashboard.

function getEventMetadata(event) {
  const rawMetadata = event?.metadata;
  if (
    rawMetadata &&
    typeof rawMetadata === "object" &&
    !Array.isArray(rawMetadata) &&
    Object.keys(rawMetadata).length > 0
  ) {
    return rawMetadata;
  }
  const rawMetadataJson = event?.metadata_json;
  if (
    rawMetadataJson &&
    typeof rawMetadataJson === "object" &&
    !Array.isArray(rawMetadataJson)
  ) {
    return rawMetadataJson;
  }
  if (typeof rawMetadataJson !== "string" || !rawMetadataJson.trim()) {
    return {};
  }
  try {
    const parsed = JSON.parse(rawMetadataJson);
    return parsed && typeof parsed === "object" && !Array.isArray(parsed)
      ? parsed
      : {};
  } catch {
    return {};
  }
}

function formatMetadataLabel(key) {
  return String(key).replace(/_/g, " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

function formatMetadataValue(key, value) {
  if (value === null || value === undefined || value === "") return "—";
  if (["frame_received_at_utc", "timestamp_utc", "detected_at"].includes(key)) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString();
  }
  if (key === "timestamp_seconds") {
    const seconds = Number(value);
    return Number.isFinite(seconds) ? `${seconds.toFixed(2)} s` : String(value);
  }
  if (key === "ai_confidence") {
    const confidence = Number(value);
    return Number.isFinite(confidence) ? `${Math.round(confidence * 100)}%` : String(value);
  }
  if (typeof value === "object") {
    try {
      return JSON.stringify(value);
    } catch {
      return "[Unrenderable value]";
    }
  }
  return String(value);
}
// Safely render the small subset of Markdown used by incident summaries.
// No HTML is injected; summary text is rendered as ordinary React text.

function renderInlineSummaryText(text, keyPrefix) {
  const parts = String(text).split(/(\*\*[^*]+\*\*)/g);
  return parts.map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
      return (
        <strong key={`${keyPrefix}-bold-${index}`}>
          {part.slice(2, -2)}
        </strong>
      );
    }
    return part;
  });
}

function renderSummaryMarkdown(markdown) {
  const lines = String(markdown || "").split(/\r?\n/);
  const elements = [];
  let bulletItems = [];
  let listNumber = 0;
  const flushList = () => {
    if (bulletItems.length > 0) {
      elements.push(
        <ul
          key={`summary-list-${listNumber++}`}
          className="monitoring-alert-summary-list"
          style={{ margin: "0.35rem 0 0.75rem", paddingLeft: "1.25rem" }}
        >
          {bulletItems}
        </ul>,
      );
      bulletItems = [];
    }
  };
  lines.forEach((rawLine, index) => {
    const line = rawLine.trim();
    if (!line) {
      flushList();
      return;
    }
    const headingMatch = line.match(/^#{1,3}\s+(.+)$/);
    if (headingMatch) {
      flushList();
      const heading = headingMatch[1].trim();
      // The surrounding card already has the heading "AI Incident Summary".
      if (/^(incident )?summary$/i.test(heading)) return;
      elements.push(
        <h4
          key={`summary-heading-${index}`}
          className="monitoring-alert-summary-heading"
          style={{ margin: "0.65rem 0 0.35rem", fontSize: "0.92rem" }}
        >
          {renderInlineSummaryText(heading, `summary-heading-${index}`)}
        </h4>,
      );
      return;
    }
    const bulletMatch = line.match(/^[-*]\s+(.+)$/);
    if (bulletMatch) {
      bulletItems.push(
        <li
          key={`summary-bullet-${index}`}
          style={{ margin: "0.2rem 0", textAlign: "left" }}
        >
          {renderInlineSummaryText(bulletMatch[1], `summary-bullet-${index}`)}
        </li>,
      );
      return;
    }
    flushList();
    elements.push(
      <p
        key={`summary-paragraph-${index}`}
        className="monitoring-alert-summary-paragraph"
        style={{ margin: "0.45rem 0", textAlign: "left" }}
      >
        {renderInlineSummaryText(line, `summary-paragraph-${index}`)}
      </p>,
    );
  });
  flushList();
  return elements;
}

// =========================================================

// MONITORING PAGE
// =========================================================

function Monitoring({ token, focusAlertId = null, onAlertFocused }) {
  // Cameras
  const [cameras, setCameras] = useState([]);
  const [selectedCameraId, setSelectedCameraId] = useState("");
  const [cameraLoading, setCameraLoading] = useState(true);
  const [cameraError, setCameraError] = useState("");
  // Events
  const [events, setEvents] = useState([]);
  const [eventsLoading, setEventsLoading] = useState(true);
  const [eventsError, setEventsError] = useState("");
  // Alerts
  const [alerts, setAlerts] = useState([]);
  const [alertsLoading, setAlertsLoading] = useState(true);
  const [alertsError, setAlertsError] = useState("");
  const [alertActionLoadingId, setAlertActionLoadingId] = useState(null);
  const [alertActionError, setAlertActionError] = useState("");
  // Nurse-to-Nurse assignment / handoff UI state
  const [transferAlertId, setTransferAlertId] = useState(null);
  const [eligibleNurses, setEligibleNurses] = useState([]);
  const [eligibleNursesLoading, setEligibleNursesLoading] = useState(false);
  const [selectedTransferNurseId, setSelectedTransferNurseId] = useState("");
  const [transferReason, setTransferReason] = useState("");
  const [transferError, setTransferError] = useState("");
  const [transferLoadingId, setTransferLoadingId] = useState(null);
  const [transferStatusMessage, setTransferStatusMessage] = useState("");
  // Persistent handoff-history UI state
  const [historyOpenAlertId, setHistoryOpenAlertId] = useState(null);
  const [handoffHistoryByAlert, setHandoffHistoryByAlert] = useState({});
  const [historyLoadingId, setHistoryLoadingId] = useState(null);
  const [historyError, setHistoryError] = useState("");
  // Offline Demo Video Lab — kept separate from shared playback
  const [demoVideoFile, setDemoVideoFile] = useState(null);
  const [demoVideoUrl, setDemoVideoUrl] = useState("");
  const [demoVideoBusy, setDemoVideoBusy] = useState(false);
  const [demoVideoError, setDemoVideoError] = useState("");
  const [demoVideoResult, setDemoVideoResult] = useState(null);
  const selectedCamera =
    cameras.find(
      (camera) => String(camera.id) === String(selectedCameraId),
    ) || null;
  const activeAlertCount = alerts.filter(
    (alert) => alert.status === "active",
  ).length;
  // =======================================================
  // LOAD CAMERAS
  // =======================================================
  const loadCameras = useCallback(async () => {
    try {
      setCameraLoading(true);
      setCameraError("");
      const data = await fetchCameras(token);
      setCameras(data);
      setSelectedCameraId((current) => {
        const currentExists = data.some(
          (camera) => String(camera.id) === String(current),
        );
        if (currentExists) return current;
        const firstActive = data.find(
          (camera) => camera.is_active !== false,
        );
        const firstCamera = firstActive || data[0];
        return firstCamera ? String(firstCamera.id) : "";
      });
    } catch (error) {
      console.error("Monitoring camera error:", error);
      setCameraError(
        getErrorMessage(error, "Unable to load cameras."),
      );
    } finally {
      setCameraLoading(false);
    }
  }, [token]);
  // =======================================================
  // LOAD EVENTS
  // silent=true refreshes data without flashing loading states
  // =======================================================
  const loadEvents = useCallback(
    async ({ silent = false } = {}) => {
      try {
        if (!silent) setEventsLoading(true);
        setEventsError("");
        const data = await fetchEvents(token);
        setEvents(data);
      } catch (error) {
        console.error("Monitoring event error:", error);
        setEventsError(
          getErrorMessage(error, "Unable to load events."),
        );
      } finally {
        setEventsLoading(false);
      }
    },
    [token],
  );
  // =======================================================
  // LOAD ALERTS
  // =======================================================
  const loadAlerts = useCallback(
    async ({ silent = false } = {}) => {
      try {
        if (!silent) setAlertsLoading(true);
        setAlertsError("");
        const data = await fetchAlerts(token);
        setAlerts(data);
      } catch (error) {
        console.error("Monitoring alert error:", error);
        setAlertsError(
          getErrorMessage(error, "Unable to load alerts."),
        );
      } finally {
        setAlertsLoading(false);
      }
    },
    [token],
  );
  // =======================================================
  // INITIAL DATA
  // =======================================================
  useEffect(() => {
    if (!token) return;
    loadCameras();
    loadEvents();
    loadAlerts();
  }, [token, loadCameras, loadEvents, loadAlerts]);
  // =======================================================
  // PERIODIC EVENT / ALERT REFRESH
  // =======================================================
  useEffect(() => {
    if (!token) return undefined;
    const intervalId = window.setInterval(() => {
      loadEvents({ silent: true });
      loadAlerts({ silent: true });
    }, 4000);
    return () => window.clearInterval(intervalId);
  }, [token, loadEvents, loadAlerts]);
  // =======================================================
  // LOCAL DEMO VIDEO PREVIEW URL
  // =======================================================
  useEffect(() => {
    if (!demoVideoFile) {
      setDemoVideoUrl("");
      return undefined;
    }
    const objectUrl = URL.createObjectURL(demoVideoFile);
    setDemoVideoUrl(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [demoVideoFile]);
  // =======================================================
  // ALERT ACTIONS
  // =======================================================
  const handleAlertAction = async (alertId, action) => {
    try {
      setAlertActionLoadingId(alertId);
      setAlertActionError("");
      const updatedAlert = await updateAlert(
        token,
        alertId,
        action,
      );
      setAlerts((currentAlerts) =>
        currentAlerts.map((alert) =>
          alert.id === updatedAlert.id ? updatedAlert : alert,
        ),
      );
      await loadAlerts({ silent: true });
      await loadEvents({ silent: true });
    } catch (error) {
      console.error(`Alert ${action} error:`, error);
      setAlertActionError(
        getErrorMessage(error, `Unable to ${action} alert.`),
      );
    } finally {
      setAlertActionLoadingId(null);
    }
  };
  const openTransferPanel = async (alertId) => {
    if (transferAlertId === alertId) {
      setTransferAlertId(null);
      setTransferError("");
      setTransferStatusMessage("");
      return;
    }
    setTransferAlertId(alertId);
    setEligibleNurses([]);
    setSelectedTransferNurseId("");
    setTransferReason("");
    setTransferError("");
    setTransferStatusMessage("");
    setEligibleNursesLoading(true);
    try {
      const nurses = await fetchEligibleNurses(token, alertId);
      setEligibleNurses(nurses);
      if (nurses.length === 0) {
        setTransferError(
          "No other eligible Nurses were returned for this alert. Verify your Nurse role and resource assignments.",
        );
      }
    } catch (error) {
      setTransferError(
        getErrorMessage(
          error,
          "Unable to load eligible Nurses. Check your role, permissions, and resource access.",
        ),
      );
    } finally {
      setEligibleNursesLoading(false);
    }
  };
  const handleSubmitTransfer = async (event, alert) => {
    event.preventDefault();
    if (!selectedTransferNurseId) {
      setTransferError("Choose a receiving Nurse first.");
      return;
    }
    if (transferReason.trim().length < 3) {
      setTransferError("Enter a transfer reason of at least 3 characters.");
      return;
    }
    const receivingNurse = eligibleNurses.find(
      (nurse) => String(nurse.user_id) === String(selectedTransferNurseId),
    );
    setTransferLoadingId(alert.id);
    setTransferError("");
    setTransferStatusMessage("");
    try {
      const updatedAlert = await submitAlertTransfer(
        token,
        alert.id,
        selectedTransferNurseId,
        transferReason,
      );
      setAlerts((currentAlerts) =>
        currentAlerts.map((item) =>
          item.id === updatedAlert.id ? updatedAlert : item,
        ),
      );
      const actionLabel = alert.assigned_to_user_id == null ? "assigned" : "transferred";
      const recipientLabel = receivingNurse
        ? `${receivingNurse.full_name || receivingNurse.username} (user ${receivingNurse.user_id})`
        : `user ${selectedTransferNurseId}`;
      setTransferStatusMessage(
        `Alert #${alert.id} ${actionLabel} to ${recipientLabel}.`,
      );
      setTransferAlertId(null);
      setEligibleNurses([]);
      setSelectedTransferNurseId("");
      setTransferReason("");
      await loadAlerts({ silent: true });
      // Load the saved audit record after the transfer succeeds.
      setHistoryOpenAlertId(alert.id);
      setHistoryError("");
      setHistoryLoadingId(alert.id);
      try {
        const history = await fetchAlertHistory(token, alert.id);
        setHandoffHistoryByAlert((current) => ({
          ...current,
          [alert.id]: history,
        }));
      } catch (historyLoadError) {
        setHistoryError(
          getErrorMessage(historyLoadError, "Transfer succeeded, but history could not be loaded."),
        );
      } finally {
        setHistoryLoadingId(null);
      }
    } catch (error) {
      setTransferError(
        getErrorMessage(error, "Unable to transfer this alert."),
      );
    } finally {
      setTransferLoadingId(null);
    }
  };
  const toggleAlertHistory = async (alertId) => {
    if (historyOpenAlertId === alertId) {
      setHistoryOpenAlertId(null);
      setHistoryError("");
      return;
    }
    setHistoryOpenAlertId(alertId);
    setHistoryError("");
    setHistoryLoadingId(alertId);
    try {
      const history = await fetchAlertHistory(token, alertId);
      setHandoffHistoryByAlert((current) => ({
        ...current,
        [alertId]: history,
      }));
    } catch (error) {
      setHistoryError(
        getErrorMessage(error, "Unable to load transfer history."),
      );
    } finally {
      setHistoryLoadingId(null);
    }
  };
  // =======================================================
  // OFFLINE DEMO VIDEO ANALYSIS
  // KEEP THIS SEPARATE FROM SHARED PLAYBACK
  // =======================================================
  const runDemoVideoAnalysis = async () => {
    if (!demoVideoFile) {
      setDemoVideoError("Choose a video file first.");
      return;
    }
    if (!selectedCameraId) {
      setDemoVideoError(
        "Select an authorized camera before running analysis.",
      );
      return;
    }
    const allowedExtensions = [
      ".mp4",
      ".avi",
      ".mov",
      ".mkv",
      ".webm",
    ];
    const extension = demoVideoFile.name
      .slice(demoVideoFile.name.lastIndexOf("."))
      .toLowerCase();
    if (!allowedExtensions.includes(extension)) {
      setDemoVideoError(
        "Unsupported file type. Choose MP4, AVI, MOV, MKV, or WEBM.",
      );
      return;
    }
    try {
      setDemoVideoBusy(true);
      setDemoVideoError("");
      setDemoVideoResult(null);
      const result = await analyzeVideo(
        token,
        demoVideoFile,
        selectedCameraId,
      );
      setDemoVideoResult(result);
      await Promise.all([
        loadEvents({ silent: true }),
        loadAlerts({ silent: true }),
      ]);
    } catch (error) {
      console.error("Demo video analysis error:", error);
      setDemoVideoError(
        getErrorMessage(error, "Unable to analyze the video."),
      );
    } finally {
      setDemoVideoBusy(false);
    }
  };
  // =======================================================
  // SORT EVENTS AND ALERTS FOR DISPLAY
  // =======================================================
  const visibleEvents = [...events]
    .sort(
      (a, b) =>
        new Date(b.detected_at || 0).getTime() -
        new Date(a.detected_at || 0).getTime(),
    )
    .slice(0, 5);
  const actionableAlerts = [...alerts]
    .filter((alert) => alert.status === "active" || alert.status === "acknowledged")
    .sort(
      (a, b) =>
        new Date(b.created_at || 0).getTime() -
        new Date(a.created_at || 0).getTime(),
    );
  const focusedAlert = focusAlertId == null
    ? null
    : actionableAlerts.find((alert) => String(alert.id) === String(focusAlertId));
  // Put the notification's alert first so it remains visible in the five-item panel.
  const visibleAlerts = focusedAlert
    ? [focusedAlert, ...actionableAlerts.filter((alert) => String(alert.id) !== String(focusAlertId)).slice(0, 4)]
    : actionableAlerts.slice(0, 5);
  useEffect(() => {
    if (focusAlertId == null || alertsLoading) return;
    const existsAndActionable = alerts.some(
      (alert) =>
        String(alert.id) === String(focusAlertId) &&
        (alert.status === "active" || alert.status === "acknowledged"),
    );
    if (!existsAndActionable) return;
    const target = document.getElementById(`empath-alert-${focusAlertId}`);
    if (!target) return;
    target.scrollIntoView({ behavior: "smooth", block: "center" });
    target.style.boxShadow = "0 0 0 3px rgba(14, 165, 233, 0.9), 0 12px 32px rgba(14, 165, 233, 0.16)";
    target.style.borderColor = "#0ea5e9";
    window.setTimeout(() => {
      if (target.isConnected) {
        target.style.boxShadow = "";
        target.style.borderColor = "";
      }
    }, 5000);
    if (typeof onAlertFocused === "function") onAlertFocused();
  }, [focusAlertId, alertsLoading, alerts, onAlertFocused]);
  // =======================================================
  // RENDER
  // =======================================================
  return (
    <main className="monitoring-page">
      {/* PAGE HEADER */}
      <div className="monitoring-header">
        <div className="monitoring-header-content">
          <span className="monitoring-eyebrow">
            LIVE MONITORING
          </span>
          <h1>Clinical Video Intelligence</h1>
          <p>
            Monitor authorized camera resources and review experimental
            visual safety indicators requiring staff verification.
          </p>
        </div>
        <div className="monitoring-header-actions">
          <button
            type="button"
            className="monitoring-refresh-button"
            onClick={() => {
              loadCameras();
              loadEvents();
              loadAlerts();
            }}
            disabled={cameraLoading || eventsLoading || alertsLoading}
          >
            {cameraLoading || eventsLoading || alertsLoading
              ? "Refreshing..."
              : "Refresh"}
          </button>
        </div>
      </div>
      {/* SUMMARY CARDS */}
      <section className="monitoring-summary-grid">
        <div className="monitoring-summary-card">
          <span className="monitoring-summary-label">
            AUTHORIZED CAMERAS
          </span>
          <strong className="monitoring-summary-value">
            {cameraLoading ? "…" : cameras.length}
          </strong>
        </div>
        <div className="monitoring-summary-card">
          <span className="monitoring-summary-label">
            SELECTED CAMERA
          </span>
          <strong className="monitoring-summary-value">
            {selectedCamera ? selectedCamera.name : "—"}
          </strong>
        </div>
        <div className="monitoring-summary-card">
          <span className="monitoring-summary-label">
            RECENT EVENTS
          </span>
          <strong className="monitoring-summary-value">
            {events.length}
          </strong>
        </div>
      </section>
      <LiveWebcam
        token={token}
        cameras={cameras}
        selectedCameraId={selectedCameraId}
        onCameraChange={setSelectedCameraId}
        onRefreshEvents={loadEvents}
        onRefreshAlerts={loadAlerts}
      />
      <MultiCameraDashboard
        token={token}
        cameras={cameras}
        loading={cameraLoading}
      />
      {/* CLINICAL CONTEXT, RECENT EVENTS, AND ACTIVE ALERTS */}
      <section className="monitoring-workspace monitoring-workspace-panels-only">
        {/* SIDE PANELS */}
        <aside className="monitoring-side-column">
          {/* CLINICAL CONTEXT */}
          <div className="monitoring-side-card">
            <div className="monitoring-card-header compact">
              <div>
                <span className="monitoring-card-eyebrow">
                  CLINICAL CONTEXT
                </span>
                <h2>Current Resource</h2>
              </div>
            </div>
            {selectedCamera ? (
              <div className="monitoring-context">
                <div className="monitoring-context-row">
                  <span className="monitoring-context-label">
                    Camera
                  </span>
                  <span className="monitoring-context-value">
                    {selectedCamera.name}
                  </span>
                </div>
                <div className="monitoring-context-row">
                  <span className="monitoring-context-label">
                    Code
                  </span>
                  <span className="monitoring-context-value">
                    {selectedCamera.code}
                  </span>
                </div>
                <div className="monitoring-context-row">
                  <span className="monitoring-context-label">
                    Source
                  </span>
                  <span className="monitoring-context-value">
                    {selectedCamera.source_type}
                  </span>
                </div>
                <div className="monitoring-context-row">
                  <span className="monitoring-context-label">
                    Status
                  </span>
                  <span className="monitoring-context-value">
                    {selectedCamera.is_active ? "Active" : "Inactive"}
                  </span>
                </div>
                <div className="monitoring-context-row">
                  <span className="monitoring-context-label">
                    Room ID
                  </span>
                  <span className="monitoring-context-value">
                    #{selectedCamera.room_id}
                  </span>
                </div>
              </div>
            ) : (
              <div className="monitoring-empty-state">
                No authorized camera selected.
              </div>
            )}
          </div>
          {/* RECENT EVENTS */}
          <div className="monitoring-side-card">
            <div className="monitoring-card-header compact">
              <div>
                <span className="monitoring-card-eyebrow">
                  EVENT FEED
                </span>
                <h2>Recent Events</h2>
              </div>
            </div>
            {eventsLoading ? (
              <div className="monitoring-empty-state">
                Loading events...
              </div>
            ) : eventsError ? (
              <div className="monitoring-empty-state error-text">
                {eventsError}
              </div>
            ) : visibleEvents.length === 0 ? (
              <div className="monitoring-empty-state">
                No recent events.
              </div>
            ) : (
              <div className="monitoring-event-list">
                {visibleEvents.map((event) => {
                  const metadata = getEventMetadata(event);
                  const metadataEntries = Object.entries(metadata).filter(
                    ([, value]) => value !== null && value !== undefined && value !== "",
                  );
                  const hasAIContext = metadataEntries.length > 0;
                  return (
                    <div
                      className="monitoring-event-item"
                      key={event.id}
                    >
                      <div>
                        <p className="monitoring-event-title">
                          {event.event_type || "Event"}
                        </p>
                        <p className="monitoring-event-description">
                          {event.description || "No description"}
                        </p>
                        {hasAIContext && (
                          <details
                            className="monitoring-event-ai-context"
                            style={{ marginTop: "6px" }}
                          >
                            <summary
                              style={{
                                cursor: "pointer",
                                fontSize: "12px",
                              }}
                            >
                              AI Context
                              {metadata.analysis_mode
                                ? ` · ${metadata.analysis_mode}`
                                : ""}
                              {metadata.frame_number !== null && metadata.frame_number !== undefined
                                ? ` · Frame ${metadata.frame_number}`
                                : ""}
                              {metadata.timestamp_seconds !== null &&
                                metadata.timestamp_seconds !== undefined &&
                                Number.isFinite(Number(metadata.timestamp_seconds))
                                ? ` · Video ${Number(metadata.timestamp_seconds).toFixed(2)} s`
                                : ""}
                            </summary>
                            <div
                              style={{
                                marginTop: "6px",
                                fontSize: "12px",
                                lineHeight: 1.7,
                                overflowWrap: "anywhere",
                              }}
                            >
                              {metadataEntries.map(([key, value]) => (
                                <div key={key}>
                                  <strong>{formatMetadataLabel(key)}:</strong>{" "}
                                  <span>{formatMetadataValue(key, value)}</span>
                                </div>
                              ))}
                            </div>
                          </details>
                        )}
                      </div>
                      <div className="monitoring-event-meta">
                        <span
                          className={`event-badge ${String(
                            event.severity || "low",
                          ).toLowerCase()}`}
                        >
                          {event.severity || "low"}
                        </span>
                        <span className="monitoring-event-time">
                          {formatTime(event.detected_at)}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
          {/* ALERT ENGINE */}
          <div className="monitoring-side-card">
            <div className="monitoring-card-header compact">
              <div>
                <span className="monitoring-card-eyebrow">
                  AI ALERT ENGINE
                </span>
                <h2>Active Alerts</h2>
              </div>
              <div
                className={`monitoring-status-pill ${activeAlertCount > 0 ? "live" : "standby"
                  }`}
              >
                {activeAlertCount > 0
                  ? `${activeAlertCount} ACTIVE`
                  : "CLEAR"}
              </div>
            </div>
            {alertsLoading ? (
              <div className="monitoring-empty-state">
                Loading alerts...
              </div>
            ) : alertsError ? (
              <div className="monitoring-empty-state error-text">
                {alertsError}
              </div>
            ) : visibleAlerts.length === 0 ? (
              <div className="monitoring-alert-placeholder">
                <span className="monitoring-card-eyebrow">
                  SYSTEM READY
                </span>
                <h2>No active safety alerts</h2>
                <p className="monitoring-alert-description">
                  AI-generated safety indicators requiring staff
                  verification will appear here when an event is created.
                </p>
                <div className="monitoring-alert-state">
                  WAITING FOR SAFETY EVENTS
                </div>
              </div>
            ) : (
              <div className="monitoring-event-list">
                {visibleAlerts.map((alert) => (
                  <div
                    className="monitoring-event-item"
                    key={alert.id}
                    id={`empath-alert-${alert.id}`}
                    data-alert-id={String(alert.id)}
                  >
                    <div>
                      <p className="monitoring-event-title">
                        {alert.title}
                      </p>
                      <p className="monitoring-event-description">
                        {alert.message || "Staff verification required."}
                      </p>
                      <section
                        className="monitoring-alert-summary"
                        aria-label={`AI incident summary for alert ${alert.id}`}
                        style={{
                          marginTop: "0.85rem",
                          marginBottom: "0.85rem",
                          padding: "0.85rem",
                          border: "1px solid rgba(148, 163, 184, 0.35)",
                          borderRadius: "0.75rem",
                          background: "rgba(148, 163, 184, 0.08)",
                        }}
                      >
                        <h3
                          style={{
                            margin: "0 0 0.5rem",
                            fontSize: "0.95rem",
                            fontWeight: 700,
                          }}
                        >
                          AI Incident Summary
                        </h3>
                        <div
                          className="monitoring-alert-summary-content"
                          style={{
                            overflowWrap: "anywhere",
                            lineHeight: 1.55,
                            textAlign: "left",
                          }}
                        >
                          {typeof alert.summary === "string" && alert.summary.trim()
                            ? renderSummaryMarkdown(alert.summary.trim())
                            : (
                              <p style={{ margin: 0 }}>
                                Summary is not available yet. Review the original alert message and event details before deciding.
                              </p>
                            )}
                        </div>
                        <p
                          style={{
                            margin: "0.65rem 0 0",
                            fontSize: "0.78rem",
                            opacity: 0.8,
                          }}
                        >
                          AI-generated information may be incomplete. Verify the source evidence; this summary does not confirm a medical event.
                        </p>
                      </section>
                      <p className="monitoring-event-description">
                        Event #{alert.event_id ?? "—"}
                      </p>
                    </div>
                    <div className="monitoring-event-meta">
                      <span
                        className={`event-badge ${String(
                          alert.priority || "low",
                        ).toLowerCase()}`}
                      >
                        {alert.priority || "low"}
                      </span>
                      <span className="monitoring-event-time">
                        {alert.status}
                      </span>
                      <span className="monitoring-event-time">
                        {formatTime(alert.created_at)}
                      </span>
                      <span className="monitoring-event-time">
                        {alert.assigned_to_user_id == null
                          ? "Unassigned"
                          : `Assigned to user #${alert.assigned_to_user_id}`}
                      </span>
                    </div>
                    {transferAlertId === alert.id && (
                      <section
                        aria-label={`Transfer alert ${alert.id}`}
                        style={{
                          marginTop: "0.85rem",
                          padding: "0.9rem",
                          border: "1px solid rgba(148, 163, 184, 0.35)",
                          borderRadius: "0.75rem",
                          background: "rgba(148, 163, 184, 0.06)",
                          display: "grid",
                          gap: "0.7rem",
                        }}
                      >
                        <h4 style={{ margin: 0 }}>Assign / Transfer Alert</h4>
                        {eligibleNursesLoading ? (
                          <p style={{ margin: 0 }}>Loading eligible Nurses…</p>
                        ) : (
                          <form onSubmit={(event) => handleSubmitTransfer(event, alert)} style={{ display: "grid", gap: "0.7rem" }}>
                            <label style={{ display: "grid", gap: "0.3rem" }}>
                              <span>Receiving Nurse</span>
                              <select
                                value={selectedTransferNurseId}
                                onChange={(event) => setSelectedTransferNurseId(event.target.value)}
                                required
                                disabled={eligibleNurses.length === 0 || transferLoadingId === alert.id}
                                style={{ width: "100%", padding: "0.65rem", borderRadius: "0.5rem" }}
                              >
                                <option value="">Select an eligible Nurse</option>
                                {eligibleNurses.map((nurse) => (
                                  <option key={nurse.user_id} value={String(nurse.user_id)}>
                                    {nurse.full_name || nurse.username} ({nurse.username}, ID {nurse.user_id})
                                  </option>
                                ))}
                              </select>
                            </label>
                            <label style={{ display: "grid", gap: "0.3rem" }}>
                              <span>Transfer reason (required)</span>
                              <textarea
                                value={transferReason}
                                onChange={(event) => setTransferReason(event.target.value)}
                                minLength={3}
                                maxLength={1000}
                                rows={3}
                                placeholder="Explain why this alert is being assigned or transferred…"
                                required
                                disabled={transferLoadingId === alert.id}
                                style={{ width: "100%", boxSizing: "border-box", padding: "0.65rem", borderRadius: "0.5rem", resize: "vertical" }}
                              />
                            </label>
                            {transferError && (
                              <div className="monitoring-message error" role="alert">
                                {transferError}
                              </div>
                            )}
                            <div className="monitoring-controls">
                              <button
                                type="submit"
                                className="monitoring-start-button"
                                disabled={
                                  transferLoadingId === alert.id ||
                                  eligibleNursesLoading ||
                                  eligibleNurses.length === 0 ||
                                  !selectedTransferNurseId ||
                                  transferReason.trim().length < 3
                                }
                              >
                                {transferLoadingId === alert.id ? "Transferring…" : "Confirm Transfer"}
                              </button>
                              <button
                                type="button"
                                className="monitoring-refresh-button"
                                onClick={() => {
                                  setTransferAlertId(null);
                                  setTransferError("");
                                }}
                                disabled={transferLoadingId === alert.id}
                              >
                                Cancel
                              </button>
                            </div>
                          </form>
                        )}
                        {!eligibleNursesLoading && eligibleNurses.length === 0 && !transferError && (
                          <p style={{ margin: 0 }}>No other eligible Nurses are available for this alert.</p>
                        )}
                        {transferError && eligibleNursesLoading && (
                          <div className="monitoring-message error" role="alert">{transferError}</div>
                        )}
                      </section>
                    )}
                    <div className="monitoring-controls">
                      {(alert.status === "active" || alert.status === "acknowledged") && (
                        <button
                          type="button"
                          className="monitoring-refresh-button"
                          onClick={() => openTransferPanel(alert.id)}
                          disabled={transferLoadingId === alert.id || eligibleNursesLoading}
                        >
                          {transferAlertId === alert.id
                            ? "Close Transfer"
                            : alert.assigned_to_user_id == null
                              ? "Assign to Nurse"
                              : "Transfer Alert"}
                        </button>
                      )}
                      <button
                        type="button"
                        className="monitoring-refresh-button"
                        onClick={() => toggleAlertHistory(alert.id)}
                        disabled={historyLoadingId === alert.id}
                      >
                        {historyLoadingId === alert.id
                          ? "Loading History…"
                          : historyOpenAlertId === alert.id
                            ? "Hide History"
                            : "Transfer History"}
                      </button>
                      {alert.status === "active" && (
                        <button
                          type="button"
                          className="monitoring-start-button"
                          onClick={() =>
                            handleAlertAction(alert.id, "acknowledge")
                          }
                          disabled={alertActionLoadingId === alert.id}
                        >
                          {alertActionLoadingId === alert.id
                            ? "Updating..."
                            : "Acknowledge"}
                        </button>
                      )}
                      {(alert.status === "active" ||
                        alert.status === "acknowledged") && (
                          <button
                            type="button"
                            className="monitoring-stop-button"
                            onClick={() =>
                              handleAlertAction(alert.id, "resolve")
                            }
                            disabled={alertActionLoadingId === alert.id}
                          >
                            {alertActionLoadingId === alert.id
                              ? "Updating..."
                              : "Resolve"}
                          </button>
                        )}
                      {(alert.status === "active" ||
                        alert.status === "acknowledged") && (
                          <button
                            type="button"
                            className="monitoring-refresh-button"
                            onClick={() => {
                              const confirmed = window.confirm(
                                `Dismiss alert #${alert.id}? It will be removed from the Active Alerts list.`
                              );
                              if (confirmed) {
                                handleAlertAction(alert.id, "dismiss");
                              }
                            }}
                            disabled={alertActionLoadingId === alert.id}
                          >
                            {alertActionLoadingId === alert.id
                              ? "Updating..."
                              : "Dismiss"}
                          </button>
                        )}
                    </div>
                    {historyOpenAlertId === alert.id && (
                      <section
                        aria-label={`Transfer history for alert ${alert.id}`}
                        style={{
                          marginTop: "0.75rem",
                          padding: "0.85rem",
                          border: "1px solid rgba(148, 163, 184, 0.35)",
                          borderRadius: "0.75rem",
                          background: "rgba(148, 163, 184, 0.06)",
                        }}
                      >
                        <h4 style={{ margin: "0 0 0.65rem" }}>Alert Transfer History</h4>
                        {historyLoadingId === alert.id ? (
                          <p style={{ margin: 0 }}>Loading transfer history…</p>
                        ) : historyError ? (
                          <div className="monitoring-message error" role="alert">{historyError}</div>
                        ) : (handoffHistoryByAlert[alert.id] || []).length === 0 ? (
                          <p style={{ margin: 0 }}>No assignment or transfer history recorded for this alert yet.</p>
                        ) : (
                          <ol style={{ margin: 0, paddingLeft: "1.2rem", display: "grid", gap: "0.75rem" }}>
                            {(handoffHistoryByAlert[alert.id] || []).map((entry) => (
                              <li key={entry.id}>
                                <strong>{entry.action === "assigned" ? "Assigned" : "Transferred"}</strong>
                                <p style={{ margin: "0.25rem 0" }}>
                                  From {entry.from_user_id == null ? "Unassigned" : `Nurse user #${entry.from_user_id}`} to Nurse user #{entry.to_user_id}.
                                </p>
                                <p style={{ margin: "0.25rem 0" }}>
                                  Recorded by user #{entry.transferred_by_user_id} · {entry.created_at ? new Date(entry.created_at).toLocaleString() : "Time not recorded"}
                                </p>
                                <p style={{ margin: "0.25rem 0" }}>
                                  <strong>Reason:</strong> {entry.reason}
                                </p>
                              </li>
                            ))}
                          </ol>
                        )}
                      </section>
                    )}
                  </div>
                ))}
              </div>
            )}
            {transferStatusMessage && (
              <div
                role="status"
                style={{
                  marginTop: "0.75rem",
                  padding: "0.75rem",
                  borderRadius: "0.6rem",
                  background: "rgba(34, 197, 94, 0.10)",
                  border: "1px solid rgba(34, 197, 94, 0.35)",
                }}
              >
                {transferStatusMessage}
              </div>
            )}
            {alertActionError && (
              <div className="monitoring-message error" role="alert">
                {alertActionError}
              </div>
            )}
          </div>
        </aside>
      </section>
      {/* =====================================================
          DEMO VIDEO LAB — KEPT SEPARATE
         ===================================================== */}
      <section className="demo-video-section">
        <div className="demo-video-heading">
          <div>
            <span className="monitoring-card-eyebrow">
              OFFLINE VIDEO INTELLIGENCE
            </span>
            <h2>Demo Video Lab</h2>
            <p>
              Upload a video, review it, and run EMPATH&apos;s visual
              behavior analysis separately from shared playback.
            </p>
          </div>
          <span className="demo-video-badge">
            LOCAL ANALYSIS
          </span>
        </div>
        <div className="demo-video-grid">
          {/* VIDEO WORKSPACE */}
          <div className="demo-video-panel">
            <h3>Video Workspace</h3>
            <div className="demo-video-camera-picker">
              <label htmlFor="demo-video-camera">
                Associate findings with an authorized camera
              </label>
              <select
                id="demo-video-camera"
                value={selectedCameraId}
                onChange={(event) => {
                  setSelectedCameraId(event.target.value);
                  setDemoVideoResult(null);
                  setDemoVideoError("");
                }}
                disabled={
                  cameraLoading ||
                  cameras.length === 0 ||
                  demoVideoBusy
                }
                required
              >
                <option value="">
                  {cameraLoading
                    ? "Loading cameras..."
                    : "Select a camera"}
                </option>
                {cameras.map((camera) => (
                  <option
                    key={camera.id}
                    value={String(camera.id)}
                    disabled={camera.is_active === false}
                  >
                    {camera.name ||
                      camera.code ||
                      `Camera ${camera.id}`}
                    {camera.code && camera.name
                      ? ` (${camera.code})`
                      : ""}
                  </option>
                ))}
              </select>
              <p className="demo-video-camera-help">
                The camera provides the resource scope for saved events.
                It does not change the uploaded video&apos;s source.
              </p>
            </div>
            {demoVideoUrl ? (
              <video
                className="demo-video-player"
                src={demoVideoUrl}
                controls
                playsInline
                preload="metadata"
                aria-label="Selected demo video preview"
              />
            ) : (
              <div className="demo-video-empty">
                <div className="demo-video-icon">▶</div>
                <h4>No demo video selected</h4>
                <p>
                  Choose an MP4, AVI, MOV, MKV, or WEBM file to preview it.
                </p>
              </div>
            )}
            <label className="demo-video-file-picker">
              <span>Choose video file</span>
              <input
                type="file"
                accept=".mp4,.avi,.mov,.mkv,.webm,video/*"
                onChange={(event) => {
                  const file = event.target.files?.[0] ?? null;
                  setDemoVideoFile(file);
                  setDemoVideoResult(null);
                  setDemoVideoError("");
                  event.target.value = "";
                }}
              />
            </label>
            {demoVideoFile && (
              <p className="demo-video-filename">
                {demoVideoFile.name}
                {" · "}
                {(demoVideoFile.size / (1024 * 1024)).toFixed(1)} MB
              </p>
            )}
            <button
              type="button"
              className="monitoring-start-button demo-video-run-button"
              onClick={runDemoVideoAnalysis}
              disabled={
                !demoVideoFile ||
                demoVideoBusy ||
                !selectedCameraId
              }
            >
              {demoVideoBusy ? "Analyzing video..." : "Run AI Analysis"}
            </button>
            {demoVideoError && (
              <div
                className="monitoring-message error"
                role="alert"
              >
                {demoVideoError}
              </div>
            )}
          </div>
          {/* ANALYSIS RESULTS */}
          <div className="demo-video-panel">
            <h3>AI Analysis Results</h3>
            {!demoVideoResult && !demoVideoBusy && (
              <div className="demo-video-empty demo-video-results-empty">
                <h4>Awaiting analysis</h4>
                <p>
                  Select a video and run analysis to see posture and
                  frame-level results.
                </p>
              </div>
            )}
            {demoVideoBusy && (
              <div
                className="demo-video-empty demo-video-results-empty"
                aria-live="polite"
              >
                <h4>Processing frames</h4>
                <p>
                  OpenCV and the existing pose-analysis pipeline are
                  processing your video.
                </p>
              </div>
            )}
            {demoVideoResult && (
              <>
                <p className="demo-video-result-filename">
                  {demoVideoResult.video?.original_filename ||
                    demoVideoResult.video?.filename ||
                    demoVideoFile?.name}
                </p>
                <div className="demo-video-metrics">
                  <div className="demo-video-metric">
                    <span>Duration</span>
                    <strong>
                      {Number(
                        demoVideoResult.video?.duration_seconds ?? 0,
                      ).toFixed(1)}
                      s
                    </strong>
                  </div>
                  <div className="demo-video-metric">
                    <span>Frames analyzed</span>
                    <strong>
                      {demoVideoResult.analysis?.frames_analyzed ?? 0}
                    </strong>
                  </div>
                  <div className="demo-video-metric">
                    <span>Pose detection</span>
                    <strong>
                      {(
                        Number(
                          demoVideoResult.analysis?.pose_detection_rate ?? 0,
                        ) * 100
                      ).toFixed(1)}
                      %
                    </strong>
                  </div>
                  <div className="demo-video-metric">
                    <span>Possible-fall frames</span>
                    <strong>
                      {demoVideoResult.analysis?.possible_fall_frames ?? 0}
                    </strong>
                  </div>
                </div>
                {demoVideoResult.event_alerts && (
                  <div
                    className="demo-video-event-summary"
                    role="status"
                  >
                    <strong>
                      {demoVideoResult.event_alerts.created_count > 0
                        ? `${demoVideoResult.event_alerts.created_count} event/alert pair(s) created`
                        : "No possible-fall event was flagged in this video"}
                    </strong>
                    <p>
                      {demoVideoResult.event_alerts.created_count > 0
                        ? "Review the Active Alerts panel. These experimental visual indicators require staff verification."
                        : "This result does not prove that no fall occurred. Only analyzer findings flagged as possible falls can create alerts."}
                    </p>
                    {demoVideoResult.event_alerts.items?.length > 0 && (
                      <ul>
                        {demoVideoResult.event_alerts.items.map(
                          (item, index) => (
                            <li
                              key={`${item.alert_id ?? "alert"}-${index}`}
                            >
                              Alert {item.alert_id ?? "—"} · Event{" "}
                              {item.event_id ?? "—"}
                              {Number.isFinite(
                                Number(item.timestamp_seconds),
                              )
                                ? ` · ${Number(
                                  item.timestamp_seconds,
                                ).toFixed(1)}s`
                                : ""}
                            </li>
                          ),
                        )}
                      </ul>
                    )}
                  </div>
                )}
                <h4 className="demo-video-timeline-heading">
                  Posture Timeline
                </h4>
                <div className="demo-video-timeline">
                  {(demoVideoResult.results ?? [])
                    .filter(
                      (item, index, all) =>
                        item.pose_detected &&
                        (index === 0 ||
                          item.posture !== all[index - 1]?.posture),
                    )
                    .slice(0, 12)
                    .map((item) => (
                      <div
                        className="demo-video-timeline-item"
                        key={item.frame_number}
                      >
                        <strong>
                          {Number(
                            item.timestamp_seconds ?? 0,
                          ).toFixed(1)}
                          s
                        </strong>
                        <span>{item.posture}</span>
                        <span className="demo-video-confidence">
                          {Math.round(
                            Number(item.confidence ?? 0) * 100,
                          )}
                          % confidence
                        </span>
                      </div>
                    ))}
                  {!(demoVideoResult.results ?? []).some(
                    (item) => item.pose_detected,
                  ) && (
                      <p className="demo-video-no-results">
                        No poses were detected. Try a clearer video with the
                        person&apos;s body visible.
                      </p>
                    )}
                </div>
                <p className="demo-video-disclaimer">
                  Results are experimental visual indicators and require
                  human verification. Zero possible-fall frames does not
                  prove that no fall occurred.
                </p>
              </>
            )}
          </div>
        </div>
      </section>
    </main>
  );
}

export default Monitoring;
