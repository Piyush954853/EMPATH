
import { useCallback, useEffect, useState } from "react";
import "./HospitalStructureAdmin.css";

const API_URL = "http://127.0.0.1:8000";

async function fetchResource(endpoint, token, options = {}) {
  const response = await fetch(`${API_URL}${endpoint}`, {
    ...options,
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
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

const RESOURCE_TYPES = {
  hospital: { label: "Hospital", endpoint: "/hospitals" },
  department: {
    label: "Department",
    endpoint: "/departments",
    parentType: "hospital",
    parentField: "hospital_id",
  },
  ward: {
    label: "Ward",
    endpoint: "/wards",
    parentType: "department",
    parentField: "department_id",
  },
  room: {
    label: "Room",
    endpoint: "/rooms",
    parentType: "ward",
    parentField: "ward_id",
  },
  bed: {
    label: "Bed",
    endpoint: "/beds",
    parentType: "room",
    parentField: "room_id",
  },
};

const CHILD_RESOURCE = {
  hospital: "department",
  department: "ward",
  ward: "room",
  room: "bed",
};

function getActiveLabel(isActive) {
  return isActive ? "Active" : "Inactive";
}

function getInitials(name) {
  if (!name) return "?";

  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join("");
}

function HospitalStructure({ token }) {
  const [hospitals, setHospitals] = useState([]);
  const [departments, setDepartments] = useState({});
  const [wards, setWards] = useState({});
  const [rooms, setRooms] = useState({});
  const [beds, setBeds] = useState({});

  const [expandedHospitals, setExpandedHospitals] = useState({});
  const [expandedDepartments, setExpandedDepartments] = useState({});
  const [expandedWards, setExpandedWards] = useState({});
  const [expandedRooms, setExpandedRooms] = useState({});

  const [selectedNode, setSelectedNode] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadingNodes, setLoadingNodes] = useState({});
  const [error, setError] = useState("");

  const [canManage, setCanManage] = useState(false);
  const [savingResource, setSavingResource] = useState(false);
  const [editorMode, setEditorMode] = useState(null);
  const [editorType, setEditorType] = useState(null);
  const [editorParent, setEditorParent] = useState(null);

  const [resourceFeedback, setResourceFeedback] = useState({
    type: "",
    message: "",
  });

  const [resourceForm, setResourceForm] = useState({
    name: "",
    code: "",
    address: "",
    is_active: true,
    is_occupied: false,
  });

  // ----------------------------------------------------------
  // LOAD HOSPITALS
  // ----------------------------------------------------------

  const loadHospitals = useCallback(async () => {
    setLoading(true);
    setError("");

    try {
      const data = await fetchResource("/hospitals", token);
      setHospitals(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Unable to load hospitals."
      );
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    loadHospitals();
  }, [loadHospitals]);

  // ----------------------------------------------------------
  // CHECK WHETHER THE USER IS ADMIN
  // UI visibility is not a replacement for backend permissions.
  // ----------------------------------------------------------

  useEffect(() => {
    let cancelled = false;

    if (!token) {
      setCanManage(false);
      return undefined;
    }

    fetchResource("/auth/me", token)
      .then((profile) => {
        if (!cancelled) {
          setCanManage(
            String(profile?.role_name || "").toUpperCase() === "ADMIN"
          );
        }
      })
      .catch(() => {
        if (!cancelled) setCanManage(false);
      });

    return () => {
      cancelled = true;
    };
  }, [token]);

  // ----------------------------------------------------------
  // LOADING HELPERS
  // ----------------------------------------------------------

  const setNodeLoading = (key, value) => {
    setLoadingNodes((current) => ({
      ...current,
      [key]: value,
    }));
  };

  // ----------------------------------------------------------
  // LOAD DEPARTMENTS
  // ----------------------------------------------------------

  const loadDepartments = async (hospitalId) => {
    const key = `hospital-${hospitalId}`;
    setNodeLoading(key, true);

    try {
      const data = await fetchResource(
        `/departments?hospital_id=${hospitalId}`,
        token
      );

      setDepartments((current) => ({
        ...current,
        [hospitalId]: Array.isArray(data) ? data : [],
      }));
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Unable to load departments."
      );
    } finally {
      setNodeLoading(key, false);
    }
  };

  // ----------------------------------------------------------
  // LOAD WARDS
  // ----------------------------------------------------------

  const loadWards = async (departmentId) => {
    const key = `department-${departmentId}`;
    setNodeLoading(key, true);

    try {
      const data = await fetchResource(
        `/wards?department_id=${departmentId}`,
        token
      );

      setWards((current) => ({
        ...current,
        [departmentId]: Array.isArray(data) ? data : [],
      }));
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Unable to load wards."
      );
    } finally {
      setNodeLoading(key, false);
    }
  };

  // ----------------------------------------------------------
  // LOAD ROOMS
  // ----------------------------------------------------------

  const loadRooms = async (wardId) => {
    const key = `ward-${wardId}`;
    setNodeLoading(key, true);

    try {
      const data = await fetchResource(
        `/rooms?ward_id=${wardId}`,
        token
      );

      setRooms((current) => ({
        ...current,
        [wardId]: Array.isArray(data) ? data : [],
      }));
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Unable to load rooms."
      );
    } finally {
      setNodeLoading(key, false);
    }
  };

  // ----------------------------------------------------------
  // LOAD BEDS
  // ----------------------------------------------------------

  const loadBeds = async (roomId) => {
    const key = `room-${roomId}`;
    setNodeLoading(key, true);

    try {
      const data = await fetchResource(
        `/beds?room_id=${roomId}`,
        token
      );

      setBeds((current) => ({
        ...current,
        [roomId]: Array.isArray(data) ? data : [],
      }));
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Unable to load beds."
      );
    } finally {
      setNodeLoading(key, false);
    }
  };

  // ----------------------------------------------------------
  // EXPAND AND SELECT RESOURCES
  // ----------------------------------------------------------

  const toggleHospital = async (hospital) => {
    const isExpanded = expandedHospitals[hospital.id];

    setSelectedNode({ type: "hospital", data: hospital });

    if (isExpanded) {
      setExpandedHospitals((current) => ({
        ...current,
        [hospital.id]: false,
      }));
      return;
    }

    setExpandedHospitals((current) => ({
      ...current,
      [hospital.id]: true,
    }));

    if (!departments[hospital.id]) {
      await loadDepartments(hospital.id);
    }
  };

  const toggleDepartment = async (department) => {
    const isExpanded = expandedDepartments[department.id];

    setSelectedNode({ type: "department", data: department });

    if (isExpanded) {
      setExpandedDepartments((current) => ({
        ...current,
        [department.id]: false,
      }));
      return;
    }

    setExpandedDepartments((current) => ({
      ...current,
      [department.id]: true,
    }));

    if (!wards[department.id]) {
      await loadWards(department.id);
    }
  };

  const toggleWard = async (ward) => {
    const isExpanded = expandedWards[ward.id];

    setSelectedNode({ type: "ward", data: ward });

    if (isExpanded) {
      setExpandedWards((current) => ({
        ...current,
        [ward.id]: false,
      }));
      return;
    }

    setExpandedWards((current) => ({
      ...current,
      [ward.id]: true,
    }));

    if (!rooms[ward.id]) {
      await loadRooms(ward.id);
    }
  };

  const toggleRoom = async (room) => {
    const isExpanded = expandedRooms[room.id];

    setSelectedNode({ type: "room", data: room });

    if (isExpanded) {
      setExpandedRooms((current) => ({
        ...current,
        [room.id]: false,
      }));
      return;
    }

    setExpandedRooms((current) => ({
      ...current,
      [room.id]: true,
    }));

    if (!beds[room.id]) {
      await loadBeds(room.id);
    }
  };

  const selectBed = (bed) => {
    setSelectedNode({ type: "bed", data: bed });
  };

  // ----------------------------------------------------------
  // COUNTS
  // ----------------------------------------------------------

  const departmentCount = Object.values(departments).reduce(
    (total, items) => total + items.length,
    0
  );

  const wardCount = Object.values(wards).reduce(
    (total, items) => total + items.length,
    0
  );

  const roomCount = Object.values(rooms).reduce(
    (total, items) => total + items.length,
    0
  );

  const bedCount = Object.values(beds).reduce(
    (total, items) => total + items.length,
    0
  );

  // ----------------------------------------------------------
  // RESOURCE CREATE / EDIT CONTROLS
  // ----------------------------------------------------------

  const beginCreateResource = (type, parent = null) => {
    setError("");
    setResourceFeedback({ type: "", message: "" });
    setEditorMode("create");
    setEditorType(type);
    setEditorParent(parent);

    setResourceForm({
      name: "",
      code: "",
      address: "",
      is_active: true,
      is_occupied: false,
    });
  };

  const beginEditSelectedResource = () => {
    if (!selectedNode) return;

    setError("");
    setResourceFeedback({ type: "", message: "" });
    setEditorMode("edit");
    setEditorType(selectedNode.type);
    setEditorParent(null);

    setResourceForm({
      name: selectedNode.data?.name || "",
      code: selectedNode.data?.code || "",
      address: selectedNode.data?.address || "",
      is_active: selectedNode.data?.is_active !== false,
      is_occupied: Boolean(selectedNode.data?.is_occupied),
    });
  };

  const beginAddChildResource = () => {
    if (!selectedNode) return;

    const childType = CHILD_RESOURCE[selectedNode.type];
    if (!childType) return;

    beginCreateResource(childType, selectedNode);
  };

  const cancelResourceEditor = () => {
    setEditorMode(null);
    setEditorType(null);
    setEditorParent(null);
    setResourceFeedback({ type: "", message: "" });
  };

  const handleResourceFormChange = (event) => {
    const { name, value, checked, type } = event.target;

    setResourceForm((current) => ({
      ...current,
      [name]: type === "checkbox" ? checked : value,
    }));
  };

  const refreshResourceCollection = async (type, data) => {
    if (type === "hospital") {
      await loadHospitals();
    } else if (type === "department" && data.hospital_id != null) {
      await loadDepartments(data.hospital_id);
    } else if (type === "ward" && data.department_id != null) {
      await loadWards(data.department_id);
    } else if (type === "room" && data.ward_id != null) {
      await loadRooms(data.ward_id);
    } else if (type === "bed" && data.room_id != null) {
      await loadBeds(data.room_id);
    }
  };

  const handleSaveResource = async (event) => {
    event.preventDefault();

    if (!canManage || !editorMode || !editorType) return;

    const config = RESOURCE_TYPES[editorType];
    if (!config) return;

    const name = String(resourceForm.name || "").trim();
    const code = String(resourceForm.code || "").trim();

    if (!name || !code) {
      setResourceFeedback({
        type: "error",
        message: "Name and code are required.",
      });
      return;
    }

    const payload = { name, code };

    if (editorMode === "create") {
      if (editorType === "hospital") {
        payload.address =
          String(resourceForm.address || "").trim() || null;
      } else {
        if (!editorParent || editorParent.type !== config.parentType) {
          setResourceFeedback({
            type: "error",
            message: `Select a valid ${config.parentType} before creating this resource.`,
          });
          return;
        }

        payload[config.parentField] = editorParent.data.id;
      }
    } else {
      if (!selectedNode || selectedNode.type !== editorType) return;

      payload.is_active = Boolean(resourceForm.is_active);

      if (editorType === "hospital") {
        payload.address =
          String(resourceForm.address || "").trim() || null;
      }

      if (editorType === "bed") {
        payload.is_occupied = Boolean(resourceForm.is_occupied);
      }
    }

    setSavingResource(true);
    setResourceFeedback({ type: "", message: "" });

    try {
      const isCreating = editorMode === "create";

      const endpoint = isCreating
        ? config.endpoint
        : `${config.endpoint}/${selectedNode.data.id}`;

      const savedResource = await fetchResource(endpoint, token, {
        method: isCreating ? "POST" : "PATCH",
        body: JSON.stringify(payload),
      });

      await refreshResourceCollection(editorType, savedResource);

      setSelectedNode({ type: editorType, data: savedResource });
      setEditorMode(null);
      setEditorParent(null);

      setResourceFeedback({
        type: "success",
        message: `${config.label} ${
          isCreating ? "created" : "updated"
        } successfully.`,
      });
    } catch (err) {
      setResourceFeedback({
        type: "error",
        message:
          err instanceof Error
            ? err.message
            : "Unable to save resource.",
      });
    } finally {
      setSavingResource(false);
    }
  };

  // ----------------------------------------------------------
  // SELECTED RESOURCE DETAILS
  // ----------------------------------------------------------

  const renderSelectedDetails = () => {
    if (!selectedNode) {
      return (
        <div className="structure-detail-empty">
          <div className="structure-detail-icon">H</div>
          <h3>Select a resource</h3>
          <p>
            Select a hospital, department, ward, room, or bed to view its details.
          </p>
        </div>
      );
    }

    const { type, data } = selectedNode;

    return (
      <div className="structure-detail">
        <div className="structure-detail-top">
          <div className="structure-detail-icon">
            {getInitials(data.name)}
          </div>

          <div>
            <span className="structure-detail-type">{type}</span>
            <h3>{data.name}</h3>
          </div>
        </div>

        <div className="structure-detail-fields">
          <div className="structure-detail-field">
            <span>ID</span>
            <strong>#{data.id}</strong>
          </div>

          <div className="structure-detail-field">
            <span>Code</span>
            <strong className="structure-code">{data.code}</strong>
          </div>

          {type === "hospital" && (
            <div className="structure-detail-field">
              <span>Address</span>
              <strong>{data.address || "—"}</strong>
            </div>
          )}

          {type === "department" && (
            <div className="structure-detail-field">
              <span>Hospital ID</span>
              <strong>#{data.hospital_id}</strong>
            </div>
          )}

          {type === "ward" && (
            <div className="structure-detail-field">
              <span>Department ID</span>
              <strong>#{data.department_id}</strong>
            </div>
          )}

          {type === "room" && (
            <div className="structure-detail-field">
              <span>Ward ID</span>
              <strong>#{data.ward_id}</strong>
            </div>
          )}

          {type === "bed" && (
            <>
              <div className="structure-detail-field">
                <span>Room ID</span>
                <strong>#{data.room_id}</strong>
              </div>

              <div className="structure-detail-field">
                <span>Occupancy</span>
                <strong
                  className={
                    data.is_occupied
                      ? "occupied-value"
                      : "available-value"
                  }
                >
                  {data.is_occupied ? "Occupied" : "Available"}
                </strong>
              </div>
            </>
          )}

          <div className="structure-detail-field">
            <span>Status</span>
            <strong
              className={
                data.is_active ? "active-value" : "inactive-value"
              }
            >
              {getActiveLabel(data.is_active)}
            </strong>
          </div>
        </div>
      </div>
    );
  };

  // ----------------------------------------------------------
  // LOADING VIEW
  // ----------------------------------------------------------

  if (loading) {
    return (
      <main className="workspace-page">
        <div className="structure-loading">
          <div className="loading-spinner" />
          <h2>Loading hospital structure...</h2>
          <p>Retrieving authorized hospital resources.</p>
        </div>
      </main>
    );
  }

  // ----------------------------------------------------------
  // MAIN UI
  // ----------------------------------------------------------

  return (
    <main className="workspace-page">
      <section className="workspace-header">
        <div>
          <span className="section-eyebrow">HOSPITAL OPERATIONS</span>
          <h2>Hospital Structure</h2>
          <p>
            Explore the authorized hospital hierarchy from facility to individual bed.
          </p>
        </div>

        <div className="structure-header-actions">
          {canManage && (
            <button
              type="button"
              className="structure-admin-button"
              onClick={() => beginCreateResource("hospital")}
              disabled={savingResource}
            >
              + Add Hospital
            </button>
          )}

          <button
            type="button"
            className="structure-refresh-button"
            onClick={loadHospitals}
            disabled={loading || savingResource}
          >
            Refresh
          </button>
        </div>
      </section>

      {error && (
        <div className="workspace-error">
          <div>
            <strong>Unable to load structure</strong>
            <span>{error}</span>
          </div>
        </div>
      )}

      {resourceFeedback.message && (
        <div
          className={`structure-admin-message ${
            resourceFeedback.type === "error" ? "is-error" : "is-success"
          }`}
          role="status"
        >
          {resourceFeedback.message}
        </div>
      )}

      <section className="structure-summary-grid">
        <div className="summary-card">
          <span>Hospitals</span>
          <strong>{hospitals.length}</strong>
        </div>

        <div className="summary-card">
          <span>Departments</span>
          <strong>{departmentCount}</strong>
        </div>

        <div className="summary-card">
          <span>Wards</span>
          <strong>{wardCount}</strong>
        </div>

        <div className="summary-card">
          <span>Rooms</span>
          <strong>{roomCount}</strong>
        </div>

        <div className="summary-card">
          <span>Beds</span>
          <strong>{bedCount}</strong>
        </div>
      </section>

      <section className="structure-workspace">
        {/* Resource hierarchy tree */}

        <div className="structure-tree-card">
          <div className="structure-card-header">
            <div>
              <span className="panel-eyebrow">RESOURCE HIERARCHY</span>
              <h3>Hospital Resources</h3>
            </div>

            <span className="record-count">
              {hospitals.length} hospital{hospitals.length === 1 ? "" : "s"}
            </span>
          </div>

          <div className="structure-tree">
            {hospitals.length === 0 ? (
              <div className="structure-empty">
                <div className="structure-empty-icon">H</div>
                <h3>No hospitals available</h3>
                <p>No authorized hospital resources were returned by the backend.</p>
              </div>
            ) : (
              hospitals.map((hospital) => {
                const hospitalExpanded = Boolean(
                  expandedHospitals[hospital.id]
                );
                const hospitalLoading = Boolean(
                  loadingNodes[`hospital-${hospital.id}`]
                );
                const hospitalDepartments = departments[hospital.id] || [];

                return (
                  <div className="tree-node" key={hospital.id}>
                    <button
                      type="button"
                      className={`tree-row tree-row-hospital ${
                        selectedNode?.type === "hospital" &&
                        selectedNode?.data?.id === hospital.id
                          ? "selected"
                          : ""
                      }`}
                      onClick={() => toggleHospital(hospital)}
                    >
                      <span className="tree-toggle">
                        {hospitalExpanded ? "−" : "+"}
                      </span>
                      <span className="tree-icon hospital-icon">H</span>
                      <span className="tree-main">
                        <strong>{hospital.name}</strong>
                        <small>{hospital.code}</small>
                      </span>
                      <span
                        className={
                          hospital.is_active
                            ? "tree-status active"
                            : "tree-status inactive"
                        }
                      >
                        {getActiveLabel(hospital.is_active)}
                      </span>
                    </button>

                    {hospitalExpanded && (
                      <div className="tree-children">
                        {hospitalLoading ? (
                          <div className="tree-loading">
                            Loading departments...
                          </div>
                        ) : hospitalDepartments.length === 0 ? (
                          <div className="tree-empty">
                            No authorized departments.
                          </div>
                        ) : (
                          hospitalDepartments.map((department) => {
                            const expanded = Boolean(
                              expandedDepartments[department.id]
                            );
                            const departmentLoading = Boolean(
                              loadingNodes[`department-${department.id}`]
                            );
                            const departmentWards = wards[department.id] || [];

                            return (
                              <div
                                className="tree-node"
                                key={`department-${department.id}`}
                              >
                                <button
                                  type="button"
                                  className={`tree-row tree-row-department ${
                                    selectedNode?.type === "department" &&
                                    selectedNode?.data?.id === department.id
                                      ? "selected"
                                      : ""
                                  }`}
                                  onClick={() => toggleDepartment(department)}
                                >
                                  <span className="tree-toggle">
                                    {expanded ? "−" : "+"}
                                  </span>
                                  <span className="tree-icon department-icon">
                                    D
                                  </span>
                                  <span className="tree-main">
                                    <strong>{department.name}</strong>
                                    <small>{department.code}</small>
                                  </span>
                                  <span
                                    className={
                                      department.is_active
                                        ? "tree-status active"
                                        : "tree-status inactive"
                                    }
                                  >
                                    {getActiveLabel(department.is_active)}
                                  </span>
                                </button>

                                {expanded && (
                                  <div className="tree-children">
                                    {departmentLoading ? (
                                      <div className="tree-loading">
                                        Loading wards...
                                      </div>
                                    ) : departmentWards.length === 0 ? (
                                      <div className="tree-empty">
                                        No authorized wards.
                                      </div>
                                    ) : (
                                      departmentWards.map((ward) => {
                                        const wardExpanded = Boolean(
                                          expandedWards[ward.id]
                                        );
                                        const wardLoading = Boolean(
                                          loadingNodes[`ward-${ward.id}`]
                                        );
                                        const wardRooms = rooms[ward.id] || [];

                                        return (
                                          <div
                                            className="tree-node"
                                            key={`ward-${ward.id}`}
                                          >
                                            <button
                                              type="button"
                                              className={`tree-row tree-row-ward ${
                                                selectedNode?.type === "ward" &&
                                                selectedNode?.data?.id === ward.id
                                                  ? "selected"
                                                  : ""
                                              }`}
                                              onClick={() => toggleWard(ward)}
                                            >
                                              <span className="tree-toggle">
                                                {wardExpanded ? "−" : "+"}
                                              </span>
                                              <span className="tree-icon ward-icon">
                                                W
                                              </span>
                                              <span className="tree-main">
                                                <strong>{ward.name}</strong>
                                                <small>{ward.code}</small>
                                              </span>
                                              <span
                                                className={
                                                  ward.is_active
                                                    ? "tree-status active"
                                                    : "tree-status inactive"
                                                }
                                              >
                                                {getActiveLabel(ward.is_active)}
                                              </span>
                                            </button>

                                            {wardExpanded && (
                                              <div className="tree-children">
                                                {wardLoading ? (
                                                  <div className="tree-loading">
                                                    Loading rooms...
                                                  </div>
                                                ) : wardRooms.length === 0 ? (
                                                  <div className="tree-empty">
                                                    No authorized rooms.
                                                  </div>
                                                ) : (
                                                  wardRooms.map((room) => {
                                                    const roomExpanded = Boolean(
                                                      expandedRooms[room.id]
                                                    );
                                                    const roomLoading = Boolean(
                                                      loadingNodes[`room-${room.id}`]
                                                    );
                                                    const roomBeds = beds[room.id] || [];

                                                    return (
                                                      <div
                                                        className="tree-node"
                                                        key={`room-${room.id}`}
                                                      >
                                                        <button
                                                          type="button"
                                                          className={`tree-row tree-row-room ${
                                                            selectedNode?.type === "room" &&
                                                            selectedNode?.data?.id === room.id
                                                              ? "selected"
                                                              : ""
                                                          }`}
                                                          onClick={() => toggleRoom(room)}
                                                        >
                                                          <span className="tree-toggle">
                                                            {roomExpanded ? "−" : "+"}
                                                          </span>
                                                          <span className="tree-icon room-icon">
                                                            R
                                                          </span>
                                                          <span className="tree-main">
                                                            <strong>{room.name}</strong>
                                                            <small>{room.code}</small>
                                                          </span>
                                                          <span
                                                            className={
                                                              room.is_active
                                                                ? "tree-status active"
                                                                : "tree-status inactive"
                                                            }
                                                          >
                                                            {getActiveLabel(room.is_active)}
                                                          </span>
                                                        </button>

                                                        {roomExpanded && (
                                                          <div className="tree-children">
                                                            {roomLoading ? (
                                                              <div className="tree-loading">
                                                                Loading beds...
                                                              </div>
                                                            ) : roomBeds.length === 0 ? (
                                                              <div className="tree-empty">
                                                                No authorized beds.
                                                              </div>
                                                            ) : (
                                                              roomBeds.map((bed) => (
                                                                <button
                                                                  type="button"
                                                                  key={`bed-${bed.id}`}
                                                                  className={`tree-row tree-row-bed ${
                                                                    selectedNode?.type === "bed" &&
                                                                    selectedNode?.data?.id === bed.id
                                                                      ? "selected"
                                                                      : ""
                                                                  }`}
                                                                  onClick={() => selectBed(bed)}
                                                                >
                                                                  <span className="tree-spacer" />
                                                                  <span className="tree-icon bed-icon">
                                                                    B
                                                                  </span>
                                                                  <span className="tree-main">
                                                                    <strong>{bed.name}</strong>
                                                                    <small>{bed.code}</small>
                                                                  </span>
                                                                  <span
                                                                    className={
                                                                      bed.is_occupied
                                                                        ? "tree-occupancy occupied"
                                                                        : "tree-occupancy available"
                                                                    }
                                                                  >
                                                                    {bed.is_occupied
                                                                      ? "Occupied"
                                                                      : "Available"}
                                                                  </span>
                                                                </button>
                                                              ))
                                                            )}
                                                          </div>
                                                        )}
                                                      </div>
                                                    );
                                                  })
                                                )}
                                              </div>
                                            )}
                                          </div>
                                        );
                                      })
                                    )}
                                  </div>
                                )}
                              </div>
                            );
                          })
                        )}
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Selected resource details and admin editor */}

        <aside className="structure-detail-card">
          <div className="structure-card-header">
            <div>
              <span className="panel-eyebrow">RESOURCE DETAILS</span>
              <h3>Selected Resource</h3>
            </div>
          </div>

          {renderSelectedDetails()}

          {canManage && (
            <div className="structure-admin-actions">
              {selectedNode && (
                <button
                  type="button"
                  className="structure-admin-button structure-admin-button-secondary"
                  onClick={beginEditSelectedResource}
                  disabled={savingResource}
                >
                  Edit selected
                </button>
              )}

              {selectedNode && CHILD_RESOURCE[selectedNode.type] && (
                <button
                  type="button"
                  className="structure-admin-button"
                  onClick={beginAddChildResource}
                  disabled={savingResource}
                >
                  + Add{" "}
                  {RESOURCE_TYPES[CHILD_RESOURCE[selectedNode.type]].label}
                </button>
              )}
            </div>
          )}

          {canManage && editorMode && editorType && (
            <section className="structure-resource-editor">
              <div className="structure-resource-editor-heading">
                <h4>
                  {editorMode === "create" ? "Add" : "Edit"}{" "}
                  {RESOURCE_TYPES[editorType].label}
                </h4>

                {editorMode === "create" && editorParent && (
                  <p>
                    Parent:{" "}
                    {editorParent.data?.name ||
                      RESOURCE_TYPES[editorParent.type]?.label}
                  </p>
                )}
              </div>

              <form onSubmit={handleSaveResource}>
                <label className="structure-admin-field">
                  Name
                  <input
                    name="name"
                    value={resourceForm.name}
                    onChange={handleResourceFormChange}
                    maxLength={
                      editorType === "room" || editorType === "bed"
                        ? 100
                        : 200
                    }
                    required
                  />
                </label>

                <label className="structure-admin-field">
                  Code
                  <input
                    name="code"
                    value={resourceForm.code}
                    onChange={handleResourceFormChange}
                    maxLength={50}
                    required
                  />
                </label>

                {editorType === "hospital" && (
                  <label className="structure-admin-field">
                    Address
                    <textarea
                      name="address"
                      value={resourceForm.address}
                      onChange={handleResourceFormChange}
                      rows={3}
                      maxLength={500}
                    />
                  </label>
                )}

                {editorMode === "edit" && (
                  <label className="structure-admin-checkbox">
                    <input
                      type="checkbox"
                      name="is_active"
                      checked={Boolean(resourceForm.is_active)}
                      onChange={handleResourceFormChange}
                    />
                    Resource active
                  </label>
                )}

                {editorMode === "edit" && editorType === "bed" && (
                  <label className="structure-admin-checkbox">
                    <input
                      type="checkbox"
                      name="is_occupied"
                      checked={Boolean(resourceForm.is_occupied)}
                      onChange={handleResourceFormChange}
                    />
                    Bed currently occupied
                  </label>
                )}

                <div className="structure-admin-form-actions">
                  <button
                    type="submit"
                    className="structure-admin-button"
                    disabled={savingResource}
                  >
                    {savingResource
                      ? "Saving..."
                      : `Save ${RESOURCE_TYPES[editorType].label}`}
                  </button>

                  <button
                    type="button"
                    className="structure-admin-button structure-admin-button-secondary"
                    onClick={cancelResourceEditor}
                    disabled={savingResource}
                  >
                    Cancel
                  </button>
                </div>
              </form>
            </section>
          )}
        </aside>
      </section>
    </main>
  );
}

export default HospitalStructure;
