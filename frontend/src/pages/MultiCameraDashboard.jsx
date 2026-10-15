import { useMemo, useState } from "react";

import SharedPlayback from "./SharedPlayback";
import "./MultiCameraDashboard.css";

function cameraLabel(camera) {
  return camera.name || camera.code || `Camera ${camera.id}`;
}

export default function MultiCameraDashboard({
  token,
  cameras = [],
  loading = false,
}) {
  const [search, setSearch] = useState("");
  const [cameraFilter, setCameraFilter] = useState("all");
  const [cameraFocusId, setCameraFocusId] = useState("all");

  const activeCount = cameras.filter(
    (camera) => camera.is_active !== false,
  ).length;

  const filteredCameras = useMemo(() => {
    const query = search.trim().toLowerCase();

    return cameras.filter((camera) => {
      const isActive = camera.is_active !== false;
      const matchesFilter =
        cameraFilter === "all" ||
        (cameraFilter === "active" && isActive) ||
        (cameraFilter === "inactive" && !isActive);

      const searchableText = [
        camera.name,
        camera.code,
        camera.room_id,
        camera.id,
        camera.source_type,
      ]
        .filter((value) => value !== null && value !== undefined)
        .join(" ")
        .toLowerCase();

      const matchesFocusedCamera =
        cameraFocusId === "all" || String(camera.id) === String(cameraFocusId);

      return (
        matchesFilter &&
        matchesFocusedCamera &&
        (!query || searchableText.includes(query))
      );
    });
  }, [cameras, search, cameraFilter, cameraFocusId]);

  return (
    <section
      className="multi-camera-dashboard"
      aria-labelledby="multi-camera-dashboard-title"
    >
      <header className="multi-camera-dashboard-header">
        <div>
          <span className="monitoring-card-eyebrow">
            AUTHORIZED CAMERA RESOURCES
          </span>
          <h2 id="multi-camera-dashboard-title">Multi-Camera Dashboard</h2>
          <p>
            Each card has an independent recorded-video analysis session.
            These demo loops are not physical CCTV streams.
          </p>
        </div>
        <div className="multi-camera-counts" aria-label="Camera counts">
          <span>{cameras.length} total</span>
          <span>{activeCount} active</span>
        </div>
      </header>

      <div className="multi-camera-dashboard-tools">
        <label className="multi-camera-search">
          <span>Find a camera</span>
          <input
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Search name, code, room, or ID..."
            aria-label="Search authorized cameras"
          />
        </label>

        <label className="multi-camera-filter">
          <span>Jump to camera</span>
          <select
            value={cameraFocusId}
            onChange={(event) => setCameraFocusId(event.target.value)}
            aria-label="Select a camera card"
          >
            <option value="all">All camera cards</option>
            {cameras.map((camera) => (
              <option key={camera.id} value={String(camera.id)}>
                {cameraLabel(camera)} — {camera.code || `ID ${camera.id}`}
              </option>
            ))}
          </select>
        </label>

        <label className="multi-camera-filter">
          <span>Show cameras</span>
          <select
            value={cameraFilter}
            onChange={(event) => setCameraFilter(event.target.value)}
            aria-label="Filter cameras by active status"
          >
            <option value="all">All statuses</option>
            <option value="active">Active only</option>
            <option value="inactive">Inactive only</option>
          </select>
        </label>

        <div className="multi-camera-result-count" aria-live="polite">
          Showing {filteredCameras.length} of {cameras.length}
        </div>
      </div>

      {loading ? (
        <div className="multi-camera-empty-state">Loading authorized cameras...</div>
      ) : cameras.length === 0 ? (
        <div className="multi-camera-empty-state">
          No authorized cameras are available for this account.
        </div>
      ) : filteredCameras.length === 0 ? (
        <div className="multi-camera-empty-state">
          No cameras match your search or filter.
        </div>
      ) : (
        <div className="multi-camera-grid">
          {filteredCameras.map((camera) => (
            <div
              className="multi-camera-grid-item"
              key={camera.id}
              id={`camera-card-${camera.id}`}
              data-camera-id={camera.id}
            >
              <div className="multi-camera-resource-strip">
                <div className="multi-camera-resource-text">
                  <strong>{cameraLabel(camera)}</strong>
                  <span>
                    {camera.code || `Camera ID ${camera.id}`} · Room {camera.room_id ?? "—"}
                  </span>
                </div>
                <span
                  className={`multi-camera-resource-status ${
                    camera.is_active === false ? "is-inactive" : "is-active"
                  }`}
                >
                  {camera.is_active === false ? "INACTIVE" : "REGISTERED"}
                </span>
              </div>

              <SharedPlayback
                token={token}
                initialCameraId={camera.id}
                fixedCamera
              />
            </div>
          ))}
        </div>
      )}

      <p className="multi-camera-dashboard-note">
        The top LIVE Webcam panel uses the administrator's browser webcam and
        remains separate. A registered camera record does not mean a physical
        CCTV device is connected. Possible-fall indicators are experimental
        and require staff review.
      </p>
    </section>
  );
}
