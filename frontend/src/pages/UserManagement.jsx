
import { useCallback, useEffect, useState } from "react";
import "./UserManagement.css";

const API_URL = "http://127.0.0.1:8000";

const EMPTY_ASSIGNMENTS = {
  department_ids: [],
  ward_ids: [],
  room_ids: [],
  bed_ids: [],
};

async function userRequest(endpoint, token, options = {}) {
  const response = await fetch(`${API_URL}${endpoint}`, {
    ...options,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
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

function numberArray(values) {
  return values.map(Number);
}

function UserManagement({ token }) {
  const [users, setUsers] = useState([]);
  const [roles, setRoles] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [wards, setWards] = useState([]);
  const [rooms, setRooms] = useState([]);
  const [beds, setBeds] = useState([]);

  const [selectedUserId, setSelectedUserId] = useState("");
  const [assignments, setAssignments] = useState(EMPTY_ASSIGNMENTS);

  const [createForm, setCreateForm] = useState({
    username: "",
    email: "",
    full_name: "",
    password: "",
    role_id: "",
  });

  const [editForm, setEditForm] = useState({
    full_name: "",
    email: "",
    password: "",
    role_id: "",
    is_active: true,
  });

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [resourceWarning, setResourceWarning] = useState("");

  const selectedUser =
    users.find((user) => String(user.id) === String(selectedUserId)) ||
    null;

  const loadData = useCallback(async () => {
    setLoading(true);
    setError("");
    setResourceWarning("");

    try {
      const [userData, roleData] = await Promise.all([
        userRequest("/users", token),
        userRequest("/users/roles", token),
      ]);

      setUsers(Array.isArray(userData) ? userData : []);
      setRoles(Array.isArray(roleData) ? roleData : []);

      const endpoints = [
        ["/departments", setDepartments, "departments"],
        ["/wards", setWards, "wards"],
        ["/rooms", setRooms, "rooms"],
        ["/beds", setBeds, "beds"],
      ];

      const results = await Promise.allSettled(
        endpoints.map(([endpoint]) => userRequest(endpoint, token))
      );

      const failed = [];

      results.forEach((result, index) => {
        const [, setter, label] = endpoints[index];

        if (result.status === "fulfilled") {
          setter(Array.isArray(result.value) ? result.value : []);
        } else {
          setter([]);
          failed.push(label);
          console.error(`Could not load ${label}:`, result.reason);
        }
      });

      if (failed.length) {
        setResourceWarning(
          `Could not load ${failed.join(", ")}. Check the corresponding API permissions and endpoints.`
        );
      }
    } catch (err) {
      setError(err.message || "Unable to load user management data.");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  useEffect(() => {
    if (!selectedUser) {
      setEditForm({
        full_name: "",
        email: "",
        password: "",
        role_id: "",
        is_active: true,
      });
      setAssignments(EMPTY_ASSIGNMENTS);
      return;
    }

    setEditForm({
      full_name: selectedUser.full_name || "",
      email: selectedUser.email || "",
      password: "",
      role_id: String(selectedUser.role_id),
      is_active: Boolean(selectedUser.is_active),
    });

    let cancelled = false;

    userRequest(`/users/${selectedUser.id}/assignments`, token)
      .then((data) => {
        if (!cancelled) {
          setAssignments({
            department_ids: numberArray(data.department_ids || []),
            ward_ids: numberArray(data.ward_ids || []),
            room_ids: numberArray(data.room_ids || []),
            bed_ids: numberArray(data.bed_ids || []),
          });
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(`Could not load assignments: ${err.message}`);
          setAssignments(EMPTY_ASSIGNMENTS);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [selectedUser, token]);

  const updateCreateField = (event) => {
    const { name, value } = event.target;

    setCreateForm((current) => ({
      ...current,
      [name]: value,
    }));
  };

  const updateEditField = (event) => {
    const { name, value, checked, type } = event.target;

    setEditForm((current) => ({
      ...current,
      [name]: type === "checkbox" ? checked : value,
    }));
  };

  const changeDepartmentSelection = (event) => {
    const department_ids = numberArray(
      Array.from(event.target.selectedOptions, (option) => option.value)
    );

    setAssignments((current) => {
      const ward_ids = current.ward_ids.filter((id) => {
        const ward = wards.find((item) => Number(item.id) === id);
        return ward && department_ids.includes(Number(ward.department_id));
      });

      const room_ids = current.room_ids.filter((id) => {
        const room = rooms.find((item) => Number(item.id) === id);
        return room && ward_ids.includes(Number(room.ward_id));
      });

      const bed_ids = current.bed_ids.filter((id) => {
        const bed = beds.find((item) => Number(item.id) === id);
        return bed && room_ids.includes(Number(bed.room_id));
      });

      return { department_ids, ward_ids, room_ids, bed_ids };
    });
  };

  const changeWardSelection = (event) => {
    const ward_ids = numberArray(
      Array.from(event.target.selectedOptions, (option) => option.value)
    );

    setAssignments((current) => {
      const room_ids = current.room_ids.filter((id) => {
        const room = rooms.find((item) => Number(item.id) === id);
        return room && ward_ids.includes(Number(room.ward_id));
      });

      const bed_ids = current.bed_ids.filter((id) => {
        const bed = beds.find((item) => Number(item.id) === id);
        return bed && room_ids.includes(Number(bed.room_id));
      });

      return { ...current, ward_ids, room_ids, bed_ids };
    });
  };

  const changeRoomSelection = (event) => {
    const room_ids = numberArray(
      Array.from(event.target.selectedOptions, (option) => option.value)
    );

    setAssignments((current) => {
      const bed_ids = current.bed_ids.filter((id) => {
        const bed = beds.find((item) => Number(item.id) === id);
        return bed && room_ids.includes(Number(bed.room_id));
      });

      return { ...current, room_ids, bed_ids };
    });
  };

  const changeBedSelection = (event) => {
    const bed_ids = numberArray(
      Array.from(event.target.selectedOptions, (option) => option.value)
    );

    setAssignments((current) => ({ ...current, bed_ids }));
  };

  const handleCreateUser = async (event) => {
    event.preventDefault();
    setError("");
    setSuccess("");
    setSaving(true);

    try {
      const created = await userRequest("/users", token, {
        method: "POST",
        body: JSON.stringify({
          ...createForm,
          role_id: Number(createForm.role_id),
        }),
      });

      setCreateForm({
        username: "",
        email: "",
        full_name: "",
        password: "",
        role_id: "",
      });

      await loadData();
      setSelectedUserId(String(created.id));
      setSuccess(`Account created successfully for ${created.username}.`);
    } catch (err) {
      setError(err.message || "Could not create the account.");
    } finally {
      setSaving(false);
    }
  };

  const handleSaveUser = async (event) => {
    event.preventDefault();

    if (!selectedUser) return;

    setError("");
    setSuccess("");
    setSaving(true);

    try {
      const body = {
        full_name: editForm.full_name,
        email: editForm.email,
        role_id: Number(editForm.role_id),
        is_active: editForm.is_active,
      };

      if (editForm.password.trim()) {
        body.password = editForm.password;
      }

      await userRequest(`/users/${selectedUser.id}`, token, {
        method: "PATCH",
        body: JSON.stringify(body),
      });

      setEditForm((current) => ({ ...current, password: "" }));
      await loadData();
      setSuccess("User details updated successfully.");
    } catch (err) {
      setError(err.message || "Could not update this user.");
    } finally {
      setSaving(false);
    }
  };

  const handleSaveAssignments = async () => {
    if (!selectedUser) return;

    setError("");
    setSuccess("");
    setSaving(true);

    try {
      await userRequest(
        `/users/${selectedUser.id}/assignments`,
        token,
        {
          method: "PUT",
          body: JSON.stringify(assignments),
        }
      );

      setSuccess("Resource assignments saved successfully.");
    } catch (err) {
      setError(err.message || "Could not save resource assignments.");
    } finally {
      setSaving(false);
    }
  };

  const handleDeactivate = async () => {
    if (!selectedUser) return;

    const confirmed = window.confirm(
      `Deactivate account "${selectedUser.username}"?`
    );

    if (!confirmed) return;

    setError("");
    setSuccess("");
    setSaving(true);

    try {
      await userRequest(`/users/${selectedUser.id}`, token, {
        method: "DELETE",
      });

      await loadData();
      setSuccess("Account deactivated. Its record and assignments are retained.");
    } catch (err) {
      setError(err.message || "Could not deactivate this account.");
    } finally {
      setSaving(false);
    }
  };

  const availableDepartments = departments.filter(
    (item) => item.is_active !== false
  );

  const availableWards = wards.filter(
    (item) =>
      item.is_active !== false &&
      (
        assignments.department_ids.includes(Number(item.department_id)) ||
        assignments.ward_ids.includes(Number(item.id))
      )
  );

  const availableRooms = rooms.filter(
    (item) =>
      item.is_active !== false &&
      (
        assignments.ward_ids.includes(Number(item.ward_id)) ||
        assignments.room_ids.includes(Number(item.id))
      )
  );

  const availableBeds = beds.filter(
    (item) =>
      item.is_active !== false &&
      (
        assignments.room_ids.includes(Number(item.room_id)) ||
        assignments.bed_ids.includes(Number(item.id))
      )
  );

  return (
    <main className="dashboard-main um-page">
      <header className="um-header">
        <div>
          <span className="section-eyebrow">ADMINISTRATION</span>
          <h2>User Management</h2>
          <p>Create accounts, manage roles, and assign hospital resources.</p>
        </div>

        <button
          type="button"
          className="refresh-button"
          onClick={loadData}
          disabled={loading || saving}
        >
          {loading ? "Loading..." : "Refresh"}
        </button>
      </header>

      {error && <div className="um-message um-error">{error}</div>}
      {success && <div className="um-message um-success">{success}</div>}
      {resourceWarning && (
        <div className="um-message um-warning">{resourceWarning}</div>
      )}

      <section className="um-panel">
        <h3>Create a user account</h3>

        <form onSubmit={handleCreateUser}>
          <div className="um-form-grid">
            <label className="um-field">
              Full name
              <input
                name="full_name"
                value={createForm.full_name}
                onChange={updateCreateField}
                required
                maxLength={200}
              />
            </label>

            <label className="um-field">
              Username
              <input
                name="username"
                value={createForm.username}
                onChange={updateCreateField}
                required
                minLength={3}
                maxLength={100}
              />
            </label>

            <label className="um-field">
              Email
              <input
                type="email"
                name="email"
                value={createForm.email}
                onChange={updateCreateField}
                required
                maxLength={200}
              />
            </label>

            <label className="um-field">
              Initial password
              <input
                type="password"
                name="password"
                value={createForm.password}
                onChange={updateCreateField}
                required
                minLength={10}
                maxLength={128}
                autoComplete="new-password"
              />
            </label>

            <label className="um-field">
              Role
              <select
                name="role_id"
                value={createForm.role_id}
                onChange={updateCreateField}
                required
              >
                <option value="">Choose a role</option>
                {roles.map((role) => (
                  <option key={role.id} value={role.id}>
                    {role.name}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <button className="um-button" type="submit" disabled={saving}>
            {saving ? "Saving..." : "Create account"}
          </button>
        </form>
      </section>

      <section className="um-panel">
        <div className="um-section-heading">
          <div>
            <h3>Existing accounts</h3>
            <p>Select a user to edit details and access assignments.</p>
          </div>
          <span>{users.length} accounts</span>
        </div>

        {loading ? (
          <p>Loading users...</p>
        ) : users.length === 0 ? (
          <p>No users found.</p>
        ) : (
          <div className="um-user-list">
            {users.map((user) => (
              <div
                key={user.id}
                className={`um-user-row ${
                  String(user.id) === String(selectedUserId)
                    ? "um-user-row-selected"
                    : ""
                }`}
              >
                <div className="um-user-details">
                  <strong>{user.full_name || user.username}</strong>
                  <span>
                    @{user.username} · {user.role_name || "Unknown role"}
                  </span>
                  <small>
                    {user.is_active ? "Active account" : "Inactive account"}
                  </small>
                </div>

                <button
                  type="button"
                  className="um-secondary-button"
                  onClick={() => {
                    setError("");
                    setSuccess("");
                    setSelectedUserId(String(user.id));
                  }}
                >
                  Manage
                </button>
              </div>
            ))}
          </div>
        )}
      </section>

      {selectedUser && (
        <>
          <section className="um-panel">
            <h3>Edit account</h3>
            <p>
              Editing <strong>{selectedUser.username}</strong>
            </p>

            <form onSubmit={handleSaveUser}>
              <div className="um-form-grid">
                <label className="um-field">
                  Full name
                  <input
                    name="full_name"
                    value={editForm.full_name}
                    onChange={updateEditField}
                    required
                    maxLength={200}
                  />
                </label>

                <label className="um-field">
                  Email
                  <input
                    type="email"
                    name="email"
                    value={editForm.email}
                    onChange={updateEditField}
                    required
                    maxLength={200}
                  />
                </label>

                <label className="um-field">
                  Role
                  <select
                    name="role_id"
                    value={editForm.role_id}
                    onChange={updateEditField}
                    required
                  >
                    {roles.map((role) => (
                      <option key={role.id} value={role.id}>
                        {role.name}
                      </option>
                    ))}
                  </select>
                </label>

                <label className="um-field">
                  New password (leave blank to keep current)
                  <input
                    type="password"
                    name="password"
                    value={editForm.password}
                    onChange={updateEditField}
                    minLength={10}
                    maxLength={128}
                    autoComplete="new-password"
                  />
                </label>
              </div>

              <label className="um-checkbox">
                <input
                  type="checkbox"
                  name="is_active"
                  checked={editForm.is_active}
                  onChange={updateEditField}
                />
                Account active
              </label>

              <div className="um-actions">
                <button className="um-button" type="submit" disabled={saving}>
                  Save account
                </button>

                {selectedUser.is_active && (
                  <button
                    className="um-danger-button"
                    type="button"
                    onClick={handleDeactivate}
                    disabled={saving}
                  >
                    Deactivate account
                  </button>
                )}
              </div>
            </form>
          </section>

          <section className="um-panel">
            <h3>Resource assignments</h3>
            <p>
              Select a department first. Available ward, room, and bed
              choices depend on the selected parent resources.
            </p>

            <div className="um-assignment-grid">
              <label className="um-field">
                Departments
                <select
                  multiple
                  size={5}
                  value={assignments.department_ids.map(String)}
                  onChange={changeDepartmentSelection}
                >
                  {availableDepartments.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name} ({item.code})
                    </option>
                  ))}
                </select>
              </label>

              <label className="um-field">
                Wards
                <select
                  multiple
                  size={5}
                  value={assignments.ward_ids.map(String)}
                  onChange={changeWardSelection}
                >
                  {availableWards.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name} ({item.code})
                    </option>
                  ))}
                </select>
              </label>

              <label className="um-field">
                Rooms
                <select
                  multiple
                  size={5}
                  value={assignments.room_ids.map(String)}
                  onChange={changeRoomSelection}
                >
                  {availableRooms.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name} ({item.code})
                    </option>
                  ))}
                </select>
              </label>

              <label className="um-field">
                Beds
                <select
                  multiple
                  size={5}
                  value={assignments.bed_ids.map(String)}
                  onChange={changeBedSelection}
                >
                  {availableBeds.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name} ({item.code})
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <p className="um-help">
              Tip: hold Ctrl while clicking to select multiple items.
              Saving an assignment replaces that user's previous assignments
              in these four categories.
            </p>

            <button
              className="um-button"
              type="button"
              onClick={handleSaveAssignments}
              disabled={saving}
            >
              {saving ? "Saving..." : "Save resource assignments"}
            </button>
          </section>
        </>
      )}
    </main>
  );
}

export default UserManagement;
