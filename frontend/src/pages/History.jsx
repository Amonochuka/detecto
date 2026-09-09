import { useState, useEffect, useCallback } from "react";
import { fetchHistory, resetHistory, exportHistory } from "../utils/api";

export default function History() {
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [dateFilter, setDateFilter] = useState("");
  const [limit, setLimit] = useState(50);

  const loadHistory = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchHistory({
        date: dateFilter || undefined,
        limit,
      });
      setRecords(data.detections || []);
    } catch (err) {
      setError(err.message || "Failed to fetch history.");
    } finally {
      setLoading(false);
    }
  }, [dateFilter, limit]);

  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  async function handleReset() {
    if (!window.confirm("Clear all detection history? This cannot be undone.")) return;
    setError(null);
    try {
      await resetHistory();
      setRecords([]);
    } catch (err) {
      setError(err.message || "Failed to clear history.");
    }
  }

  async function handleExport() {
    setError(null);
    try {
      const blob = await exportHistory({
        date: dateFilter || undefined,
        limit,
        format: "csv",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `detecto-history-${dateFilter || "all"}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err.message || "Export failed.");
    }
  }

  function confBadge(conf) {
    const pct = (conf * 100).toFixed(1);
    let cls = "conf-low";
    if (conf >= 0.7) cls = "conf-high";
    else if (conf >= 0.4) cls = "conf-medium";
    return <span className={`conf-badge ${cls}`}>{pct}%</span>;
  }

  function formatTime(seconds) {
    return seconds < 1
      ? `${(seconds * 1000).toFixed(0)} ms`
      : `${seconds.toFixed(2)} s`;
  }

  return (
    <div>
      <div className="page-header">
        <h1>History View</h1>
        <p>Review past detections and monitor activity over time.</p>
      </div>

      {error && <div className="error-banner">{error}</div>}

      <div className="filters-bar">
        <label style={{ fontSize: "0.85rem", color: "var(--color-text-muted)" }}>
          Date:
          <input
            type="date"
            value={dateFilter}
            onChange={(e) => setDateFilter(e.target.value)}
            style={{ marginLeft: "0.5rem" }}
          />
        </label>
        <label style={{ fontSize: "0.85rem", color: "var(--color-text-muted)" }}>
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
        <button className="btn btn-outline" onClick={loadHistory}>
          Refresh
        </button>
        <button className="btn btn-outline" onClick={handleExport}>
          Download CSV
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
            Run a detection from the <a href="/">Detection</a> page to see results here.
          </p>
        </div>
      ) : (
        <>
          <HourlyStats records={records} />
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
                    <td style={{ color: "var(--color-text-muted)" }}>{i + 1}</td>
                    <td>{formatDateTime(rec.timestamp)}</td>
                    <td style={{ fontWeight: 600 }}>{rec.count}</td>
                    <td>{confBadge(rec.average_confidence)}</td>
                    <td style={{ fontVariantNumeric: "tabular-nums" }}>
                      {formatTime(rec.inference_time)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div style={{ marginTop: "0.75rem", fontSize: "0.8rem", color: "var(--color-text-muted)" }}>
              Showing {records.length} record{records.length !== 1 && "s"}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function formatDateTime(iso) {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function computeHourlyStats(records) {
  const byHour = new Map();
  for (const rec of records) {
    const t = new Date(rec.timestamp);
    if (!Number.isFinite(t.getTime()) || typeof rec.count !== "number") continue;
    const key = `${t.getFullYear()}-${String(t.getMonth() + 1).padStart(2, "0")}-${String(
      t.getDate()
    ).padStart(2, "0")} ${String(t.getHours()).padStart(2, "0")}:00`;
    if (!byHour.has(key)) byHour.set(key, { counts: [] });
    byHour.get(key).counts.push(rec.count);
  }
  return [...byHour.entries()]
    .sort((a, b) => a[0].localeCompare(b[0]))
    .map(([label, { counts }]) => ({
      label,
      avg: counts.reduce((s, c) => s + c, 0) / counts.length,
      samples: counts.length,
    }));
}

function HourlyStats({ records }) {
  const stats = computeHourlyStats(records);
  if (stats.length === 0) return null;

  const maxAvg = Math.max(...stats.map((s) => s.avg));
  const overallAvg = stats.reduce((s, x) => s + x.avg, 0) / stats.length;
  const peak = stats.reduce((a, b) => (b.avg > a.avg ? b : a));

  return (
    <div className="card stats-card">
      <div className="card-title">Average Crowd Size per Hour</div>
      <div className="hourly-chart">
        {stats.map((s) => (
          <div
            className="hourly-bar-col"
            key={s.label}
            title={`${s.label} — avg ${s.avg.toFixed(1)} people (${s.samples} detection${
              s.samples !== 1 ? "s" : ""
            })`}
          >
            <div className="hourly-bar-val">{s.avg.toFixed(1)}</div>
            <div
              className="hourly-bar"
              style={{ height: `${Math.max(4, (s.avg / maxAvg) * 92)}%` }}
            />
            <div className="hourly-bar-label">{s.label.slice(11)}</div>
          </div>
        ))}
      </div>
      <div className="stats-summary">
        Avg across recorded hours: <strong>{overallAvg.toFixed(1)}</strong> people/h · Peak
        hour: <strong>{peak.label}</strong> ({peak.avg.toFixed(1)} people avg)
      </div>
    </div>
  );
}