
import { useCallback, useEffect, useMemo, useState } from "react";
import "./CamerasAdmin.css";

const API_URL = "http://127.0.0.1:8000";

const EMPTY_FORM = {
  room_id: "",
  name: "",
  code: "",
  source_type: "webcam",
  source_url: "",
  is_active: true,
};

const SOURCE_OPTIONS = [
  { value: "webcam", label: "Webcam" },
  { value: "stream_url", label: "Network stream URL" },
];

async function cameraRequest(endpoint, token, options = {}) {
  const response = await fetch(`${API_URL}${endpoint}`, {
    ...options,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(options.headers || {}),
    },
  });

  let data = null;

  try {
    data = await response.json();
  } catch {
    data = null;
  }

  if (!response.ok) {
    throw new Error(
      data?.detail || data?.message || `Request failed (${response.status})`
    );
  }

  return data;
}

function Cameras({ token }) {
  const [cameras, setCameras] = useState([]);
  const [rooms, setRooms] = useState([]);
  const [isAdmin, setIsAdmin] = useState(false);

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [saving, setSaving] = useState(false);

  const [error, setError] = useState("");
  const [roomWarning, setRoomWarning] = useState("");
  const [formError, setFormError] = useState("");
  const [notice, setNotice] = useState("");

  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState("all");

  const [formOpen, setFormOpen] = useState(false);
  const [editingCamera, setEditingCamera] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);

  // ----------------------------------------------------------
  // LOAD CAMERAS, ROOMS AND AUTHENTICATED USER
  // ----------------------------------------------------------

  const loadCameras = useCallback(
    async (manualRefresh = false) => {
      if (manualRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }

      setError("");
      setRoomWarning("");

      try {
        const [cameraResult, roomResult, profileResult] =
          await Promise.allSettled([
            cameraRequest("/cameras", token),
            cameraRequest("/rooms", token),
            cameraRequest("/auth/me", token),
          ]);

        if (cameraResult.status !== "fulfilled") {
          throw cameraResult.reason;
        }

        if (!Array.isArray(cameraResult.value)) {
          throw new Error("Unexpected camera API response.");
        }

        setCameras(cameraResult.value);

        if (roomResult.status === "fulfilled") {
          setRooms(
            Array.isArray(roomResult.value) ? roomResult.value : []
          );
        } else {
          setRooms([]);
          setRoomWarning(
            "Room options could not be loaded. Check room permissions and the room API."
          );
        }

        if (profileResult.status === "fulfilled") {
          setIsAdmin(
            String(profileResult.value?.role_name || "")
              .toUpperCase() === "ADMIN"
          );
        } else {
          setIsAdmin(false);
        }
      } catch (err) {
        console.error("Camera loading error:", err);

        setError(
          err instanceof Error
            ? err.message
            : "Unable to load cameras."
        );
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [token]
  );

  useEffect(() => {
    loadCameras();
  }, [loadCameras]);

  // ----------------------------------------------------------
  // SEARCH AND STATUS FILTERS
  // ----------------------------------------------------------

  const filteredCameras = useMemo(() => {
    const normalizedSearch = search.trim().toLowerCase();

    return cameras.filter((camera) => {
      const room = rooms.find(
        (item) => Number(item.id) === Number(camera.room_id)
      );

      const matchesSearch =
        normalizedSearch === "" ||
        camera.name?.toLowerCase().includes(normalizedSearch) ||
        camera.code?.toLowerCase().includes(normalizedSearch) ||
        camera.source_type?.toLowerCase().includes(normalizedSearch) ||
        room?.name?.toLowerCase().includes(normalizedSearch);

      const matchesFilter =
        filter === "all" ||
        (filter === "active" && camera.is_active) ||
        (filter === "inactive" && !camera.is_active);

      return matchesSearch && matchesFilter;
    });
  }, [cameras, rooms, search, filter]);

  const activeCount = cameras.filter(
    (camera) => camera.is_active
  ).length;

  const inactiveCount = cameras.filter(
    (camera) => !camera.is_active
  ).length;

  const getRoomLabel = (roomId) => {
    const room = rooms.find(
      (item) => Number(item.id) === Number(roomId)
    );

    return room
      ? `${room.name} (${room.code})`
      : `Room ${roomId}`;
  };

  // ----------------------------------------------------------
  // OPEN CREATE / EDIT FORMS
  // ----------------------------------------------------------

  const openCreateForm = () => {
    setEditingCamera(null);
    setFormError("");
    setNotice("");

    setForm({
      ...EMPTY_FORM,
      room_id: rooms.length ? String(rooms[0].id) : "",
    });

    setFormOpen(true);
  };

  const openEditForm = (camera) => {
    setEditingCamera(camera);
    setFormError("");
    setNotice("");

    setForm({
      room_id: String(camera.room_id),
      name: camera.name || "",
      code: camera.code || "",
      source_type: camera.source_type || "webcam",
      source_url: camera.source_url || "",
      is_active: Boolean(camera.is_active),
    });

    setFormOpen(true);
  };

  const closeForm = () => {
    setFormOpen(false);
    setEditingCamera(null);
    setFormError("");
  };

  const handleFormChange = (event) => {
    const { name, value, checked, type } = event.target;

    setForm((current) => ({
      ...current,
      [name]: type === "checkbox" ? checked : value,
    }));
  };

  // ----------------------------------------------------------
  // SAVE CAMERA
  // ----------------------------------------------------------

  const handleSaveCamera = async (event) => {
    event.preventDefault();

    setFormError("");
    setNotice("");

    if (!isAdmin) {
      setFormError("Only an administrator can manage cameras.");
      return;
    }

    const name = form.name.trim();
    const code = form.code.trim();
    const sourceUrl = form.source_url.trim();

    if (!name || !code || !form.room_id) {
      setFormError("Camera name, code and room are required.");
      return;
    }

    if (form.source_type === "stream_url" && !sourceUrl) {
      setFormError(
        "Enter a network stream URL when using Network stream URL."
      );
      return;
    }

    const payload = {
      room_id: Number(form.room_id),
      name,
      code,
      source_type: form.source_type,
      source_url: sourceUrl || null,
    };

    if (editingCamera) {
      payload.is_active = Boolean(form.is_active);
    }

    setSaving(true);

    try {
      const isEditing = Boolean(editingCamera);

      const endpoint = isEditing
        ? `/cameras/${editingCamera.id}`
        : "/cameras";

      await cameraRequest(endpoint, token, {
        method: isEditing ? "PATCH" : "POST",
        body: JSON.stringify(payload),
      });

      closeForm();

      setNotice(
        isEditing
          ? "Camera updated successfully."
          : "Camera created successfully."
      );

      await loadCameras(true);
    } catch (err) {
      setFormError(
        err instanceof Error
          ? err.message
          : "Unable to save camera."
      );
    } finally {
      setSaving(false);
    }
  };

  // ----------------------------------------------------------
  // LOADING
  // ----------------------------------------------------------

  if (loading) {
    return (
      <main className="workspace-page">
        <div className="workspace-loading">
          <div className="loading-spinner" />
          <h2>Loading cameras...</h2>
          <p>Retrieving camera information from EMPATH.</p>
        </div>
      </main>
    );
  }

  // ----------------------------------------------------------
  // MAIN PAGE
  // ----------------------------------------------------------

  return (
    <main className="workspace-page camera-page">
      <section className="workspace-header camera-page-header">
        <div>
          <span className="section-eyebrow">
            CAMERA MANAGEMENT
          </span>

          <h2>Cameras</h2>

          <p>
            Manage authorized camera records and room assignments.
          </p>
        </div>

        <div className="camera-header-actions">
          {isAdmin && (
            <button
              type="button"
              className="camera-primary-button"
              onClick={openCreateForm}
              disabled={saving || rooms.length === 0}
              title={
                rooms.length === 0
                  ? "No rooms are available to assign."
                  : "Create a camera"
              }
            >
              + Add Camera
            </button>
          )}

          <button
            type="button"
            className="refresh-button"
            onClick={() => loadCameras(true)}
            disabled={refreshing || saving}
          >
            {refreshing ? "Refreshing..." : "Refresh cameras"}
          </button>
        </div>
      </section>

      {error && (
        <div className="camera-message camera-message-error">
          <strong>Unable to load camera records</strong>
          <span>{error}</span>

          <button
            type="button"
            className="camera-secondary-button"
            onClick={() => loadCameras(true)}
          >
            Retry
          </button>
        </div>
      )}

      {roomWarning && (
        <div className="camera-message camera-message-warning">
          {roomWarning}
        </div>
      )}

      {notice && (
        <div className="camera-message camera-message-success">
          {notice}
        </div>
      )}

      {/* CAMERA CREATE / EDIT FORM */}

      {formOpen && isAdmin && (
        <section className="camera-editor">
          <div className="camera-editor-header">
            <div>
              <span className="panel-eyebrow">
                CAMERA CONFIGURATION
              </span>

              <h3>
                {editingCamera ? "Edit Camera" : "Add Camera"}
              </h3>

              <p>
                Set the camera identity, room and source configuration.
              </p>
            </div>
          </div>

          {formError && (
            <div className="camera-message camera-message-error">
              {formError}
            </div>
          )}

          <form className="camera-form" onSubmit={handleSaveCamera}>
            <div className="camera-form-grid">
              <label className="camera-field">
                Camera name
                <input
                  name="name"
                  value={form.name}
                  onChange={handleFormChange}
                  maxLength={100}
                  required
                  placeholder="Example: ICU Camera 02"
                />
              </label>

              <label className="camera-field">
                Unique camera code
                <input
                  name="code"
                  value={form.code}
                  onChange={handleFormChange}
                  maxLength={50}
                  required
                  placeholder="Example: ICU-CAM-02"
                />
              </label>

              <label className="camera-field">
                Assigned room
                <select
                  name="room_id"
                  value={form.room_id}
                  onChange={handleFormChange}
                  required
                >
                  <option value="">Select a room</option>

                  {rooms
                    .filter((room) => room.is_active !== false)
                    .map((room) => (
                      <option key={room.id} value={room.id}>
                        {room.name} ({room.code}) — ID {room.id}
                      </option>
                    ))}
                </select>
              </label>

              <label className="camera-field">
                Source type
                <select
                  name="source_type"
                  value={form.source_type}
                  onChange={handleFormChange}
                  required
                >
                  {SOURCE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}

                  {!SOURCE_OPTIONS.some(
                    (option) => option.value === form.source_type
                  ) && (
                    <option value={form.source_type}>
                      Existing: {form.source_type}
                    </option>
                  )}
                </select>
              </label>

              <label className="camera-field camera-field-full">
                Source URL
                <input
                  type="text"
                  name="source_url"
                  value={form.source_url}
                  onChange={handleFormChange}
                  maxLength={500}
                  placeholder="Optional for webcam; enter stream URL if applicable"
                />

                <small>
                  This saves the source configuration. Actual live streaming,
                  uploaded-video playback and looping require a separate
                  playback integration.
                </small>
              </label>
            </div>

            {editingCamera && (
              <label className="camera-checkbox">
                <input
                  type="checkbox"
                  name="is_active"
                  checked={Boolean(form.is_active)}
                  onChange={handleFormChange}
                />
                Camera active
              </label>
            )}

            <div className="camera-form-actions">
              <button
                type="submit"
                className="camera-primary-button"
                disabled={saving}
              >
                {saving
                  ? "Saving..."
                  : editingCamera
                    ? "Save Changes"
                    : "Create Camera"}
              </button>

              <button
                type="button"
                className="camera-secondary-button"
                onClick={closeForm}
                disabled={saving}
              >
                Cancel
              </button>
            </div>
          </form>
        </section>
      )}

      {/* SUMMARY */}

      <section className="summary-grid camera-summary-grid">
        <div className="summary-card">
          <span>TOTAL CAMERAS</span>
          <strong>{cameras.length}</strong>
        </div>

        <div className="summary-card">
          <span>ACTIVE</span>
          <strong>{activeCount}</strong>
        </div>

        <div className="summary-card">
          <span>INACTIVE</span>
          <strong>{inactiveCount}</strong>
        </div>
      </section>

      {/* DIRECTORY, SEARCH AND FILTERS */}

      <section className="workspace-card camera-directory">
        <div className="workspace-card-header">
          <div>
            <span className="panel-eyebrow">
              CAMERA DIRECTORY
            </span>

            <h3>Authorized Cameras</h3>
          </div>

          <span className="record-count">
            {filteredCameras.length}{" "}
            {filteredCameras.length === 1 ? "record" : "records"}
          </span>
        </div>

        <div className="patient-filters camera-filters">
          <div className="search-wrapper">
            <input
              type="search"
              placeholder="Search camera, code, room or source..."
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>

          <div className="filter-buttons">
            {["all", "active", "inactive"].map((value) => (
              <button
                key={value}
                type="button"
                className={
                  filter === value
                    ? "filter-button active"
                    : "filter-button"
                }
                onClick={() => setFilter(value)}
              >
                {value[0].toUpperCase() + value.slice(1)}
              </button>
            ))}
          </div>
        </div>

        {filteredCameras.length === 0 ? (
          <div className="patient-empty">
            <div className="patient-empty-icon">C</div>
            <h3>No cameras found</h3>

            <p>
              {cameras.length === 0
                ? "No camera records are available within your authorized scope."
                : "No cameras match the current search or filter."}
            </p>

            {isAdmin && rooms.length > 0 && (
              <button
                type="button"
                className="camera-primary-button"
                onClick={openCreateForm}
              >
                + Add Camera
              </button>
            )}
          </div>
        ) : (
          <div className="patient-table-wrapper">
            <table className="patient-table camera-table">
              <thead>
                <tr>
                  <th>Camera</th>
                  <th>Code</th>
                  <th>Room</th>
                  <th>Source</th>
                  <th>Status</th>
                  <th>Camera ID</th>
                  {isAdmin && <th>Actions</th>}
                </tr>
              </thead>

              <tbody>
                {filteredCameras.map((camera) => (
                  <tr key={camera.id}>
                    <td>
                      <div className="patient-name-cell">
                        <div className="patient-avatar">C</div>

                        <div>
                          <strong>{camera.name}</strong>
                          <span>Monitoring device</span>
                        </div>
                      </div>
                    </td>

                    <td>
                      <span className="patient-code">
                        {camera.code}
                      </span>
                    </td>

                    <td>
                      <span className="camera-room-name">
                        {getRoomLabel(camera.room_id)}
                      </span>
                    </td>

                    <td>
                      <span className="patient-code">
                        {camera.source_type}
                      </span>
                    </td>

                    <td>
                      <span
                        className={
                          camera.is_active
                            ? "patient-status active"
                            : "patient-status inactive"
                        }
                      >
                        <span />
                        {camera.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>

                    <td>#{camera.id}</td>

                    {isAdmin && (
                      <td>
                        <button
                          type="button"
                          className="camera-secondary-button camera-edit-button"
                          onClick={() => openEditForm(camera)}
                          disabled={saving}
                        >
                          Edit
                        </button>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}

export default Cameras;
