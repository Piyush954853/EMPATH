import { useCallback, useEffect, useRef, useState } from "react";

import "./SharedPlayback.css";

const API_BASE = "http://127.0.0.1:8000";

async function apiJson(token, path, options = {}) {

  const headers = new Headers(options.headers || {});

  headers.set("Authorization", `Bearer ${token}`);

  const response = await fetch(`${API_BASE}${path}`, {

    ...options,

    headers,

  });

  const data = await response.json().catch(() => null);

  if (!response.ok) {

    throw new Error(

      data?.detail || `Request failed (${response.status})`,

    );

  }

  return data;

}

function getRoleName(user) {

  return String(

    user?.role_name || user?.role?.name || user?.role || "",

  ).toUpperCase();

}

function formatPercent(value) {

  return `${(Number(value || 0) * 100).toFixed(1)}%`;

}

export default function SharedPlayback({ token, initialCameraId = "", fixedCamera = false }) {

  const normalizedInitialCameraId = initialCameraId == null ? "" : String(initialCameraId);

  const [isAdmin, setIsAdmin] = useState(false);

  const [cameras, setCameras] = useState([]);

  const [cameraId, setCameraId] = useState(normalizedInitialCameraId);

  const [selectedFile, setSelectedFile] = useState(null);

  const [session, setSession] = useState(null);

  const [profileLoaded, setProfileLoaded] = useState(false);

  const [loading, setLoading] = useState(false);

  const [actionBusy, setActionBusy] = useState(false);

  const [error, setError] = useState("");

  const [notice, setNotice] = useState("");

  const [videoUrl, setVideoUrl] = useState(null);

  const [expanded, setExpanded] = useState(false);

  const videoRef = useRef(null);

  const loadedSessionKeyRef = useRef("");

  const selectedCamera = cameras.find(

    (camera) => String(camera.id) === String(cameraId),

  );

  const isSessionForSelectedCamera = Boolean(
    session && String(session.camera_id) === String(cameraId),
  );

  const sessionStatus = isSessionForSelectedCamera
    ? String(session?.status || "stopped").toLowerCase()
    : "loading";

  const sessionBusy =
    Boolean(isSessionForSelectedCamera && session?.busy) ||
    ["starting", "running", "stopping"].includes(sessionStatus);

  // Hide last-session metrics when playback is no longer active. The backend
  // may keep the last session object after stop, so camera match alone is not
  // enough to decide whether these metrics should remain visible.
  const showSessionMetrics =
    isSessionForSelectedCamera &&
    ["starting", "running", "stopping"].includes(sessionStatus);

  const displayName =
    selectedCamera?.name || selectedCamera?.code ||
    (cameraId ? `Camera ${cameraId}` : "No camera selected");

  const headingId = fixedCamera
    ? `shared-playback-heading-${cameraId}`
    : "shared-playback-heading";

  const fileInputId = fixedCamera
    ? `shared-playback-file-${cameraId}`
    : "shared-playback-file";

  // Load the current user's real role and authorized camera list.

  useEffect(() => {

    let cancelled = false;

    async function loadInitialData() {

      setLoading(true);

      setError("");

      if (!token) {

        setError("Login token is missing. Please sign in again.");

        setProfileLoaded(true);

        setLoading(false);

        return;

      }

      let userLoaded = false;

      try {

        const user = await apiJson(token, "/auth/me");

        if (!cancelled) {

          setIsAdmin(getRoleName(user) === "ADMIN");

          userLoaded = true;

        }

      } catch (requestError) {

        if (!cancelled) {

          setError(

            `Could not load user profile: ${requestError.message}`,

          );

        }

      }

      try {

        const data = await apiJson(token, "/cameras");

        if (!Array.isArray(data)) {

          throw new Error("Camera list response is not an array.");

        }

        if (!cancelled) {

          setCameras(data);

          if (fixedCamera) {
            const pinnedCameraExists = data.some(
              (camera) => String(camera.id) === normalizedInitialCameraId,
            );

            setCameraId(pinnedCameraExists ? normalizedInitialCameraId : "");

            if (!pinnedCameraExists) {
              setError("This camera is not present in your authorized camera list.");
            }
          } else {
            setCameraId((current) => {
              const stillExists = data.some(
                (camera) => String(camera.id) === String(current),
              );

              if (stillExists) return current;

              const firstActive = data.find(
                (camera) => camera.is_active !== false,
              );

              return firstActive ? String(firstActive.id) : "";
            });
          }

        }

      } catch (requestError) {

        if (!cancelled) {

          setError(

            `Could not load authorized cameras: ${requestError.message}`,

          );

        }

      } finally {

        if (!cancelled) {

          setProfileLoaded(userLoaded);

          setLoading(false);

        }

      }

    }

    loadInitialData();

    return () => {

      cancelled = true;

    };

  }, [token, fixedCamera, normalizedInitialCameraId]);

  // Poll the shared backend session for the selected camera.

  useEffect(() => {

    let cancelled = false;

    if (!token || !cameraId) {

      setSession(null);

      return;

    }

    async function refreshStatus() {

      try {

        const data = await apiJson(

          token,

          `/playback/cameras/${cameraId}/status`,

        );

        if (!cancelled) {

          setSession(data.session);

          // Clear only lifecycle notices when the backend returns a session
          // status confirming the relevant transition. Keep unrelated notices
          // (for example, browser autoplay warnings) visible.
          if (data.session) {
            const currentStatus = String(
              data.session.status || "stopped",
            ).toLowerCase();

            const startWaitingNotice =
              "Shared playback start request accepted. Waiting for session status...";

            const stopWaitingNotice =
              "Stop request accepted. Analysis will finish its current work before stopping.";

            setNotice((currentNotice) => {
              if (
                currentNotice === startWaitingNotice &&
                ["running", "stopping", "stopped", "completed", "error", "failed"].includes(currentStatus)
              ) {
                return "";
              }

              if (
                currentNotice === stopWaitingNotice &&
                ["stopped", "completed", "error", "failed"].includes(currentStatus)
              ) {
                return "";
              }

              return currentNotice;
            });
          }

        }

      } catch (requestError) {

        if (!cancelled) {

          setError(

            `Could not refresh playback status: ${requestError.message}`,

          );

        }

      }

    }

    refreshStatus();

    const intervalId = window.setInterval(

      refreshStatus,

      2500,

    );

    return () => {

      cancelled = true;

      window.clearInterval(intervalId);

    };

  }, [token, cameraId]);

  const sessionIsVisible =

    isSessionForSelectedCamera &&

    ["starting", "running", "stopping"].includes(session.status) &&

    session.video_available === true;

  const activeSessionKey = sessionIsVisible

    ? `${cameraId}:${session.started_at}:${session.original_filename}`

    : "";

  // Download the shared video through an authenticated request.

  // A normal <video src="/api/..."> cannot add our bearer header.

  useEffect(() => {

    let cancelled = false;

    let localObjectUrl = null;

    if (!activeSessionKey || !token) {

      loadedSessionKeyRef.current = "";

      setVideoUrl(null);

      return;

    }

    const requestKey = `${token}:${activeSessionKey}`;

    if (loadedSessionKeyRef.current === requestKey) {

      return;

    }

    loadedSessionKeyRef.current = requestKey;

    setVideoUrl(null);

    setError("");

    async function loadSharedVideo() {

      try {

        const response = await fetch(

          `${API_BASE}/playback/cameras/${cameraId}/video`,

          {

            headers: {

              Authorization: `Bearer ${token}`,

            },

          },

        );

        if (!response.ok) {

          const data = await response.json().catch(() => null);

          throw new Error(

            data?.detail ||

              `Unable to load playback video (${response.status})`,

          );

        }

        const blob = await response.blob();

        if (cancelled) return;

        localObjectUrl = URL.createObjectURL(blob);

        setVideoUrl(localObjectUrl);

      } catch (requestError) {

        if (!cancelled) {

          loadedSessionKeyRef.current = "";

          setError(

            `Shared video could not be loaded: ${requestError.message}`,

          );

        }

      }

    }

    loadSharedVideo();

    return () => {

      cancelled = true;

      if (localObjectUrl) {

        URL.revokeObjectURL(localObjectUrl);

      }

    };

  }, [token, cameraId, activeSessionKey]);

  // Start the common backend session. This is not a per-nurse upload.

  const handleStart = useCallback(

    async (event) => {

      event.preventDefault();

      setError("");

      setNotice("");

      if (!isAdmin) {

        setError("Only an administrator can start shared playback.");

        return;

      }

      if (!cameraId || !selectedCamera) {

        setError("Select an authorized camera.");

        return;

      }

      if (selectedCamera.is_active === false) {

        setError("The selected camera is inactive.");

        return;

      }

      if (!selectedFile) {

        setError("Choose an MP4 or WEBM video first.");

        return;

      }

      if (sessionBusy) {

        setError("A playback session is already active for this camera.");

        return;

      }

      const formData = new FormData();

      formData.append("file", selectedFile);

      setActionBusy(true);

      try {

        const data = await apiJson(

          token,

          `/playback/cameras/${cameraId}/start`,

          {

            method: "POST",

            body: formData,

          },

        );

        setSession(data.session);

        setSelectedFile(null);

        setNotice(

          "Shared playback start request accepted. Waiting for session status...",

        );

      } catch (requestError) {

        setError(requestError.message);

      } finally {

        setActionBusy(false);

      }

    },

    [

      token,

      isAdmin,

      cameraId,

      selectedCamera,

      selectedFile,

      sessionBusy,

    ],

  );

  const handleStop = useCallback(async () => {

    setError("");

    setNotice("");

    if (!isAdmin || !cameraId) {

      setError("Only an administrator can stop shared playback.");

      return;

    }

    setActionBusy(true);

    try {

      const data = await apiJson(

        token,

        `/playback/cameras/${cameraId}/stop`,

        { method: "POST" },

      );

      setSession(data.session);

      setNotice(

        "Stop request accepted. Analysis will finish its current work before stopping.",

      );

    } catch (requestError) {

      setError(requestError.message);

    } finally {

      setActionBusy(false);

    }

  }, [token, isAdmin, cameraId]);

  const handleVideoMetadata = () => {

    const video = videoRef.current;

    if (!video || !Number.isFinite(video.duration) || video.duration <= 0) {

      return;

    }

    const startedAt = Date.parse(session?.started_at || "");

    if (Number.isFinite(startedAt)) {

      const elapsedSeconds = Math.max(

        0,

        (Date.now() - startedAt) / 1000,

      );

      video.currentTime = elapsedSeconds % video.duration;

    }

    video.play().catch(() => {

      setNotice(

        "Press play on the browser video if automatic playback was blocked.",

      );

    });

  };

  if (!token) {

    return (

      <section className="shared-playback-card">

        <h2>{fixedCamera ? displayName : "Shared Camera Playback"}</h2>

        <p>Please sign in to access authorized cameras.</p>

      </section>

    );

  }

  return (

    <section

      className={`shared-playback-card ${

        fixedCamera ? "shared-playback-fixed-card" : ""

      } ${expanded ? "shared-playback-expanded" : ""}`}

      aria-labelledby={headingId}

    >

      <header className="shared-playback-header">

        <div>

          <span className="shared-playback-eyebrow">

            {fixedCamera ? "CAMERA PLAYBACK" : "ADMIN-CONTROLLED PLAYBACK"}

          </span>

          <h2 id={headingId}>

            {fixedCamera ? displayName : "Shared Camera Playback"}

          </h2>

          <p>

            {fixedCamera
              ? "Independent recorded-video demo and backend analysis for this registered camera."
              : "One backend analysis session, associated with the selected registered camera."}

          </p>

        </div>

        <span

          className={`shared-playback-status status-${sessionStatus}`}

        >

          {String(sessionStatus).toUpperCase()}

        </span>

      </header>

      <div className="shared-playback-layout">

        <div className="shared-playback-control-panel">

          {!fixedCamera && (
            <label htmlFor="shared-playback-camera">
              Authorized camera
            </label>
          )}

          {!fixedCamera && (
            <select

              id="shared-playback-camera"

              value={cameraId}

              onChange={(event) => {

                setCameraId(event.target.value);

                setError("");

                setNotice("");

              }}

              disabled={loading || cameras.length === 0 || actionBusy}

            >

              <option value="">

                {loading ? "Loading cameras..." : "Select a camera"}

              </option>

              {cameras.map((camera) => (

                <option

                  key={camera.id}

                  value={String(camera.id)}

                  disabled={camera.is_active === false}

                >

                  {camera.name || camera.code || `Camera ${camera.id}`}

                  {camera.code && camera.name ? ` (${camera.code})` : ""}

                  {camera.is_active === false ? " — Inactive" : ""}

                </option>

              ))}

            </select>
          )}

          <div className="shared-playback-camera-info">

            <span>Camera</span>

            <strong>{displayName}</strong>

            {selectedCamera && (

              <>

                <span>Code</span>

                <strong>{selectedCamera.code || "—"}</strong>

                <span>Room ID</span>

                <strong>{selectedCamera.room_id}</strong>

              </>

            )}

          </div>

          {profileLoaded && isAdmin && (

            <form

              className="shared-playback-admin-form"

              onSubmit={handleStart}

            >

              <label htmlFor={fileInputId}>

                Select demo video (MP4 or WEBM)

              </label>

              <input

                id={fileInputId}

                type="file"

                accept=".mp4,.webm,video/mp4,video/webm"

                onChange={(event) =>

                  setSelectedFile(event.target.files?.[0] || null)

                }

                disabled={actionBusy || sessionBusy || selectedCamera?.is_active === false}

              />

              <button

                type="submit"

                disabled={

                  actionBusy ||

                  !cameraId ||

                  !selectedFile ||

                  selectedCamera?.is_active === false ||

                  sessionBusy

                }

              >

                {actionBusy ? "Please wait..." : "Start Shared Loop"}

              </button>

              <button

                type="button"

                className="shared-playback-stop-button"

                onClick={handleStop}

                disabled={actionBusy || !sessionBusy}

              >

                Stop Shared Loop

              </button>

              <p className="shared-playback-help">

                Only an administrator can start or stop the backend

                session. A new video upload starts one shared session

                for this camera.

              </p>

            </form>

          )}

          {profileLoaded && !isAdmin && (

            <div className="shared-playback-nurse-note">

              <strong>Nurse view</strong>

              <p>

                You can view authorized camera playback and expand or

                minimize the video. Playback source and session controls

                are restricted to administrators.

              </p>

            </div>

          )}

        </div>

        <div className="shared-playback-view-panel">

          <div className="shared-playback-video-heading">

            <h3>{displayName}</h3>

            <button

              type="button"

              className="shared-playback-expand-button"

              onClick={() => setExpanded((value) => !value)}

              disabled={!videoUrl}

            >

              {expanded ? "Minimize video" : "Expand video"}

            </button>

          </div>

          <div

            className={`shared-playback-video-frame ${

              expanded ? "is-expanded" : ""

            }`}

          >

            {videoUrl ? (

              <video

                key={activeSessionKey}

                ref={videoRef}

                className="shared-playback-video"

                src={videoUrl}

                autoPlay

                muted

                loop

                playsInline

                onLoadedMetadata={handleVideoMetadata}

                aria-label="Shared camera video playback"

              />

            ) : (

              <div className="shared-playback-placeholder">

                <span className="shared-playback-placeholder-icon">

                  ▶

                </span>

                <strong>

                  {sessionStatus === "stopping"

                    ? "Stopping playback..."

                    : sessionStatus === "running" ||

                        sessionStatus === "starting"

                      ? "Loading shared video..."

                      : "No active shared playback"}

                </strong>

                <p>

                  {isAdmin

                    ? "Select a video and start the shared loop to display it here."

                    : "The video will appear here when the administrator starts an authorized playback session."}

                </p>

              </div>

            )}

          </div>

          {showSessionMetrics && (

            <div className="shared-playback-metrics">

              <div>

                <span>Completed loops</span>

                <strong>{session.loops_completed ?? 0}</strong>

              </div>

              <div>

                <span>Frames analyzed</span>

                <strong>{session.frames_analyzed_total ?? 0}</strong>

              </div>

              <div>

                <span>Pose detection rate</span>

                <strong>

                  {formatPercent(session.last_pose_detection_rate)}

                </strong>

              </div>

              <div>

                <span>Possible-fall frames</span>

                <strong>{session.last_possible_fall_frames ?? 0}</strong>

              </div>

              <div>

                <span>Events created</span>

                <strong>{session.events_created ?? 0}</strong>

              </div>

              <div>

                <span>Alerts created</span>

                <strong>{session.alerts_created ?? 0}</strong>

              </div>

            </div>

          )}

            {/* Additive feature: experimental bed/body movement metrics.
                The original playback and fall metrics above remain unchanged. */}
            {showSessionMetrics && (
              <>
                <h3 className="shared-playback-movement-heading">
                  Bed Movement — Experimental
                </h3>
                <div className="shared-playback-metrics shared-playback-movement-metrics">
                  <div>
                    <span>Body-motion frames (total)</span>
                    <strong>{session.body_motion_frames ?? 0}</strong>
                  </div>
                  <div>
                    <span>Body-motion frames (last loop)</span>
                    <strong>{session.last_body_motion_frames ?? 0}</strong>
                  </div>
                  <div>
                    <span>Low-motion frames (last loop)</span>
                    <strong>{session.last_low_body_motion_frames ?? 0}</strong>
                  </div>
                  <div>
                    <span>Scene-change frames (last loop)</span>
                    <strong>{session.last_scene_change_frames ?? 0}</strong>
                  </div>
                  <div>
                    <span>Movement unassessed (last loop)</span>
                    <strong>{session.last_movement_unassessed_frames ?? 0}</strong>
                  </div>
                  <div>
                    <span>Tracked body joints (latest frame)</span>
                    <strong>{session.last_bed_movement?.tracked_joints ?? 0}</strong>
                  </div>
                  <div>
                    <span>Body-motion score</span>
                    <strong>
                      {session.last_bed_movement?.body_motion_score == null
                        ? "—"
                        : Number(session.last_bed_movement.body_motion_score).toFixed(4)}
                    </strong>
                  </div>
                  <div>
                    <span>Scene change (latest frame)</span>
                    <strong>
                      {session.last_bed_movement?.scene_change_pct == null
                        ? "—"
                        : `${Number(session.last_bed_movement.scene_change_pct).toFixed(2)}%`}
                    </strong>
                  </div>
                  <div>
                    <span>Current movement status</span>
                    <strong>
                      {session.last_bed_movement?.status || "Waiting for analysis"}
                    </strong>
                  </div>
                  {Number(session.movement_analyzer_errors || 0) > 0 && (
                    <div>
                      <span>Movement analyzer errors</span>
                      <strong>{session.movement_analyzer_errors}</strong>
                    </div>
                  )}
                </div>
                <p className="shared-playback-disclaimer">
                  {session.bed_movement_note ||
                    "Experimental visual movement indicators only. Scene changes can result from lighting, blankets, camera movement, or video compression; this is not a medical assessment."}
                </p>
              </>
            )}

        </div>

      </div>

      {error && (

        <div className="shared-playback-message error" role="alert">

          {error}

        </div>

      )}

      {notice && (

        <div className="shared-playback-message notice" role="status">

          {notice}

        </div>

      )}

      {session?.last_error && (

        <div className="shared-playback-message error" role="alert">

          Worker error: {session.last_error}

        </div>

      )}

      <p className="shared-playback-disclaimer">

        This is a recorded-video prototype. The backend analyzes clips in

        a loop; analysis may take longer than the source video's duration.

        Possible-fall indicators are experimental and require staff

        verification. Pose detection rate is not fall-detection accuracy.

      </p>

    </section>

  );

}
