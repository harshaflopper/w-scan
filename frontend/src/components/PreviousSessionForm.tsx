import { useState } from "react";

export interface PreviousSession {
  date: string;           // ISO "YYYY-MM-DD"
  area_cm2: number;
  perimeter_cm: number;
  composite_score: number;
}

interface Props {
  onData: (session: PreviousSession | null) => void;
}

/**
 * Optional form shown in the configure step.
 * Lets the clinician enter the previous session's metrics so the backend
 * can compute healing velocity, trajectory, and estimated closure.
 *
 * Data is also auto-populated from localStorage (last saved session).
 */
export default function PreviousSessionForm({ onData }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [date, setDate] = useState("");
  const [area, setArea] = useState("");
  const [perim, setPerim] = useState("");
  const [score, setScore] = useState("");

  function loadFromStorage() {
    const raw = localStorage.getItem("wscan_last_session");
    if (!raw) return;
    try {
      const s: PreviousSession = JSON.parse(raw);
      setDate(s.date);
      setArea(String(s.area_cm2));
      setPerim(String(s.perimeter_cm));
      setScore(String(s.composite_score));
      onData(s);
    } catch {
      // corrupted storage — ignore
    }
  }

  function handleChange(
    field: "date" | "area" | "perim" | "score",
    val: string
  ) {
    const setters = { date: setDate, area: setArea, perim: setPerim, score: setScore };
    setters[field](val);

    const d = field === "date" ? val : date;
    const a = field === "area" ? val : area;
    const p = field === "perim" ? val : perim;
    const sc = field === "score" ? val : score;

    if (d && a && p && sc) {
      onData({
        date: d,
        area_cm2: parseFloat(a),
        perimeter_cm: parseFloat(p),
        composite_score: parseFloat(sc),
      });
    } else {
      onData(null);
    }
  }

  function clear() {
    setDate(""); setArea(""); setPerim(""); setScore("");
    onData(null);
  }

  return (
    <div
      className="card"
      style={{ marginTop: "0.75rem", borderColor: expanded ? "var(--border-bright)" : "var(--border)" }}
    >
      {/* Header toggle */}
      <button
        onClick={() => setExpanded((v) => !v)}
        style={{
          width: "100%",
          background: "none",
          border: "none",
          cursor: "pointer",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: 0,
          color: "var(--text-secondary)",
        }}
      >
        <span style={{ fontSize: "0.85rem", fontWeight: 600 }}>
          Previous session data
          <span
            className="text-muted"
            style={{ fontSize: "0.72rem", fontWeight: 400, marginLeft: 6 }}
          >
            (enables healing velocity & trajectory)
          </span>
        </span>
        <span
          style={{
            fontSize: "0.8rem",
            color: "var(--teal)",
            transform: expanded ? "rotate(180deg)" : "none",
            transition: "transform 0.2s",
            lineHeight: 1,
          }}
        >
          ▾
        </span>
      </button>

      {expanded && (
        <div className="animate-fade-in" style={{ marginTop: "1rem" }}>
          {/* Auto-fill from localStorage */}
          {localStorage.getItem("wscan_last_session") && (
            <button
              className="btn btn-ghost"
              style={{ width: "100%", marginBottom: "0.75rem", fontSize: "0.8rem" }}
              onClick={loadFromStorage}
            >
              ↓ Load last saved session
            </button>
          )}

          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr 1fr",
              gap: "0.5rem",
            }}
          >
            <div>
              <label htmlFor="prev-date">Date</label>
              <input
                id="prev-date"
                type="text"
                placeholder="YYYY-MM-DD"
                value={date}
                onChange={(e) => handleChange("date", e.target.value)}
              />
            </div>
            <div>
              <label htmlFor="prev-score">Composite score</label>
              <input
                id="prev-score"
                type="number"
                placeholder="0–100"
                min="0"
                max="100"
                value={score}
                onChange={(e) => handleChange("score", e.target.value)}
              />
            </div>
            <div>
              <label htmlFor="prev-area">Area (cm²)</label>
              <input
                id="prev-area"
                type="number"
                placeholder="e.g. 8.4"
                min="0"
                step="0.01"
                value={area}
                onChange={(e) => handleChange("area", e.target.value)}
              />
            </div>
            <div>
              <label htmlFor="prev-perim">Perimeter (cm)</label>
              <input
                id="prev-perim"
                type="number"
                placeholder="e.g. 10.2"
                min="0"
                step="0.01"
                value={perim}
                onChange={(e) => handleChange("perim", e.target.value)}
              />
            </div>
          </div>

          {date && area && perim && score && (
            <div
              className="animate-fade-in"
              style={{
                marginTop: "0.6rem",
                fontSize: "0.78rem",
                color: "var(--teal)",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
              }}
            >
              <span>✓ Temporal analysis enabled</span>
              <button
                onClick={clear}
                style={{
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  color: "var(--text-muted)",
                  fontSize: "0.75rem",
                }}
              >
                clear
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
