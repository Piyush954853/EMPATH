function Sidebar({ activePage, onNavigate, user }) {
  // Read the role returned by the backend's /auth/me endpoint.
  const role = String(user?.role_name || "").trim().toUpperCase();

  // Existing navigation items, now filtered by role.
  const navigationItems = [
    {
      id: "dashboard",
      label: "Dashboard",
      icon: "D",
      roles: ["ADMIN", "NURSE", "DOCTOR", "RESEARCHER"],
    },
    {
      id: "monitoring",
      label: "Monitoring",
      icon: "M",
      roles: ["ADMIN", "NURSE", "DOCTOR"],
    },
    {
      id: "patients",
      label: "Patients",
      icon: "P",
      roles: ["ADMIN", "NURSE", "DOCTOR"],
    },
    {
      id: "cameras",
      label: "Cameras",
      icon: "C",
      roles: ["ADMIN", "NURSE", "DOCTOR"],
    },
    {
      id: "events",
      label: "Events",
      icon: "E",
      roles: ["ADMIN", "NURSE", "DOCTOR", "RESEARCHER"],
    },
    {
      id: "hospital",
      label: "Hospital Structure",
      icon: "H",
      roles: ["ADMIN", "NURSE", "DOCTOR", "RESEARCHER"],
    },
    {
      id: "users",
      label: "User Management",
       icon: "U",
       roles: ["ADMIN"],
    }
  ];
  // Display only pages assigned to the user's role.
  // If the role is missing, only the common Dashboard is shown.
  const visibleItems = navigationItems.filter((item) =>
    item.id === "dashboard"
      ? true
      : item.roles.includes(role)
  );

  const roleLabel = role
    ? role.charAt(0) + role.slice(1).toLowerCase()
    : "Role unavailable";

  return (
    <aside className="sidebar">
      {/* Brand */}
      <div className="sidebar-header">
        <div className="sidebar-logo">E</div>

        <div className="sidebar-brand">
          <strong>EMPATH</strong>
          <span>Hospital Intelligence</span>
        </div>
      </div>

      {/* Navigation */}
      <div className="sidebar-section-label">
        WORKSPACE
      </div>

      <nav className="sidebar-nav">
        {visibleItems.map((item) => {
          const active = activePage === item.id;

          return (
            <button
              key={item.id}
              type="button"
              className={`sidebar-item ${active ? "active" : ""}`}
              onClick={() => onNavigate(item.id)}
              aria-current={active ? "page" : undefined}
            >
              <span className="sidebar-item-icon">
                {item.icon}
              </span>

              <span className="sidebar-item-label">
                {item.label}
              </span>
            </button>
          );
        })}
      </nav>

      {/* Signed-in user */}
      <div className="sidebar-bottom">
        <div className="sidebar-user">
          <div className="sidebar-user-avatar">
            {(user?.username || "U")
              .charAt(0)
              .toUpperCase()}
          </div>

          <div className="sidebar-user-info">
            <strong>
              {user?.full_name || user?.username || "User"}
            </strong>

            <span>{roleLabel}</span>
          </div>
        </div>
      </div>
    </aside>
  );
}

export default Sidebar;