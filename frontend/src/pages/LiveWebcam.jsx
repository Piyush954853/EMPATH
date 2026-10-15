import { useCallback, useEffect, useRef, useState } from "react";
import "./LiveWebcam.css";

const API_URL = "http://127.0.0.1:8000";
const FRAME_INTERVAL_MS = 1500;
const STATUS_POLL_INTERVAL_MS = 2500;
const SNAPSHOT_POLL_INTERVAL_MS = 1500;

async function apiRequest(token, path, options = {}) {
  const headers = new Headers(options.headers || {});

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
    cache: "no-store",
  });

  const data = await response.json().catch(() => null);

  if (!response.ok) {
    const error = new Error(
      data?.detail || `Request failed (${response.status})`,
    );
    error.status = response.status;
    throw error;
  }

  return data;
}

function readRole(user) {
  return String(
    user?.role_name ||
      user?.role?.name ||
      user?.role ||
      "",
  ).toUpperCase();
}

function formatCount(value) {
  const number = Number(value ?? 0);
  return Number.isFinite(number) ? number.toLocaleString() : "—";
}

function formatPercent(value) {
  if (value === null || value === undefined || value === "") {
    return "—";
  }

  const number = Number(value);
  return Number.isFinite(number) ? `${number.toFixed(1)}%` : "—";
}

function formatScore(value) {
  if (value === null || value === undefined || value === "") {
    return "Not available";
  }

  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(4) : "Not available";
}

function getMovementLabel(movement) {
  if (!movement || !movement.status) {
    return "Waiting for frames";
  }

  return String(movement.status).replaceAll("_", " ");
}

export default function LiveWebcam({
  token,
  cameras = [],
  selectedCameraId = "",
  onCameraChange,
  onRefreshEvents,
  onRefreshAlerts,
}) {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const activeRef = useRef(false);
  const generationRef = useRef(0);
  const timerRef = useRef(null);
  const inFlightRef = useRef(false);

  const [isAdmin, setIsAdmin] = useState(false);
  const [roleLoading, setRoleLoading] = useState(true);
  const [session, setSession] = useState(null);
  const [localPreviewActive, setLocalPreviewActive] = useState(false);
  const [starting, setStarting] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [snapshotUrl, setSnapshotUrl] = useState("");
  const [expanded, setExpanded] = useState(false);

  const selectedCamera =
    cameras.find(
      (camera) => String(camera.id) === String(selectedCameraId),
    ) || null;

  const sessionActive = Boolean(session?.active);
  const sessionStatus = String(session?.status || "stopped").toLowerCase();

  const healthStatus = String(
    session?.health_status ||
      (session?.last_error || sessionStatus === "error"
        ? "error"
        : sessionStatus === "stale"
          ? "stale"
          : sessionActive
            ? Number(session?.frames_analyzed || 0) > 0
              ? "live"
              : "starting"
            : "stopped"),
  ).toLowerCase();

  const healthStatusLabel =
    {
      live: "LIVE",
      stale: "STALE",
      stopped: "STOPPED",
      error: "ERROR",
      starting: "STARTING",
    }[healthStatus] || healthStatus.toUpperCase();

  const hasFrameAge =
    session?.last_frame_age_seconds !== null &&
    session?.last_frame_age_seconds !== undefined &&
    Number.isFinite(Number(session.last_frame_age_seconds));

  const lastFrameAgeLabel = hasFrameAge
    ? `${Number(session.last_frame_age_seconds).toFixed(1)} sec ago`
    : "No frames yet";

  const lastFrameReceivedLabel = session?.last_frame_received_at
    ? new Date(session.last_frame_received_at).toLocaleTimeString()
    : "Not received";

  const poseRate = (
    Number(session?.pose_detection_rate || 0) * 100
  ).toFixed(1);

  const movement = session?.last_bed_movement || {};

  const bodyMotionStatus =
    movement.body_motion_detected === true
      ? "Movement indicated"
      : movement.body_motion_detected === false
        ? "Low visible movement"
        : "Unassessed";

  const sceneChangePercent =
    movement.scene_change_pct === null ||
    movement.scene_change_pct === undefined
      ? "—"
      : formatPercent(movement.scene_change_pct);

  const canExpand = Boolean(localPreviewActive || snapshotUrl);

  // -------------------------------------------------------
  // VERIFY ROLE WITH BACKEND
  // Frontend visibility is not a substitute for backend authorization.
  // -------------------------------------------------------
  useEffect(() => {
    let cancelled = false;

    async function loadRole() {
      if (!token) {
        setIsAdmin(false);
        setRoleLoading(false);
        return;
      }

      setRoleLoading(true);

      try {
        const user = await apiRequest(token, "/auth/me");

        if (!cancelled) {
          setIsAdmin(readRole(user) === "ADMIN");
        }
      } catch (requestError) {
        if (!cancelled) {
          setIsAdmin(false);
          setError(
            `Unable to verify account permissions: ${requestError.message}`,
          );
        }
      } finally {
        if (!cancelled) {
          setRoleLoading(false);
        }
      }
    }

    loadRole();

    return () => {
      cancelled = true;
    };
  }, [token]);

  // -------------------------------------------------------
  // TIMER CLEANUP
  // -------------------------------------------------------
  const clearFrameTimer = useCallback(() => {
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  // -------------------------------------------------------
  // STOP THE LOCAL WEBCAM
  // -------------------------------------------------------
  const stopLocalStream = useCallback(() => {
    clearFrameTimer();

    activeRef.current = false;
    generationRef.current += 1;

    const stream = streamRef.current;

    if (stream) {
      stream.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }

    if (videoRef.current) {
      videoRef.current.pause();
      videoRef.current.srcObject = null;
    }

    setLocalPreviewActive(false);
  }, [clearFrameTimer]);

  // -------------------------------------------------------
  // FETCH BACKEND SESSION STATUS
  // -------------------------------------------------------
  useEffect(() => {
    let cancelled = false;

    if (!token || !selectedCameraId) {
      setSession(null);
      return undefined;
    }

    async function refreshStatus() {
      try {
        const result = await apiRequest(
          token,
          `/live/cameras/${selectedCameraId}/status`,
        );

        if (!cancelled) {
          setSession(result.session || null);

          setError((current) =>
            current.startsWith("Unable to refresh live status:")
              ? ""
              : current,
          );
        }
      } catch (requestError) {
        if (!cancelled) {
          setError(
            `Unable to refresh live status: ${requestError.message}`,
          );
        }
      }
    }

    setSession(null);
    refreshStatus();

    const intervalId = window.setInterval(
      refreshStatus,
      STATUS_POLL_INTERVAL_MS,
    );

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
  }, [token, selectedCameraId]);

  // -------------------------------------------------------
  // AUTHORIZED VIEWER SNAPSHOT
  // -------------------------------------------------------
  useEffect(() => {
    let cancelled = false;
    let currentObjectUrl = "";

    setSnapshotUrl("");

    if (
      !token ||
      !selectedCameraId ||
      !sessionActive ||
      localPreviewActive
    ) {
      return undefined;
    }

    async function refreshSnapshot() {
      try {
        const response = await fetch(
          `${API_URL}/live/cameras/${selectedCameraId}/snapshot`,
          {
            headers: {
              Authorization: `Bearer ${token}`,
            },
            cache: "no-store",
          },
        );

        // The session may exist before its first frame arrives.
        if (response.status === 404) return;

        if (!response.ok) {
          throw new Error(
            `Unable to retrieve snapshot (${response.status})`,
          );
        }

        const blob = await response.blob();

        if (cancelled) return;

        const nextUrl = URL.createObjectURL(blob);

        if (currentObjectUrl) {
          URL.revokeObjectURL(currentObjectUrl);
        }

        currentObjectUrl = nextUrl;
        setSnapshotUrl(nextUrl);
      } catch (requestError) {
        if (!cancelled) {
          console.error("Live snapshot error:", requestError);
        }
      }
    }

    refreshSnapshot();

    const intervalId = window.setInterval(
      refreshSnapshot,
      SNAPSHOT_POLL_INTERVAL_MS,
    );

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);

      if (currentObjectUrl) {
        URL.revokeObjectURL(currentObjectUrl);
      }
    };
  }, [token, selectedCameraId, sessionActive, localPreviewActive]);

  // -------------------------------------------------------
  // SEND ONE FRAME FOR AI ANALYSIS
  // Only one request runs at a time.
  // -------------------------------------------------------
  const sendNextFrame = useCallback(
    async function sendFrame(generation) {
      if (
        !activeRef.current ||
        generationRef.current !== generation ||
        inFlightRef.current
      ) {
        return;
      }

      inFlightRef.current = true;

      try {
        const video = videoRef.current;
        const canvas = canvasRef.current;

        if (
          !video ||
          !canvas ||
          video.readyState < 2 ||
          video.videoWidth <= 0 ||
          video.videoHeight <= 0
        ) {
          throw new Error(
            "Waiting for the webcam to provide a frame.",
          );
        }

        // Limit uploaded image size while keeping useful visual detail.
        const sourceWidth = video.videoWidth;
        const sourceHeight = video.videoHeight;
        const maxWidth = 640;
        const scale = Math.min(1, maxWidth / sourceWidth);

        canvas.width = Math.round(sourceWidth * scale);
        canvas.height = Math.round(sourceHeight * scale);

        const context = canvas.getContext("2d");

        if (!context) {
          throw new Error("Unable to prepare the webcam frame.");
        }

        context.drawImage(
          video,
          0,
          0,
          canvas.width,
          canvas.height,
        );

        const blob = await new Promise((resolve) => {
          canvas.toBlob(resolve, "image/jpeg", 0.75);
        });

        if (!blob) {
          throw new Error("Could not encode the webcam frame.");
        }

        if (
          !activeRef.current ||
          generationRef.current !== generation
        ) {
          return;
        }

        const formData = new FormData();

        formData.append(
          "file",
          new File(
            [blob],
            `webcam-frame-${Date.now()}.jpg`,
            { type: "image/jpeg" },
          ),
        );

        const response = await fetch(
          `${API_URL}/live/cameras/${selectedCameraId}/frame`,
          {
            method: "POST",
            headers: {
              Authorization: `Bearer ${token}`,
            },
            body: formData,
          },
        );

        const data = await response.json().catch(() => null);

        if (!response.ok) {
          const requestError = new Error(
            data?.detail ||
              `Frame analysis failed (${response.status})`,
          );

          requestError.status = response.status;
          throw requestError;
        }

        if (
          !activeRef.current ||
          generationRef.current !== generation
        ) {
          return;
        }

        const analysis = data?.analysis || {};

        setSession(analysis);
        setError("");

        if (analysis.new_event_alert) {
          setNotice(
            `New event #${
              analysis.new_event_alert.event_id ?? "—"
            } and alert #${
              analysis.new_event_alert.alert_id ?? "—"
            } created. Staff verification is required.`,
          );

          Promise.resolve(
            onRefreshEvents?.({ silent: true }),
          ).catch(() => {});

          Promise.resolve(
            onRefreshAlerts?.({ silent: true }),
          ).catch(() => {});
        }
      } catch (requestError) {
        if (
          !activeRef.current ||
          generationRef.current !== generation
        ) {
          return;
        }

        setError(requestError.message);

        // Stop sending frames if the server rejected the session.
        if ([401, 403, 409].includes(requestError.status)) {
          activeRef.current = false;
          generationRef.current += 1;

          stopLocalStream();

          // Best-effort cleanup; authorization may have expired.
          apiRequest(
            token,
            `/live/cameras/${selectedCameraId}/stop`,
            { method: "POST" },
          ).catch(() => {});
        }
      } finally {
        inFlightRef.current = false;

        if (
          activeRef.current &&
          generationRef.current === generation
        ) {
          timerRef.current = window.setTimeout(
            () => sendFrame(generation),
            FRAME_INTERVAL_MS,
          );
        }
      }
    },
    [
      token,
      selectedCameraId,
      onRefreshEvents,
      onRefreshAlerts,
      stopLocalStream,
    ],
  );

  // -------------------------------------------------------
  // START WEBCAM AND BACKEND ANALYSIS — ADMIN ONLY
  // -------------------------------------------------------
  const startLive = async () => {
    if (roleLoading || starting || stopping) return;

    setError("");
    setNotice("");

    if (!isAdmin) {
      setError(
        "Only an administrator can start live webcam analysis.",
      );
      return;
    }

    if (!token || !selectedCamera || !selectedCameraId) {
      setError("Select an authorized camera first.");
      return;
    }

    if (selectedCamera.is_active === false) {
      setError("The selected camera is inactive.");
      return;
    }

    if (sessionActive) {
      setError(
        "A live session is already active for this camera.",
      );
      return;
    }

    if (!navigator.mediaDevices?.getUserMedia) {
      setError("Webcam access is unavailable in this browser.");
      return;
    }

    if (!window.isSecureContext) {
      setError("Use localhost or HTTPS to access the webcam.");
      return;
    }

    setStarting(true);

    let stream = null;
    let serverSessionStarted = false;

    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: 960 },
          height: { ideal: 540 },
          facingMode: "user",
        },
        audio: false,
      });

      streamRef.current = stream;

      if (!videoRef.current) {
        throw new Error("The webcam preview is unavailable.");
      }

      videoRef.current.srcObject = stream;
      videoRef.current.muted = true;
      videoRef.current.playsInline = true;

      await videoRef.current.play();

      setLocalPreviewActive(true);

      // Register the shared backend analysis session.
      const result = await apiRequest(
        token,
        `/live/cameras/${selectedCameraId}/start`,
        { method: "POST" },
      );

      serverSessionStarted = true;
      setSession(result.session || null);

      setNotice(
        "Webcam started. EMPATH is receiving frames for AI analysis.",
      );

      activeRef.current = true;
      generationRef.current += 1;

      const generation = generationRef.current;

      timerRef.current = window.setTimeout(
        () => sendNextFrame(generation),
        250,
      );
    } catch (startError) {
      console.error("Live webcam start error:", startError);

      activeRef.current = false;
      generationRef.current += 1;

      stopLocalStream();

      if (serverSessionStarted) {
        apiRequest(
          token,
          `/live/cameras/${selectedCameraId}/stop`,
          { method: "POST" },
        ).catch(() => {});
      }

      let message =
        startError instanceof Error
          ? startError.message
          : "Unable to start the webcam.";

      if (startError.name === "NotAllowedError") {
        message =
          "Allow camera permission in the browser and try again.";
      } else if (startError.name === "NotFoundError") {
        message = "No webcam was found on this device.";
      } else if (startError.name === "NotReadableError") {
        message =
          "The webcam may be in use by another application.";
      }

      setError(message);
    } finally {
      setStarting(false);
    }
  };

  // -------------------------------------------------------
  // STOP WEBCAM AND BACKEND SESSION — ADMIN ONLY
  // -------------------------------------------------------
  const stopLive = async () => {
    if (!isAdmin || !selectedCameraId || stopping) return;

    setStopping(true);
    setError("");
    setNotice("");

    activeRef.current = false;
    generationRef.current += 1;

    stopLocalStream();

    try {
      const result = await apiRequest(
        token,
        `/live/cameras/${selectedCameraId}/stop`,
        { method: "POST" },
      );

      setSession(result.session || null);
      setSnapshotUrl("");

      setNotice(
        "Live webcam capture and analysis have stopped.",
      );
    } catch (stopError) {
      setError(stopError.message);
    } finally {
      setStopping(false);
    }
  };

  // -------------------------------------------------------
  // RELEASE LOCAL BROWSER RESOURCES ON UNMOUNT
  // -------------------------------------------------------
  useEffect(() => {
    return () => {
      activeRef.current = false;
      generationRef.current += 1;

      if (timerRef.current !== null) {
        window.clearTimeout(timerRef.current);
      }

      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
      }

      if (videoRef.current) {
        videoRef.current.pause();
        videoRef.current.srcObject = null;
      }
    };
  }, []);

  return (
    <section className="monitoring-main-card live-webcam-card">
      <header className="monitoring-card-header">
        <div className="monitoring-card-header-left">
          <span className="monitoring-card-eyebrow">LIVE</span>
          <h2>{selectedCamera?.name || "Camera Feed"}</h2>
        </div>

        <span
          className={`monitoring-status-pill ${
            healthStatus === "live" ? "live" : "standby"
          } live-webcam-health-${healthStatus}`}
          title={
            session?.last_frame_received_at
              ? `Last frame received at ${lastFrameReceivedLabel}`
              : "No analyzed frame has been received in this session"
          }
        >
          {roleLoading
            ? "CHECKING"
            : starting
              ? "STARTING"
              : stopping
                ? "STOPPING"
                : healthStatusLabel}
        </span>
      </header>

      <div
        className={`live-webcam-frame ${
          expanded ? "is-expanded" : ""
        }`}
      >
        <video
          ref={videoRef}
          className={`live-webcam-video ${
            localPreviewActive ? "" : "is-hidden"
          }`}
          autoPlay
          muted
          playsInline
          aria-label="Local browser webcam preview"
        />

        <canvas
          ref={canvasRef}
          className="live-webcam-hidden-canvas"
          aria-hidden="true"
        />

        {!localPreviewActive && snapshotUrl && (
          <img
            className="live-webcam-snapshot"
            src={snapshotUrl}
            alt={`Latest authorized frame from ${
              selectedCamera?.name || "camera"
            }`}
          />
        )}

        {!localPreviewActive && !snapshotUrl && (
          <div className="live-webcam-placeholder">
            <span className="live-webcam-placeholder-icon">▶</span>

            <strong>
              {starting
                ? "Starting webcam..."
                : sessionActive
                  ? "Waiting for a webcam frame..."
                  : "Camera feed is offline"}
            </strong>

            <p>
              {isAdmin
                ? "Click Add Live to open the browser webcam and start backend AI analysis."
                : "The latest authorized frames appear here after the administrator starts the live session."}
            </p>
          </div>
        )}

        {sessionActive && (
          <div className="live-webcam-overlay">
            <span>● LIVE DEMO</span>
            <span>{selectedCamera?.code || "CAMERA"}</span>
          </div>
        )}
      </div>

      <div className="live-webcam-toolbar">
        <div className="live-webcam-camera-picker">
          <label htmlFor="live-webcam-camera">Camera</label>

          <select
            id="live-webcam-camera"
            value={selectedCameraId}
            onChange={(event) => {
              onCameraChange?.(event.target.value);
              setError("");
              setNotice("");
            }}
            disabled={
              cameras.length === 0 ||
              starting ||
              stopping ||
              (isAdmin && sessionActive)
            }
          >
            {cameras.length === 0 ? (
              <option value="">No authorized cameras</option>
            ) : (
              cameras.map((camera) => (
                <option
                  key={camera.id}
                  value={String(camera.id)}
                  disabled={camera.is_active === false}
                >
                  {camera.name} — {camera.code}
                </option>
              ))
            )}
          </select>
        </div>

        <button
          type="button"
          className="live-webcam-expand-button"
          onClick={() => setExpanded((value) => !value)}
          disabled={!canExpand}
        >
          {expanded ? "Minimize" : "Expand"}
        </button>

        {isAdmin && (
          <div className="live-webcam-admin-actions">
            <button
              type="button"
              className="monitoring-start-button"
              onClick={startLive}
              disabled={
                roleLoading ||
                starting ||
                stopping ||
                sessionActive ||
                !selectedCameraId ||
                selectedCamera?.is_active === false
              }
            >
              {roleLoading
                ? "Checking..."
                : starting
                  ? "Starting..."
                  : "Add Live"}
            </button>

            <button
              type="button"
              className="monitoring-stop-button"
              onClick={stopLive}
              disabled={
                roleLoading ||
                starting ||
                stopping ||
                (!sessionActive && !localPreviewActive)
              }
            >
              {stopping ? "Stopping..." : "Stop Live"}
            </button>
          </div>
        )}
      </div>

      {!roleLoading && !isAdmin && (
        <p className="live-webcam-disclaimer">
          Authorized viewer mode: playback and snapshot viewing are
          available, but live session controls belong to the administrator.
        </p>
      )}

      {/* Both metrics matrices are visible only to Admin. */}
      {isAdmin && (
        <>
          {/* Existing fall-analysis metrics */}
          <div className="live-webcam-metrics">
            <div>
              <span>Frames analyzed</span>
              <strong>{formatCount(session?.frames_analyzed)}</strong>
            </div>

            <div>
              <span>Pose detection</span>
              <strong>{poseRate}%</strong>
            </div>

            <div>
              <span>Possible-fall frames</span>
              <strong>{formatCount(session?.possible_fall_frames)}</strong>
            </div>

            <div>
              <span>Events created</span>
              <strong>{formatCount(session?.events_created)}</strong>
            </div>

            <div>
              <span>Alerts created</span>
              <strong>{formatCount(session?.alerts_created)}</strong>
            </div>

            <div>
              <span>Last posture</span>
              <strong>{session?.last_posture || "UNKNOWN"}</strong>
            </div>

            <div className="live-webcam-frame-health-metric">
              <span>Last frame age</span>
              <strong>{lastFrameAgeLabel}</strong>

              <small className="live-webcam-metric-note">
                {lastFrameReceivedLabel === "Not received"
                  ? lastFrameReceivedLabel
                  : `Received at ${lastFrameReceivedLabel}`}
              </small>
            </div>
          </div>

          {/* Experimental bed/body movement metrics */}
          <div className="live-webcam-metrics bed-movement-metrics">
            <div>
              <span>Body-motion frames</span>
              <strong>{formatCount(session?.body_motion_frames)}</strong>
            </div>

            <div>
              <span>Low-motion frames</span>
              <strong>{formatCount(session?.low_body_motion_frames)}</strong>
            </div>

            <div>
              <span>Scene-change frames</span>
              <strong>{formatCount(session?.scene_change_frames)}</strong>
            </div>

            <div>
              <span>Movement unassessed</span>
              <strong>
                {formatCount(session?.movement_unassessed_frames)}
              </strong>
            </div>

            <div>
              <span>Tracked body joints</span>
              <strong>{formatCount(movement.tracked_joints)}</strong>
            </div>

            <div>
              <span>Body-motion score</span>
              <strong>{formatScore(movement.body_motion_score)}</strong>
            </div>

            <div>
              <span>Scene change</span>
              <strong>{sceneChangePercent}</strong>
            </div>

            <div>
              <span>Current movement status</span>
              <strong aria-live="polite">
                {getMovementLabel(movement)}
              </strong>
            </div>

            {Number(session?.movement_analyzer_errors || 0) > 0 && (
              <div>
                <span>Movement-analysis errors</span>
                <strong>
                  {formatCount(session?.movement_analyzer_errors)}
                </strong>
              </div>
            )}
          </div>
        </>
      )}

      {error && (
        <div className="monitoring-message error" role="alert">
          {error}
        </div>
      )}

      {notice && (
        <div className="monitoring-message" role="status">
          {notice}
        </div>
      )}

      {healthStatus === "stale" && (
        <div className="monitoring-message error" role="alert">
          No analyzed frame has arrived for more than{" "}
          {session?.stale_after_seconds ?? 20} seconds. The session was
          marked stale. Check the webcam connection before restarting it.
        </div>
      )}

      {healthStatus === "error" && !session?.last_error && (
        <div className="monitoring-message error" role="alert">
          Live analysis reported an error. Check the backend terminal
          for details before restarting.
        </div>
      )}

      {session?.last_error && (
        <div className="monitoring-message error" role="alert">
          {session.last_error}
        </div>
      )}

      <p className="live-webcam-disclaimer">
        This prototype uses the administrator&apos;s browser webcam and
        associates its frames with the selected camera record. It is not a
        physical CCTV stream. Bed-movement metrics are experimental visual
        indicators: scene changes can result from lighting, blankets,
        camera movement, or compression. They do not independently create
        fall alerts and are not a medical assessment. Pose detection rate
        is not fall-detection accuracy.
      </p>
    </section>
  );
}