import { useState, useRef, useEffect } from "react";
import { detectImage } from "../utils/api";
import "./Detection.css";

const SAMPLES = [
  "busy-street-scene-in-yabelo-ethiopia-2011-jpg.jpg",
  "busy-street-with-pedestrians-in-dhaka-bangladesh-jpg.jpg",
  "christmas-market-crowd-winchester-geograph-org-uk-42887.jpg",
  "church-ave-people-walking-in-snow-chicken-restaurant-jan-2026-brooklyn-jpg.jpg",
  "crowd-at-the-kenting-night-market-20100925-jpg.jpg",
  "london-stadium-crowd-control-jpg.jpg",
  "pedestrians-crossing-the-a-busy-street-jpg.jpg",
  "people-walking-north-on-the-high-line-jpg.jpg",
  "people-walking-on-the-dufferin-terrace-in-winter-jpg.jpg",
  "person-in-winter-clothing-in-quebec-city-jpg.jpg",
  "queue-of-people-outside-a-mall-jpg.jpg",
  "tokyo-shibuya-scramble-crossing-2018-10-09-jpg.jpg",
  "walking-jewish-people-jerusalem-jpg.jpg",
];

function displayName(filename) {
  return filename
    .replace(/-jpg$/i, "")
    .replace(/-/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatTime(seconds) {
  return seconds < 1
    ? `${(seconds * 1000).toFixed(0)} ms`
    : `${seconds.toFixed(2)} s`;
}

export default function Detection() {
  const [selectedSample, setSelectedSample] = useState(null);
  const [dragOver, setDragOver] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    if (!result) return;
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, [result]);

  function handleFileSelect(file) {
    if (!file) return;
    setError(null);
    setSelectedSample(null);
    uploadFile(file);
  }

  function handleDrop(e) {
    e.preventDefault();
    setDragOver(false);
    handleFileSelect(e.dataTransfer.files[0]);
  }

  function handleDragOver(e) {
    e.preventDefault();
    setDragOver(true);
  }

  function handleDragLeave() {
    setDragOver(false);
  }

  async function uploadFile(file) {
    const allowed = ["image/jpeg", "image/png"];
    if (!allowed.includes(file.type)) {
      setError("Unsupported file type. Please upload a JPEG or PNG image.");
      return;
    }
    if (file.size > 15 * 1024 * 1024) {
      setError("File exceeds the 15 MB size limit.");
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const data = await detectImage(file);
      setResult(data);
    } catch (err) {
      setError(err.message || "Detection failed.");
    } finally {
      setLoading(false);
    }
  }

  async function handleSampleClick(filename) {
    setSelectedSample(filename);
    setError(null);
    setLoading(true);
    setResult(null);

    try {
      const res = await fetch(`/samples/${filename}`);
      if (!res.ok) throw new Error("Failed to fetch sample");
      const blob = await res.blob();
      await uploadFile(new File([blob], filename, { type: "image/jpeg" }));
    } catch (err) {
      setError(err.message || "Failed to load sample image.");
      setLoading(false);
    }
  }

  return (
    <div>
      <h1 className="page-title">Detection View</h1>
      <p className="page-subtitle">
        Upload an image or select a sample to detect people.
      </p>

      {error && <div className="alert alert-error">{error}</div>}

      {result && (
        <div className="results">
          <div className="stats">
            <div className="stat">
              <div className="stat-value success">{result.count}</div>
              <div className="stat-label">People Detected</div>
            </div>
            <div className="stat">
              <div className="stat-value primary">
                {(result.average_confidence * 100).toFixed(1)}%
              </div>
              <div className="stat-label">Avg Confidence</div>
            </div>
            <div className="stat">
              <div className="stat-value warning">
                {formatTime(result.inference_time)}
              </div>
              <div className="stat-label">Processing Time</div>
            </div>
          </div>

          <div className="results-grid">
            <div className="image-result">
              <img
                className="annotated-img"
                src={`data:image/jpeg;base64,${result.annotated_image}`}
                alt="Detection result"
              />
            </div>
            <div className="card">
              <div className="card-title">
                Detections ({result.detections.length})
              </div>
              <div className="detection-list">
                {result.detections.length === 0 ? (
                  <div className="empty-state">
                    <div className="icon">-</div>
                    <p>No people detected in this image.</p>
                  </div>
                ) : (
                  result.detections.map((det, i) => (
                    <div className="detection-item" key={i}>
                      <span className="det-index">#{i + 1}</span>
                      <span style={{ flex: 1, color: "var(--color-text-muted)" }}>
                        ({Math.round(det.x1)}, {Math.round(det.y1)}) &rarr; (
                        {Math.round(det.x2)}, {Math.round(det.y2)})
                      </span>
                      <span className="det-conf">
                        {(det.confidence * 100).toFixed(1)}%
                      </span>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="card" style={{ marginTop: "1.5rem" }}>
        <div className="card-title">Upload Image</div>
        <div
          className={`dropzone ${dragOver ? "dragging" : ""}`}
          onClick={() => fileInputRef.current?.click()}
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
        >
          <div className="dropzone-icon">📷</div>
          {loading ? (
            <div className="dropzone-text">
              <span className="spinner" /> Detecting…
            </div>
          ) : (
            <>
              <div className="dropzone-text">
                Drag &amp; drop an image here or{" "}
                <span className="browse">browse</span>
              </div>
              <div className="dropzone-hint">Supports JPEG, PNG (max 15 MB)</div>
            </>
          )}
          <input
            ref={fileInputRef}
            type="file"
            accept="image/jpeg,image/png"
            onChange={(e) => handleFileSelect(e.target.files[0])}
          />
        </div>
      </div>

      <div className="card" style={{ marginTop: "1.5rem" }}>
        <div className="card-title">Sample Images</div>
        <div className="sample-grid">
          {SAMPLES.map((name) => (
            <div
              key={name}
              className={`sample-card ${selectedSample === name ? "selected" : ""}`}
              onClick={() => handleSampleClick(name)}
            >
              <img src={`/samples/${name}`} alt={displayName(name)} loading="lazy" />
              <div className="sample-name">{displayName(name)}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}