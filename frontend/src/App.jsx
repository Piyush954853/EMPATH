import { useCallback, useEffect, useState } from "react";

import "./App.css";

import Sidebar from "./components/Sidebar";

import NotificationBell from "./components/NotificationBell";

import Dashboard from "./pages/Dashboard";

import Patients from "./pages/Patients";

import Cameras from "./pages/Cameras";

import Events from "./pages/Events";

import HospitalStructure from "./pages/HospitalStructure";

import Monitoring from "./pages/Monitoring";

import UserManagement from "./pages/UserManagement";

const API_URL = "http://127.0.0.1:8000";

// =========================================================

// API REQUEST

// =========================================================

async function apiRequest(endpoint, token, options = {}) {

  const response = await fetch(

    `${API_URL}${endpoint}`,

    {

      ...options,

      headers: {

        "Content-Type": "application/json",

        ...(token

          ? {

              Authorization: `Bearer ${token}`,

            }

          : {}),

        ...(options.headers || {}),

      },

    }

  );

  let data = null;

  try {

    data = await response.json();

  } catch {

    data = null;

  }

  if (!response.ok) {

    throw new Error(

      data?.detail ||

        data?.message ||

        `Request failed (${response.status})`

    );

  }

  return data;

}

// =========================================================

// LOGIN

// =========================================================

function Login({ onLogin }) {

  const [username, setUsername] = useState("");

  const [password, setPassword] = useState("");

  const [loading, setLoading] = useState(false);

  const [error, setError] = useState("");

  const handleLogin = async (event) => {

    event.preventDefault();

    setError("");

    setLoading(true);

    try {

      const data = await apiRequest(

        "/auth/login",

        null,

        {

          method: "POST",

          body: JSON.stringify({

            username,

            password,

          }),

        }

      );

      if (!data?.access_token) {

        throw new Error(

          "Login succeeded but no access token was returned."

        );

      }

      localStorage.setItem(

        "empath_token",

        data.access_token

      );

      onLogin(

        data.access_token

      );

    } catch (err) {

      setError(

        err instanceof Error

          ? err.message

          : "Unable to login."

      );

    } finally {

      setLoading(false);

    }

  };

  return (

    <div className="login-page">

      <div className="login-card">

        <div className="login-brand">

          <div className="brand-icon">

            E

          </div>

          <div>

            <h1>

              EMPATH

            </h1>

            <p>

              Hospital Intelligence Platform

            </p>

          </div>

        </div>

        <div className="login-heading">

          <h2>

            Welcome back

          </h2>

          <p>

            Sign in to access the EMPATH monitoring system.

          </p>

        </div>

        <form onSubmit={handleLogin}>

          <div className="form-group">

            <label htmlFor="username">

              Username

            </label>

            <input

              id="username"

              type="text"

              placeholder="Enter your username"

              value={username}

              onChange={(event) =>

                setUsername(event.target.value)

              }

              autoComplete="username"

              required

            />

          </div>

          <div className="form-group">

            <label htmlFor="password">

              Password

            </label>

            <input

              id="password"

              type="password"

              placeholder="Enter your password"

              value={password}

              onChange={(event) =>

                setPassword(event.target.value)

              }

              autoComplete="current-password"

              required

            />

          </div>

          {error && (

            <div className="error-message">

              {error}

            </div>

          )}

          <button

            type="submit"

            className="login-button"

            disabled={loading}

          >

            {loading

              ? "Signing in..."

              : "Sign in"}

          </button>

        </form>

        <div className="login-footer">

          <span>

            EMPATH v0.1.0

          </span>

          <span>

            Development Environment

          </span>

        </div>

      </div>

    </div>

  );

}

// =========================================================

// APPLICATION

// =========================================================

function Application({

  token,

  user,

  onLogout,

}) {

  const [

    activePage,

    setActivePage,

  ] = useState("dashboard");

  const [pendingAlertId, setPendingAlertId] = useState(null);

  const openAlertFromNotification = useCallback((alert) => {
    if (!alert || alert.id == null) return;
    setPendingAlertId(alert.id);
    setActivePage("monitoring");
  }, []);

  const clearPendingAlert = useCallback(() => setPendingAlertId(null), []);

  // Role-aware dashboard access. These checks control which UI requests are made;

  // backend permission checks remain the actual security boundary.

  const userRole = String(user?.role_name || "").trim().toUpperCase();

  const roleCanViewDashboard = [

    "ADMIN",

    "NURSE",

    "DOCTOR",

    "RESEARCHER",

  ].includes(userRole);

  const canViewPatientCameraStats = [

    "ADMIN",

    "NURSE",

    "DOCTOR",

  ].includes(userRole);

  const [stats, setStats] = useState({

    hospitals: "—",

    patients: "—",

    cameras: "—",

    events: "—",

  });

  const [

    loadingStats,

    setLoadingStats,

  ] = useState(true);

  const [

    refreshing,

    setRefreshing,

  ] = useState(false);

  const [error, setError] =

    useState("");

  const [

    lastUpdated,

    setLastUpdated,

  ] = useState(null);

  // -------------------------------------------------------

  // RESPONSE COUNT

  // -------------------------------------------------------

  const getCount = (data) => {

    if (Array.isArray(data)) {

      return data.length;

    }

    if (typeof data === "number") {

      return data;

    }

    if (

      data &&

      typeof data === "object"

    ) {

      if (

        typeof data.count === "number"

      ) {

        return data.count;

      }

      if (

        typeof data.total === "number"

      ) {

        return data.total;

      }

      if (

        Array.isArray(data.items)

      ) {

        return data.items.length;

      }

      if (

        Array.isArray(data.data)

      ) {

        return data.data.length;

      }

      if (

        Array.isArray(data.results)

      ) {

        return data.results.length;

      }

    }

    return "—";

  };

  // -------------------------------------------------------

  // LOAD DASHBOARD STATS

  // -------------------------------------------------------

  const loadDashboardData = useCallback(

    async (showRefresh = false) => {

      try {

        setError("");

        if (showRefresh) {

          setRefreshing(true);

        } else {

          setLoadingStats(true);

        }

        // Request only data appropriate to the authenticated role.

        // The backend must still validate all permissions and resource access.

        const requests = [];

        if (roleCanViewDashboard) {

          requests.push({

            key: "hospitals",

            endpoint: "/hospitals",

            label: "Hospitals",

          });

          if (canViewPatientCameraStats) {

            requests.push({

              key: "patients",

              endpoint: "/patients",

              label: "Patients",

            });

            requests.push({

              key: "cameras",

              endpoint: "/cameras",

              label: "Cameras",

            });

          }

          requests.push({

            key: "events",

            endpoint: "/events",

            label: "Events",

          });

        }

        const nextStats = {

          hospitals: "—",

          patients: "—",

          cameras: "—",

          events: "—",

        };

        if (requests.length === 0) {

          setStats(nextStats);

          setError("Dashboard data is not configured for this role.");

          setLastUpdated(new Date());

          return;

        }

        // A single 403 or server error should not discard all successful counts.

        const results = await Promise.allSettled(

          requests.map((request) =>

            apiRequest(request.endpoint, token)

          )

        );

        const failedResources = [];

        results.forEach((result, index) => {

          const request = requests[index];

          if (result.status === "fulfilled") {

            nextStats[request.key] = getCount(result.value);

          } else {

            failedResources.push(request.label);

            console.error(

              `Dashboard request failed for ${request.label}:`,

              result.reason

            );

          }

        });

        setStats(nextStats);

        setError(

          failedResources.length > 0

            ? `Some dashboard data could not be loaded: ${failedResources.join(", ")}.`

            : ""

        );

        setLastUpdated(new Date());

      } catch (err) {

        console.error("Dashboard data error:", err);

        setError(

          err instanceof Error

            ? err.message

            : "Unable to load dashboard data."

        );

      } finally {

        setLoadingStats(false);

        setRefreshing(false);

      }

    },

    [token, roleCanViewDashboard, canViewPatientCameraStats]

  );

  // INITIAL DATA

  // -------------------------------------------------------

  useEffect(() => {

    loadDashboardData();

  }, [

    loadDashboardData,

  ]);

  // -------------------------------------------------------

  // AUTO REFRESH

  // -------------------------------------------------------

  useEffect(() => {

    const interval = setInterval(

      () => {

        loadDashboardData(true);

      },

      30000

    );

    return () => {

      clearInterval(interval);

    };

  }, [

    loadDashboardData,

  ]);

  // -------------------------------------------------------

  // PAGE RENDER

  // -------------------------------------------------------

  const renderPage = () => {

    switch (activePage) {

      // ===================================================

      // DASHBOARD

      // ===================================================

      case "dashboard":

        return (

          <Dashboard

            stats={stats}

            loadingStats={

              loadingStats

            }

            refreshing={

              refreshing

            }

            lastUpdated={

              lastUpdated

            }

            error={error}

            onRefresh={() =>

              loadDashboardData(true)

            }

            onNavigate={setActivePage}
          />

        );

      // ===================================================

      // PATIENTS

      // ===================================================

      case "patients":

        return (

          <Patients

            token={token}

          />

        );

      // ===================================================

      // CAMERAS

      // ===================================================

      case "cameras":

        return (

          <Cameras

            token={token}

          />

        );

      // ===================================================

      // MONITORING

      // ===================================================

      case "monitoring":

        return (

          <Monitoring
            token={token}
            focusAlertId={pendingAlertId}
            onAlertFocused={clearPendingAlert}
          />

        );

      // ===================================================

      // EVENTS

      // ===================================================

      case "events":

        return (

          <Events

            token={token}

          />

        );

      // ===================================================

      // HOSPITAL STRUCTURE

      // ===================================================

      case "hospital":

        return (

          <HospitalStructure

            token={token}

          />

        );

      case "users":

        return <UserManagement token={token} />;

      // ===================================================

      // FALLBACK

      // ===================================================

      default:

        return (

          <Dashboard

            stats={stats}

            loadingStats={

              loadingStats

            }

            refreshing={

              refreshing

            }

            lastUpdated={

              lastUpdated

            }

            error={error}

            onRefresh={() =>

              loadDashboardData(true)

            }

            onNavigate={setActivePage}
          />

        );

    }

  };

  return (

    <div className="application-shell">

      <Sidebar

        activePage={

          activePage

        }

        onNavigate={

          setActivePage

        }

        user={user}

      />

      <div className="application-content">

        <header className="application-topbar">

          <div>

            <span className="topbar-label">

              EMPATH WORKSPACE

            </span>

            <strong>

              {activePage === "dashboard"

                ? "Dashboard"

                : activePage === "patients"

                ? "Patients"

                : activePage === "cameras"

                ? "Cameras"

                : activePage === "monitoring"

                ? "Monitoring"

                : activePage === "events"

                ? "Events"

                 : activePage === "users"

                ? "User Management"

                : "Hospital Structure"}

            </strong>

          </div>

          <div className="empath-topbar-actions">
            <NotificationBell
              token={token}
              user={user}
              onOpenAlert={openAlertFromNotification}
            />
            <button
              type="button"
              className="topbar-logout"
              onClick={onLogout}
            >
              Logout
            </button>
          </div>

        </header>

        {renderPage()}

        <footer className="dashboard-footer">

          <span>

            EMPATH v0.1.0

          </span>

          <span>

            Hospital Intelligence Platform

          </span>

        </footer>

      </div>

    </div>

  );

}

// =========================================================

// ROOT

// =========================================================

function App() {

  const [

    token,

    setToken,

  ] = useState(

    localStorage.getItem(

      "empath_token"

    )

  );

  const [

    user,

    setUser,

  ] = useState(null);

  const [

    checkingSession,

    setCheckingSession,

  ] = useState(

    Boolean(token)

  );

  // -------------------------------------------------------

  // VERIFY EXISTING SESSION

  // -------------------------------------------------------

  useEffect(() => {

    if (!token) {

      setCheckingSession(false);

      return;

    }

    const verifySession =

      async () => {

        try {

          const data =

            await apiRequest(

              "/auth/me",

              token

            );

          setUser(data);

        } catch {

          localStorage.removeItem(

            "empath_token"

          );

          setToken(null);

          setUser(null);

        } finally {

          setCheckingSession(false);

        }

      };

    verifySession();

  }, [token]);

  // -------------------------------------------------------

  // LOGIN COMPLETE

  // -------------------------------------------------------

  const handleLogin =

    async (newToken) => {

      try {

        const data =

          await apiRequest(

            "/auth/me",

            newToken

          );

        setUser(data);

        setToken(newToken);

      } catch {

        localStorage.removeItem(

          "empath_token"

        );

        setToken(null);

        setUser(null);

      }

    };

  // -------------------------------------------------------

  // LOGOUT

  // -------------------------------------------------------

  const handleLogout = () => {

    localStorage.removeItem(

      "empath_token"

    );

    setToken(null);

    setUser(null);

  };

  // -------------------------------------------------------

  // SESSION CHECK

  // -------------------------------------------------------

  if (checkingSession) {

    return (

      <div className="dashboard-loading">

        <div className="loading-card">

          <div className="loading-spinner" />

          <h2>

            Verifying EMPATH session...

          </h2>

          <p>

            Please wait.

          </p>

        </div>

      </div>

    );

  }

  // -------------------------------------------------------

  // APPLICATION

  // -------------------------------------------------------

  if (

    token &&

    user

  ) {

    return (

      <Application

        token={token}

        user={user}

        onLogout={

          handleLogout

        }

      />

    );

  }

  // -------------------------------------------------------

  // LOGIN

  // -------------------------------------------------------

  return (

    <Login

      onLogin={

        handleLogin

      }

    />

  );

}

export default App;
