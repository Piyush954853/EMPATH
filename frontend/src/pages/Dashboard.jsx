import "./Dashboard.css";

function DashboardIcon({ name, size = 20 }) {
  let graphic;

  switch (name) {
    case "hospital":
      graphic = (
        <>
          <rect x="4" y="3" width="16" height="18" rx="2" />
          <path d="M9 21v-4h6v4M12 7v6M9 10h6M8 15h.01M16 15h.01" />
        </>
      );
      break;
    case "patients":
      graphic = (
        <>
          <circle cx="12" cy="8" r="3.5" />
          <path d="M5 21v-1a7 7 0 0 1 14 0v1" />
        </>
      );
      break;
    case "cameras":
      graphic = (
        <>
          <path d="M4 7.5h3l2-3h6l2 3h3A2 2 0 0 1 22 9.5v9a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-9a2 2 0 0 1 2-2Z" />
          <circle cx="12" cy="13.5" r="3.5" />
        </>
      );
      break;
    case "events":
      graphic = (
        <>
          <path d="M3 12h4l3-7 4 14 3-7h4" />
          <path d="M5 3h14a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z" opacity=".25" />
        </>
      );
      break;
    case "refresh":
      graphic = (
        <>
          <path d="M20 7v5h-5M4 17v-5h5" />
          <path d="M5.6 9A7 7 0 0 1 17.5 6L20 12M4 12l2.5 6A7 7 0 0 0 18.4 15" />
        </>
      );
      break;
    case "arrow":
      graphic = <><path d="M5 12h14M13 6l6 6-6 6" /></>;
      break;
    case "shield":
      graphic = <><path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11Z" /><path d="m9 12 2 2 4-4" /></>;
      break;
    case "clock":
      graphic = <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>;
      break;
    case "activity":
      graphic = <><path d="M3 12h4l3-8 4 16 3-8h4" /></>;
      break;
    case "chevron":
      graphic = <><path d="m9 18 6-6-6-6" /></>;
      break;
    default:
      graphic = <><circle cx="12" cy="12" r="9" /><path d="M12 8v4M12 16h.01" /></>;
  }

  return (
    <svg
      aria-hidden="true"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {graphic}
    </svg>
  );
}

function formatLastUpdated(value) {
  if (!value) return "Waiting for first sync";

  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return "Recently updated";

  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

const metricCards = [
  {
    key: "hospitals",
    label: "Hospitals",
    description: "Connected facilities",
    icon: "hospital",
    tone: "blue",
  },
  {
    key: "patients",
    label: "Patients",
    description: "Patient records available",
    icon: "patients",
    tone: "teal",
  },
  {
    key: "cameras",
    label: "Cameras",
    description: "Registered devices",
    icon: "cameras",
    tone: "violet",
  },
  {
    key: "events",
    label: "Events",
    description: "Recorded monitoring events",
    icon: "events",
    tone: "amber",
  },
];

const modules = [
  {
    key: "hospital",
    title: "Hospital structure",
    description: "Explore facilities, departments, wards and rooms.",
    detail: "FACILITY MANAGEMENT",
    icon: "hospital",
    tone: "blue",
    page: "hospital",
  },
  {
    key: "patients",
    title: "Patients",
    description: "Review authorized patient records and bed assignments.",
    detail: "PATIENT DIRECTORY",
    icon: "patients",
    tone: "teal",
    page: "patients",
  },
  {
    key: "cameras",
    title: "Camera resources",
    description: "Manage registered devices and room-level access.",
    detail: "DEVICE MANAGEMENT",
    icon: "cameras",
    tone: "violet",
    page: "cameras",
  },
  {
    key: "events",
    title: "Monitoring events",
    description: "Review recorded events and follow-up status.",
    detail: "EVENT REVIEW",
    icon: "events",
    tone: "amber",
    page: "events",
  },
];

function Dashboard({
  stats = {},
  loadingStats = false,
  refreshing = false,
  lastUpdated = null,
  error = "",
  onRefresh,
  onNavigate,
}) {
  const hasError = Boolean(error);
  const workspaceStatus = hasError
    ? "Needs attention"
    : loadingStats
      ? "Checking connection"
      : "Workspace connected";

  const handleNavigate = (page) => {
    if (typeof onNavigate === "function") onNavigate(page);
  };

  return (
    <main className="ep-dashboard">
      <section className="ep-dashboard__page-heading">
        <div>
          <div className="ep-dashboard__breadcrumb">
            <span>WORKSPACE</span>
            <DashboardIcon name="chevron" size={13} />
            <span>OVERVIEW</span>
          </div>
          <h1>Hospital command center</h1>
          <p>One clear view of your hospital resources and monitoring activity.</p>
        </div>

        <div className="ep-dashboard__toolbar">
          <div className={`ep-dashboard__connection ${hasError ? "is-error" : ""}`}>
            <span className="ep-dashboard__connection-dot" />
            <span>{workspaceStatus}</span>
          </div>
          <button
            type="button"
            className="ep-dashboard__refresh"
            onClick={onRefresh}
            disabled={refreshing || loadingStats}
          >
            <DashboardIcon name="refresh" size={17} />
            <span>{refreshing ? "Refreshing…" : "Refresh data"}</span>
          </button>
        </div>
      </section>

      {hasError && (
        <div className="ep-dashboard__error" role="alert">
          <div className="ep-dashboard__error-icon">
            <DashboardIcon name="activity" size={19} />
          </div>
          <div>
            <strong>Some dashboard data could not be loaded</strong>
            <p>{error}</p>
          </div>
        </div>
      )}

      <section className="ep-dashboard__hero" aria-label="EMPATH overview">
        <div className="ep-dashboard__hero-content">
          <div className="ep-dashboard__hero-kicker">
            <span className="ep-dashboard__hero-kicker-dot" />
            HOSPITAL INTELLIGENCE PLATFORM
          </div>
          <h2>Monitor with clarity.<br />Respond with confidence.</h2>
          <p>
            Access authorized resources, review monitoring events, and keep
            alert response workflows moving from one workspace.
          </p>
          <button
            type="button"
            className="ep-dashboard__hero-action"
            onClick={() => handleNavigate("monitoring")}
          >
            Open live monitoring
            <DashboardIcon name="arrow" size={18} />
          </button>
        </div>

        <div className="ep-dashboard__hero-visual" aria-hidden="true">
          <div className="ep-dashboard__orbit ep-dashboard__orbit--outer" />
          <div className="ep-dashboard__orbit ep-dashboard__orbit--inner" />
          <div className="ep-dashboard__hero-glow" />
          <div className="ep-dashboard__hero-mark">
            <DashboardIcon name="activity" size={52} />
          </div>
          <div className="ep-dashboard__hero-chip ep-dashboard__hero-chip--top">
            <span className="ep-dashboard__mini-dot" />
            AUTHORIZED ACCESS
          </div>
          <div className="ep-dashboard__hero-chip ep-dashboard__hero-chip--bottom">
            <DashboardIcon name="shield" size={16} />
            Human-reviewed safety signals
          </div>
        </div>
      </section>

      <section className="ep-dashboard__metrics" aria-label="Resource summary">
        {metricCards.map((metric) => (
          <article
            key={metric.key}
            className={`ep-dashboard__metric ep-dashboard__metric--${metric.tone}`}
          >
            <div className="ep-dashboard__metric-top">
              <div className="ep-dashboard__metric-icon">
                <DashboardIcon name={metric.icon} size={21} />
              </div>
              <span className="ep-dashboard__metric-label">{metric.label}</span>
              <span className="ep-dashboard__metric-indicator" aria-hidden="true">
                <DashboardIcon name="arrow" size={15} />
              </span>
            </div>
            <div className="ep-dashboard__metric-value">
              {loadingStats ? <span className="ep-dashboard__skeleton" /> : (stats?.[metric.key] ?? "—")}
            </div>
            <div className="ep-dashboard__metric-bottom">
              <span>{metric.description}</span>
              <span className="ep-dashboard__metric-bar"><i /></span>
            </div>
          </article>
        ))}
      </section>

      <section className="ep-dashboard__lower-grid">
        <div className="ep-dashboard__panel ep-dashboard__modules-panel">
          <div className="ep-dashboard__panel-heading">
            <div>
              <span className="ep-dashboard__section-kicker">YOUR WORKSPACE</span>
              <h2>Explore modules</h2>
              <p>Jump directly to the area you need.</p>
            </div>
            <span className="ep-dashboard__panel-count">04 MODULES</span>
          </div>

          <div className="ep-dashboard__module-grid">
            {modules.map((module) => (
              <button
                key={module.key}
                type="button"
                className={`ep-dashboard__module ep-dashboard__module--${module.tone}`}
                onClick={() => handleNavigate(module.page)}
                aria-label={`Open ${module.title}`}
              >
                <div className="ep-dashboard__module-topline">
                  <div className="ep-dashboard__module-icon">
                    <DashboardIcon name={module.icon} size={22} />
                  </div>
                  <span className="ep-dashboard__module-arrow">
                    <DashboardIcon name="arrow" size={16} />
                  </span>
                </div>
                <span className="ep-dashboard__module-detail">{module.detail}</span>
                <h3>{module.title}</h3>
                <p>{module.description}</p>
              </button>
            ))}
          </div>
        </div>

        <aside className="ep-dashboard__panel ep-dashboard__status-panel">
          <div className="ep-dashboard__panel-heading">
            <div>
              <span className="ep-dashboard__section-kicker">SYSTEM SNAPSHOT</span>
              <h2>Connection overview</h2>
              <p>Current session and data refresh status.</p>
            </div>
            <div className={`ep-dashboard__status-symbol ${hasError ? "is-error" : ""}`}>
              <DashboardIcon name={hasError ? "activity" : "shield"} size={22} />
            </div>
          </div>

          <div className="ep-dashboard__status-list">
            <div className="ep-dashboard__status-row">
              <span className="ep-dashboard__status-row-icon"><DashboardIcon name="activity" size={17} /></span>
              <div className="ep-dashboard__status-row-copy">
                <strong>API data requests</strong>
                <span>{hasError ? "One or more requests failed" : loadingStats ? "Loading resource data" : "Last request cycle completed"}</span>
              </div>
              <span className={`ep-dashboard__status-pill ${hasError ? "is-error" : loadingStats ? "is-pending" : ""}`}>
                {hasError ? "Check" : loadingStats ? "Loading" : "Ready"}
              </span>
            </div>
            <div className="ep-dashboard__status-row">
              <span className="ep-dashboard__status-row-icon"><DashboardIcon name="shield" size={17} /></span>
              <div className="ep-dashboard__status-row-copy">
                <strong>Authenticated workspace</strong>
                <span>You're viewing the protected application area.</span>
              </div>
              <span className="ep-dashboard__status-pill">Active</span>
            </div>
            <div className="ep-dashboard__status-row">
              <span className="ep-dashboard__status-row-icon"><DashboardIcon name="clock" size={17} /></span>
              <div className="ep-dashboard__status-row-copy">
                <strong>Last data refresh</strong>
                <span>{formatLastUpdated(lastUpdated)}</span>
              </div>
            </div>
          </div>

          <div className="ep-dashboard__note">
            <span className="ep-dashboard__note-icon"><DashboardIcon name="shield" size={17} /></span>
            <p>
              AI-generated safety indicators are experimental and must be
              reviewed by authorized staff before operational decisions.
            </p>
          </div>
        </aside>
      </section>

      <footer className="ep-dashboard__footer">
        <span><strong>EMPATH</strong> · Hospital Intelligence Platform</span>
        <span>Operational overview <i /> Resource data is refreshed automatically.</span>
      </footer>
    </main>
  );
}

export default Dashboard;
