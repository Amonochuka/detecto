import { useState, useEffect, useCallback } from "react";

export default function History() {
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [dateFilter, setDateFilter] = useState("");
  const [limit, setLimit] = useState(50);

  const fetchHistory = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (dateFilter) params.set("date", dateFilter);
      params.set("limit", limit);
      const res = await fetch(`/api/history?${params}`);
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || "Failed to fetch history.");
        return;
      }
      setRecords(data.detections || []);
    } catch {
      setError("Could not connect to the backend. Make sure the server is running on port 8000.");
    } finally {
      setLoading(false);
    }
  }, [dateFilter, limit]);

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  async function handleReset() {
    if (!window.confirm("Clear all detection history? This cannot be undone.")) return;
    try {
      await fetch("/api/reset", { method: "POST" });
      setRecords([]);
    } catch {
      setError("Failed to clear history.");
    }
  }

  function confBadge(conf) {
    const pct = (conf * 100).toFixed(1);
    let cls = "conf-low";
    if (conf >= 0.7) cls = "conf-high";
    else if (conf >= 0.4) cls = "conf-medium";
    return (
      <span className={`conf-badge ${cls}`}>{pct}%</span>
    );
  }

  function formatTime(iso) {
    try {
      const d = new Date(iso);
      return d.toLocaleString();
    } catch {
      return iso;
    }
  }

  return (
    <div>
      <div className="page-header">
        <h1>History View</h1>
        <p>Review past detections and monitor activity over time.</p>
      </div>

      {error && <div className="error-banner">{error}</div>}

      <div className="filters-bar">
        <label style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
          Date:
          <input
            type="date"
            value={dateFilter}
            onChange={(e) => setDateFilter(e.target.value)}
            style={{ marginLeft: "0.5rem" }}
          />
        </label>
        <label style={{ fontSize: "0.85rem", color: "var(--text-muted)" }}>
          Limit:
          <input
            type="number"
            min="1"
            max="500"
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value) || 50)}
            style={{ marginLeft: "0.5rem", width: "80px" }}
          />
        </label>
        <button className="btn btn-outline" onClick={fetchHistory}>
          Refresh
        </button>
        <button className="btn btn-danger" onClick={handleReset}>
          Clear History
        </button>
      </div>

      {loading ? (
        <div className="loading-overlay">
          <div className="spinner" />
          <p>Loading history...</p>
        </div>
      ) : records.length === 0 ? (
        <div className="empty-state">
          <div className="icon">📭</div>
          <p>No detections recorded yet.</p>
          <p style={{ fontSize: "0.8rem", marginTop: "0.5rem" }}>
            Run a detection from the <a href="/" style={{ color: "var(--primary)" }}>Detection</a> page to see results here.
          </p>
        </div>
      ) : (
        <div className="card" style={{ overflowX: "auto" }}>
          <table className="history-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Timestamp</th>
                <th>People</th>
                <th>Avg Confidence</th>
                <th>Inference Time</th>
              </tr>
            </thead>
            <tbody>
              {records.map((rec, i) => (
                <tr key={i}>
                  <td style={{ color: "var(--text-muted)" }}>{i + 1}</td>
                  <td>{formatTime(rec.timestamp)}</td>
                  <td style={{ fontWeight: 600 }}>{rec.count}</td>
                  <td>{confBadge(rec.average_confidence)}</td>
                  <td style={{ fontVariantNumeric: "tabular-nums" }}>
                    {rec.inference_time < 1
                      ? `${(rec.inference_time * 1000).toFixed(0)} ms`
                      : `${rec.inference_time.toFixed(2)} s`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ marginTop: "0.75rem", fontSize: "0.8rem", color: "var(--text-muted)" }}>
            Showing {records.length} record{records.length !== 1 && "s"}
          </div>
        </div>
      )}
    </div>
  );
}
