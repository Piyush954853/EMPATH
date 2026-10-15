import { useCallback, useEffect, useMemo, useState } from "react";

const API_URL = "http://127.0.0.1:8000";


/* =========================================================
   PATIENTS PAGE
========================================================= */

function Patients({ token }) {
  const [patients, setPatients] = useState([]);

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const [error, setError] = useState("");

  const [search, setSearch] = useState("");

  const [filter, setFilter] = useState("all");


  /* ---------------------------------------------------------
     LOAD PATIENTS
  --------------------------------------------------------- */

  const loadPatients = useCallback(
    async (manualRefresh = false) => {

      if (manualRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }

      setError("");

      try {

        const response = await fetch(
          `${API_URL}/patients`,
          {
            headers: {
              Authorization: `Bearer ${token}`,
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
              `Unable to load patients (${response.status})`
          );

        }


        if (!Array.isArray(data)) {

          throw new Error(
            "Unexpected patient API response."
          );

        }


        setPatients(data);

      } catch (err) {

        console.error(
          "Patients loading error:",
          err
        );

        setError(
          err instanceof Error
            ? err.message
            : "Unable to load patients."
        );

      } finally {

        setLoading(false);
        setRefreshing(false);

      }

    },
    [token]
  );


  /* ---------------------------------------------------------
     INITIAL LOAD
  --------------------------------------------------------- */

  useEffect(() => {

    loadPatients();

  }, [loadPatients]);


  /* ---------------------------------------------------------
     FILTER PATIENTS
  --------------------------------------------------------- */

  const filteredPatients = useMemo(() => {

    const normalizedSearch =
      search.trim().toLowerCase();


    return patients.filter((patient) => {

      const matchesSearch =
        normalizedSearch === "" ||
        patient.name
          ?.toLowerCase()
          .includes(normalizedSearch) ||
        patient.patient_code
          ?.toLowerCase()
          .includes(normalizedSearch);


      const matchesFilter =
        filter === "all" ||
        (filter === "active" && patient.is_active) ||
        (filter === "inactive" && !patient.is_active);


      return (
        matchesSearch &&
        matchesFilter
      );

    });

  }, [patients, search, filter]);


  /* ---------------------------------------------------------
     COUNTS
  --------------------------------------------------------- */

  const activeCount =
    patients.filter(
      (patient) => patient.is_active
    ).length;


  const inactiveCount =
    patients.filter(
      (patient) => !patient.is_active
    ).length;


  /* ---------------------------------------------------------
     LOADING
  --------------------------------------------------------- */

  if (loading) {

    return (
      <main className="workspace-page">

        <div className="workspace-loading">

          <div className="loading-spinner" />

          <h2>
            Loading patients...
          </h2>

          <p>
            Retrieving patient records from EMPATH.
          </p>

        </div>

      </main>
    );

  }


  /* ---------------------------------------------------------
     PAGE
  --------------------------------------------------------- */

  return (
    <main className="workspace-page">

      {/* =====================================================
          HEADER
      ===================================================== */}

      <section className="workspace-header">

        <div>

          <span className="section-eyebrow">
            PATIENT MANAGEMENT
          </span>

          <h2>
            Patients
          </h2>

          <p>
            View patients available within your authorized
            monitoring scope.
          </p>

        </div>


        <button
          type="button"
          className="refresh-button"
          onClick={() => loadPatients(true)}
          disabled={refreshing}
        >
          {refreshing
            ? "Refreshing..."
            : "Refresh patients"}
        </button>

      </section>


      {/* =====================================================
          ERROR
      ===================================================== */}

      {error && (

        <div className="workspace-error">

          <strong>
            Unable to load patient records
          </strong>

          <span>
            {error}
          </span>

          <button
            type="button"
            onClick={() => loadPatients(true)}
          >
            Retry
          </button>

        </div>

      )}


      {/* =====================================================
          SUMMARY
      ===================================================== */}

      <section className="summary-grid">

        <div className="summary-card">

          <span>
            TOTAL PATIENTS
          </span>

          <strong>
            {patients.length}
          </strong>

        </div>


        <div className="summary-card">

          <span>
            ACTIVE
          </span>

          <strong>
            {activeCount}
          </strong>

        </div>


        <div className="summary-card">

          <span>
            INACTIVE
          </span>

          <strong>
            {inactiveCount}
          </strong>

        </div>

      </section>


      {/* =====================================================
          PATIENT LIST
      ===================================================== */}

      <section className="workspace-card">

        <div className="workspace-card-header">

          <div>

            <span className="panel-eyebrow">
              PATIENT DIRECTORY
            </span>

            <h3>
              Authorized Patients
            </h3>

          </div>

          <span className="record-count">
            {filteredPatients.length}{" "}
            {filteredPatients.length === 1
              ? "record"
              : "records"}
          </span>

        </div>


        {/* ---------------------------------------------------
            FILTERS
        --------------------------------------------------- */}

        <div className="patient-filters">

          <div className="search-wrapper">

            <input
              type="search"
              placeholder="Search by name or patient code..."
              value={search}
              onChange={(event) =>
                setSearch(event.target.value)
              }
            />

          </div>


          <div className="filter-buttons">

            <button
              type="button"
              className={
                filter === "all"
                  ? "filter-button active"
                  : "filter-button"
              }
              onClick={() => setFilter("all")}
            >
              All
            </button>


            <button
              type="button"
              className={
                filter === "active"
                  ? "filter-button active"
                  : "filter-button"
              }
              onClick={() => setFilter("active")}
            >
              Active
            </button>


            <button
              type="button"
              className={
                filter === "inactive"
                  ? "filter-button active"
                  : "filter-button"
              }
              onClick={() => setFilter("inactive")}
            >
              Inactive
            </button>

          </div>

        </div>


        {/* ---------------------------------------------------
            EMPTY STATE
        --------------------------------------------------- */}

        {filteredPatients.length === 0 && (

          <div className="patient-empty">

            <div className="patient-empty-icon">
              P
            </div>

            <h3>
              No patients found
            </h3>

            <p>
              {patients.length === 0
                ? "No patient records are currently available within your authorized scope."
                : "No patients match the current search or filter."}
            </p>

          </div>

        )}


        {/* ---------------------------------------------------
            PATIENT TABLE
        --------------------------------------------------- */}

        {filteredPatients.length > 0 && (

          <div className="patient-table-wrapper">

            <table className="patient-table">

              <thead>

                <tr>

                  <th>
                    Patient
                  </th>

                  <th>
                    Patient Code
                  </th>

                  <th>
                    Bed
                  </th>

                  <th>
                    Status
                  </th>

                  <th>
                    Patient ID
                  </th>

                </tr>

              </thead>


              <tbody>

                {filteredPatients.map(
                  (patient) => (

                    <tr key={patient.id}>

                      <td>

                        <div className="patient-name-cell">

                          <div className="patient-avatar">
                            {patient.name
                              ?.charAt(0)
                              .toUpperCase() || "P"}
                          </div>

                          <div>

                            <strong>
                              {patient.name}
                            </strong>

                            <span>
                              Monitored patient
                            </span>

                          </div>

                        </div>

                      </td>


                      <td>

                        <span className="patient-code">
                          {patient.patient_code}
                        </span>

                      </td>


                      <td>
                        Bed {patient.bed_id}
                      </td>


                      <td>

                        <span
                          className={
                            patient.is_active
                              ? "patient-status active"
                              : "patient-status inactive"
                          }
                        >
                          <span />
                          {patient.is_active
                            ? "Active"
                            : "Inactive"}
                        </span>

                      </td>


                      <td>
                        #{patient.id}
                      </td>

                    </tr>

                  )
                )}

              </tbody>

            </table>

          </div>

        )}

      </section>

    </main>
  );
}

export default Patients;