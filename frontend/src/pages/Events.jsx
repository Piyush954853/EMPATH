import { useEffect, useMemo, useState } from "react";

const API_URL = "http://127.0.0.1:8000";

/**
 * Read structured event metadata from the API while remaining compatible
 * with older responses that only include metadata_json.
 */
function getEventMetadata(event) {
  if (
    event?.metadata &&
    typeof event.metadata === "object" &&
    !Array.isArray(event.metadata) &&
    Object.keys(event.metadata).length > 0
  ) {
    return event.metadata;
  }

  const rawMetadata = event?.metadata_json;

  if (
    rawMetadata &&
    typeof rawMetadata === "object" &&
    !Array.isArray(rawMetadata)
  ) {
    return rawMetadata;
  }

  if (typeof rawMetadata !== "string" || !rawMetadata.trim()) {
    return event?.metadata &&
      typeof event.metadata === "object" &&
      !Array.isArray(event.metadata)
      ? event.metadata
      : {};
  }

  try {
    const parsedMetadata = JSON.parse(rawMetadata);

    return parsedMetadata &&
      typeof parsedMetadata === "object" &&
      !Array.isArray(parsedMetadata)
      ? parsedMetadata
      : {};
  } catch {
    // Malformed legacy metadata should not break the Events page.
    return {};
  }
}

/** Convert snake_case metadata keys into readable labels. */
function formatMetadataLabel(key) {
  return String(key)
    .replace(/_/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

/** Format common AI/video metadata values while preserving unknown values. */
function formatMetadataValue(key, value) {
  if (value === null || value === undefined) {
    return "—";
  }

  if (key === "frame_received_at_utc") {
    const date = new Date(value);
    return Number.isNaN(date.getTime())
      ? String(value)
      : date.toLocaleString();
  }

  if (key === "timestamp_seconds") {
    const seconds = Number(value);
    return Number.isFinite(seconds)
      ? `${seconds.toFixed(2)} s`
      : String(value);
  }

  if (key === "ai_confidence") {
    const confidence = Number(value);
    return Number.isFinite(confidence)
      ? `${Math.round(confidence * 100)}%`
      : String(value);
  }

  if (key === "body_angle") {
    const angle = Number(value);
    return Number.isFinite(angle)
      ? `${angle.toFixed(1)}°`
      : String(value);
  }

  if (key === "movement_score") {
    const score = Number(value);
    return Number.isFinite(score)
      ? score.toFixed(3)
      : String(value);
  }

  if (typeof value === "object") {
    return JSON.stringify(value);
  }

  return String(value);
}

function Events({ token }) {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [search, setSearch] = useState("");
  const [severityFilter, setSeverityFilter] = useState("all");
  const [sourceFilter, setSourceFilter] = useState("all");

  const loadEvents = async () => {
    setLoading(true);
    setError("");

    try {
      const response = await fetch(
        `${API_URL}/events`,
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
            data?.message ||
            `Unable to load events (${response.status}).`
        );
      }

      setEvents(
        Array.isArray(data)
          ? data
          : []
      );

    } catch (err) {

      setError(
        err instanceof Error
          ? err.message
          : "Unable to load events."
      );

    } finally {

      setLoading(false);

    }
  };


  useEffect(() => {
    loadEvents();
  }, [token]);


  const filteredEvents = useMemo(() => {

    const normalizedSearch =
      search.trim().toLowerCase();

    return events.filter((event) => {

      // Include event metadata in search so staff can find a frame,
      // live session, video filename, or analysis mode when available.
      const metadataSearchText = JSON.stringify(
        getEventMetadata(event)
      ).toLowerCase();

      const matchesSearch =
        !normalizedSearch ||
        String(event.id)
          .toLowerCase()
          .includes(normalizedSearch) ||
        event.event_type
          ?.toLowerCase()
          .includes(normalizedSearch) ||
        event.description
          ?.toLowerCase()
          .includes(normalizedSearch) ||
        event.status
          ?.toLowerCase()
          .includes(normalizedSearch) ||
        metadataSearchText.includes(normalizedSearch);

      const matchesSeverity =
        severityFilter === "all" ||
        event.severity
          ?.toLowerCase() ===
          severityFilter;

      const matchesSource =
        sourceFilter === "all" ||
        event.source_type
          ?.toLowerCase() ===
          sourceFilter;

      return (
        matchesSearch &&
        matchesSeverity &&
        matchesSource
      );
    });

  }, [
    events,
    search,
    severityFilter,
    sourceFilter,
  ]);


  const severityOptions = useMemo(() => {

    return [
      ...new Set(
        events
          .map((event) =>
            event.severity?.toLowerCase()
          )
          .filter(Boolean)
      ),
    ];

  }, [events]);


  const sourceOptions = useMemo(() => {

    return [
      ...new Set(
        events
          .map((event) =>
            event.source_type?.toLowerCase()
          )
          .filter(Boolean)
      ),
    ];

  }, [events]);


  const highSeverityCount =
    events.filter(
      (event) =>
        event.severity?.toLowerCase() ===
        "high"
    ).length;


  const detectedCount =
    events.filter(
      (event) =>
        event.status?.toLowerCase() ===
        "detected"
    ).length;


  const formatDateTime = (value) => {

    if (!value) {
      return "—";
    }

    const date = new Date(value);

    if (
      Number.isNaN(date.getTime())
    ) {
      return value;
    }

    return date.toLocaleString();
  };


  const formatConfidence = (value) => {

    if (
      value === null ||
      value === undefined
    ) {
      return "—";
    }

    return `${Math.round(
      value * 100
    )}%`;
  };


  const getSeverityClass = (severity) => {

    const normalized =
      severity?.toLowerCase();

    if (
      normalized === "critical" ||
      normalized === "high" ||
      normalized === "medium" ||
      normalized === "low"
    ) {
      return normalized;
    }

    return "unknown";
  };


  return (
    <main className="events-page">

      {/* =====================================================
          HEADER
      ===================================================== */}

      <section className="events-header">

        <div className="events-header-content">

          <span className="events-eyebrow">
            EVENT INTELLIGENCE
          </span>

          <h2>
            Monitoring Events
          </h2>

          <p>
            Review events generated by
            monitoring, analysis, manual
            input, and replay sources.
          </p>

        </div>


        <button
          type="button"
          className="events-refresh"
          onClick={loadEvents}
          disabled={loading}
        >
          {loading
            ? "Refreshing..."
            : "Refresh"}
        </button>

      </section>


      {/* =====================================================
          ERROR
      ===================================================== */}

      {error && (
        <div className="events-error">

          <div>
            <strong>
              Unable to load events
            </strong>

            <span>
              {error}
            </span>
          </div>

          <button
            type="button"
            onClick={loadEvents}
          >
            Retry
          </button>

        </div>
      )}


      {/* =====================================================
          SUMMARY
      ===================================================== */}

      <section className="event-summary-grid">

        <div className="event-summary-card">

          <span>
            Total Events
          </span>

          <strong>
            {events.length}
          </strong>

        </div>


        <div className="event-summary-card">

          <span>
            Visible Events
          </span>

          <strong>
            {filteredEvents.length}
          </strong>

        </div>


        <div className="event-summary-card high-severity">

          <span>
            High Severity
          </span>

          <strong>
            {highSeverityCount}
          </strong>

        </div>


        <div className="event-summary-card">

          <span>
            Detected
          </span>

          <strong>
            {detectedCount}
          </strong>

        </div>

      </section>


      {/* =====================================================
          EVENT TABLE
      ===================================================== */}

      <section className="event-table-card">

        <div className="event-table-toolbar">

          <div className="event-search">

            <input
              type="text"
              placeholder="Search event ID, type, status, description..."
              value={search}
              onChange={(event) =>
                setSearch(
                  event.target.value
                )
              }
            />

          </div>


          <div className="event-filters">

            <select
              value={severityFilter}
              onChange={(event) =>
                setSeverityFilter(
                  event.target.value
                )
              }
              aria-label="Filter by severity"
            >

              <option value="all">
                All severities
              </option>

              {severityOptions.map(
                (severity) => (
                  <option
                    key={severity}
                    value={severity}
                  >
                    {severity}
                  </option>
                )
              )}

            </select>


            <select
              value={sourceFilter}
              onChange={(event) =>
                setSourceFilter(
                  event.target.value
                )
              }
              aria-label="Filter by source"
            >

              <option value="all">
                All sources
              </option>

              {sourceOptions.map(
                (source) => (
                  <option
                    key={source}
                    value={source}
                  >
                    {source}
                  </option>
                )
              )}

            </select>

          </div>

        </div>


        {loading ? (

          <div className="event-empty">

            <div className="event-empty-icon">
              E
            </div>

            <h3>
              Loading events
            </h3>

            <p>
              Retrieving authorized monitoring
              events from EMPATH.
            </p>

          </div>

        ) : filteredEvents.length === 0 ? (

          <div className="event-empty">

            <div className="event-empty-icon">
              —
            </div>

            <h3>
              No matching events
            </h3>

            <p>
              No events match the current
              search and filter settings.
            </p>

          </div>

        ) : (

          <div className="event-table-wrapper">

            <table className="event-table">

              <thead>

                <tr>

                  <th>
                    ID
                  </th>

                  <th>
                    Event Type
                  </th>

                  <th>
                    Severity
                  </th>

                  <th>
                    Status
                  </th>

                  <th>
                    Source
                  </th>

                  <th>
                    Camera
                  </th>

                  <th>
                    Patient
                  </th>

                  <th>
                    Confidence
                  </th>

                  <th>
                    AI Context
                  </th>

                  <th>
                    Detected At
                  </th>

                </tr>

              </thead>


              <tbody>

                {filteredEvents.map(
                  (event) => {

                    const severityClass =
                      getSeverityClass(
                        event.severity
                      );

                    // Metadata may arrive as a structured `metadata` object
                    // or as the legacy JSON string `metadata_json`.
                    const metadata = getEventMetadata(event);
                    const metadataEntries = Object.entries(metadata).filter(
                      ([, value]) => value !== null && value !== undefined && value !== ""
                    );
                    const hasAIContext = metadataEntries.length > 0;

                    return (
                      <tr
                        key={event.id}
                      >

                        <td>
                          <span className="event-id">
                            #{event.id}
                          </span>
                        </td>


                        <td>
                          <span className="event-type">
                            {event.event_type ||
                              "—"}
                          </span>
                        </td>


                        <td>

                          <span
                            className={`event-badge ${severityClass}`}
                          >
                            {event.severity ||
                              "unknown"}
                          </span>

                        </td>


                        <td>

                          <span className="event-status">

                            {event.status ||
                              "—"}

                          </span>

                        </td>


                        <td>

                          <span className="camera-source">

                            <span className="camera-source-dot" />

                            {event.source_type ||
                              "—"}

                          </span>

                        </td>


                        <td>

                          {event.camera_id !==
                            null &&
                          event.camera_id !==
                            undefined ? (
                            `#${event.camera_id}`
                          ) : (
                            <span className="event-muted">
                              —
                            </span>
                          )}

                        </td>


                        <td>

                          {event.patient_id !==
                            null &&
                          event.patient_id !==
                            undefined ? (
                            `#${event.patient_id}`
                          ) : (
                            <span className="event-muted">
                              —
                            </span>
                          )}

                        </td>


                        <td>

                          <span className="event-confidence">

                            {formatConfidence(
                              event.confidence
                            )}

                          </span>

                        </td>


                        <td>

                          {hasAIContext ? (
                            <details className="event-ai-context">
                              <summary>
                                {metadata.analysis_mode
                                  ? String(metadata.analysis_mode)
                                  : "View metadata"}
                                {metadata.frame_number !== null &&
                                metadata.frame_number !== undefined
                                  ? ` · Frame ${metadata.frame_number}`
                                  : ""}
                                {metadata.timestamp_seconds !== null &&
                                metadata.timestamp_seconds !== undefined &&
                                Number.isFinite(Number(metadata.timestamp_seconds))
                                  ? ` · ${Number(metadata.timestamp_seconds).toFixed(2)} s`
                                  : ""}
                              </summary>

                              <div className="event-ai-context-details">
                                {metadataEntries.map(([key, value]) => (
                                  <div key={key}>
                                    <strong>{formatMetadataLabel(key)}:</strong>{" "}
                                    <span>{formatMetadataValue(key, value)}</span>
                                  </div>
                                ))}
                              </div>
                            </details>
                          ) : (
                            <span className="event-muted">—</span>
                          )}

                        </td>


                        <td>

                          <span className="event-muted">

                            {formatDateTime(
                              event.detected_at
                            )}

                          </span>

                        </td>

                      </tr>
                    );
                  }
                )}

              </tbody>

            </table>

          </div>

        )}

      </section>

    </main>
  );
}

export default Events;