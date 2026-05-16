import { useState, useEffect } from "react";
import { useUser } from "@clerk/clerk-react";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { Activity, Camera, ArrowLeft, ArrowUpRight, ArrowDownRight, Folder, Trash2, ChevronDown, ChevronUp, Pill, FileText, TrendingDown, AlertCircle } from "lucide-react";
import { useNavigate } from "react-router-dom";

export default function TrackingDashboard() {
  const { user } = useUser();
  const navigate = useNavigate();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [selectedWoundType, setSelectedWoundType] = useState<string | null>(null);
  const [expandedRow, setExpandedRow] = useState<number | null>(0);

  useEffect(() => {
    if (!user) return;
    fetch(`${import.meta.env.VITE_API_URL}/tracking/${user.id}`)
      .then(r => r.json())
      .then(j => setData(j))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [user]);

  async function handleDeleteFolder() {
    if (!selectedWoundType) return;
    if (!confirm(`Delete the '${selectedWoundType}' folder and ALL its scans permanently?`)) return;
    try {
      const res = await fetch(`/api/tracking/wound/${encodeURIComponent(selectedWoundType)}?patient_id=${user?.id || "anon_123"}`, { method: "DELETE" });
      if (res.ok) { setSelectedWoundType(null); window.location.reload(); }
      else alert("Failed to delete folder.");
    } catch { alert("Error deleting folder."); }
  }

  if (loading) return (
    <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: "60vh", flexDirection: "column", gap: "1rem" }}>
      <div className="radar-spinner" />
      <p style={{ color: "var(--text-muted)", fontSize: "0.9rem" }}>Loading wound history…</p>
    </div>
  );

  if (!data || data.status === "NO_HISTORY") return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", height: "60vh", gap: "1.5rem", textAlign: "center" }}>
      <div style={{ width: 80, height: 80, borderRadius: "50%", background: "rgba(180,139,108,0.08)", border: "1px solid rgba(180,139,108,0.15)", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <Activity size={36} color="var(--tertiary)" />
      </div>
      <div>
        <h2 style={{ fontSize: "1.8rem", marginBottom: "0.5rem" }}>Not Found</h2>
        <p style={{ color: "var(--text-muted)" }}>No wound history. Begin with a scan.</p>
      </div>
      <button onClick={() => navigate("/scan")} className="btn btn-primary" style={{ padding: "0.9rem 2rem", fontSize: "1rem" }}>
        <Camera size={18} /> New Scan
      </button>
    </div>
  );

  const history = data?.history || [];
  const woundsMap = new Map<string, any[]>();
  history.forEach((s: any) => {
    const key = (s.wound_type || "unknown wound").trim().toLowerCase();
    if (!woundsMap.has(key)) woundsMap.set(key, []);
    woundsMap.get(key)!.push(s);
  });
  const uniqueWounds = Array.from(woundsMap.keys());

  // ─── LEVEL 1: WOUND DIRECTORY ───────────────────────────────────────────
  if (!selectedWoundType) return (
    <div className="animate-fade-in" style={{ maxWidth: 1000, margin: "0 auto", width: "100%" }}>
      <div style={{ marginBottom: "2.5rem" }}>
        <h1 style={{ fontSize: "2rem", fontWeight: 700, letterSpacing: "-0.03em", marginBottom: "0.4rem" }}>Wounds</h1>
        <p style={{ color: "var(--text-muted)", fontSize: "0.9rem" }}>Select a wound to view its full history.</p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: "1.25rem" }}>
        {uniqueWounds.map(wt => {
          const wh = woundsMap.get(wt)!;
          const latest = wh[0];
          const area = latest.area_cm2 || 0;
          const prev = wh[1]?.area_cm2 || area;
          const improving = area <= prev;
          const pct = prev > 0 ? Math.abs(((area - prev) / prev) * 100).toFixed(0) : null;

          return (
            <div key={wt} onClick={() => { setSelectedWoundType(wt); setExpandedRow(0); }}
              style={{ cursor: "pointer", background: "rgba(255,255,255,0.02)", border: "1px solid var(--border)", borderRadius: 16, padding: "1.5rem", transition: "all 0.2s ease" }}
              onMouseEnter={e => { e.currentTarget.style.borderColor = "var(--tertiary)"; e.currentTarget.style.background = "rgba(180,139,108,0.04)"; }}
              onMouseLeave={e => { e.currentTarget.style.borderColor = "var(--border)"; e.currentTarget.style.background = "rgba(255,255,255,0.02)"; }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "1.25rem" }}>
                <div style={{ background: "rgba(180,139,108,0.12)", padding: "0.7rem", borderRadius: 12, color: "var(--tertiary)" }}>
                  <Folder size={24} />
                </div>
                <div style={{ textAlign: "right" }}>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>{wh.length} {wh.length === 1 ? "scan" : "scans"}</div>
                  {pct && (
                    <div style={{ display: "flex", alignItems: "center", gap: 3, justifyContent: "flex-end", marginTop: 2, color: improving ? "#4ade80" : "#fb923c", fontSize: "0.8rem", fontWeight: 600 }}>
                      {improving ? <TrendingDown size={12}/> : <ArrowUpRight size={12}/>} {pct}%
                    </div>
                  )}
                </div>
              </div>
              <h3 style={{ textTransform: "capitalize", fontSize: "1.15rem", fontWeight: 600, marginBottom: "0.4rem" }}>{wt}</h3>
              <div style={{ fontSize: "1.5rem", fontWeight: 700, color: "var(--tertiary)", marginBottom: "0.25rem" }}>{area.toFixed(2)} <span style={{ fontSize: "0.85rem", fontWeight: 400, color: "var(--text-muted)" }}>cm²</span></div>
              <div style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>Last scanned {latest.session_date?.substring(0, 10)}</div>
            </div>
          );
        })}

        {/* New Wound CTA */}
        <div onClick={() => navigate("/scan")}
          style={{ cursor: "pointer", border: "1px dashed var(--border)", borderRadius: 16, padding: "1.5rem", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: "0.75rem", color: "var(--text-muted)", transition: "all 0.2s ease", minHeight: 160 }}
          onMouseEnter={e => { e.currentTarget.style.borderColor = "var(--tertiary)"; e.currentTarget.style.color = "var(--tertiary)"; }}
          onMouseLeave={e => { e.currentTarget.style.borderColor = "var(--border)"; e.currentTarget.style.color = "var(--text-muted)"; }}
        >
          <Camera size={28} />
          <span style={{ fontSize: "0.9rem", fontWeight: 500 }}>New Wound Scan</span>
        </div>
      </div>
    </div>
  );

  // ─── LEVEL 2: WOUND DETAIL DASHBOARD ────────────────────────────────────
  const woundHistory = woundsMap.get(selectedWoundType) || [];
  const trendData = [...woundHistory].reverse().map((s: any) => ({ date: s.session_date?.substring(5, 10) || "", area: s.area_cm2 || 0 }));
  const isImproving = trendData.length > 1 && trendData[trendData.length - 1].area <= trendData[0].area;
  const trendColor = isImproving ? "#4ade80" : "#fb923c";

  return (
    <div className="animate-fade-in" style={{ maxWidth: 1000, margin: "0 auto", width: "100%", display: "flex", flexDirection: "column", gap: "1.5rem" }}>

      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
        <button onClick={() => setSelectedWoundType(null)} className="btn btn-ghost" style={{ padding: "0.5rem", borderRadius: "50%", width: 40, height: 40 }}>
          <ArrowLeft size={20} />
        </button>
        <div style={{ flex: 1 }}>
          <h1 style={{ fontSize: "1.8rem", fontWeight: 700, textTransform: "capitalize", letterSpacing: "-0.02em", lineHeight: 1 }}>{selectedWoundType}</h1>
          <p style={{ color: "var(--text-muted)", fontSize: "0.85rem", marginTop: "0.25rem" }}>Healing trajectory · {woundHistory.length} scans</p>
        </div>
        <button onClick={handleDeleteFolder} style={{ display: "flex", alignItems: "center", gap: "0.4rem", padding: "0.5rem 1rem", borderRadius: 8, background: "rgba(239,68,68,0.08)", color: "#f87171", border: "1px solid rgba(239,68,68,0.15)", cursor: "pointer", fontSize: "0.85rem", fontWeight: 500 }}>
          <Trash2 size={14} /> Delete
        </button>
      </div>

      {/* Update Scan Banner */}
      <div style={{ background: "linear-gradient(135deg, rgba(180,139,108,0.12), rgba(180,139,108,0.04))", border: "1px solid rgba(180,139,108,0.25)", borderRadius: 16, padding: "1.5rem 2rem", display: "flex", justifyContent: "space-between", alignItems: "center", gap: "1rem" }}>
        <div>
          <h3 style={{ fontSize: "1.1rem", fontWeight: 600, marginBottom: "0.3rem" }}>Update This Wound</h3>
          <p style={{ color: "var(--text-muted)", fontSize: "0.85rem" }}>
            AI will compare against your {woundHistory[0]?.session_date?.substring(0, 10)} scan and show you exact healing progress.
          </p>
        </div>
        <button onClick={() => navigate("/scan?wound=" + encodeURIComponent(selectedWoundType))} className="btn" style={{ background: "var(--tertiary)", color: "#fff", padding: "0.8rem 1.5rem", whiteSpace: "nowrap", flexShrink: 0 }}>
          <Camera size={16} /> Update Scan
        </button>
      </div>

      {/* Trend Chart */}
      {trendData.length > 1 && (
        <div style={{ background: "rgba(255,255,255,0.02)", border: "1px solid var(--border)", borderRadius: 16, padding: "1.5rem" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.25rem" }}>
            <span style={{ fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: "0.1em", color: "var(--text-muted)" }}>Area Reduction Trajectory</span>
            <span style={{ fontSize: "0.8rem", fontWeight: 600, color: trendColor, display: "flex", alignItems: "center", gap: 4 }}>
              {isImproving ? <TrendingDown size={14}/> : <ArrowUpRight size={14}/>}
              {isImproving ? "Healing" : "Monitoring"}
            </span>
          </div>
          <ResponsiveContainer width="100%" height={180}>
            <AreaChart data={trendData} margin={{ top: 5, right: 5, left: -25, bottom: 0 }}>
              <defs>
                <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={trendColor} stopOpacity={0.3}/>
                  <stop offset="95%" stopColor={trendColor} stopOpacity={0}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false}/>
              <XAxis dataKey="date" stroke="transparent" tick={{ fill: "var(--text-muted)", fontSize: 11 }}/>
              <YAxis stroke="transparent" tick={{ fill: "var(--text-muted)", fontSize: 11 }}/>
              <Tooltip contentStyle={{ background: "#1a1a1f", border: "1px solid var(--border)", borderRadius: 8 }} itemStyle={{ color: "var(--text-primary)" }} labelStyle={{ color: "var(--text-muted)" }}/>
              <Area type="monotone" dataKey="area" stroke={trendColor} strokeWidth={2.5} fill="url(#areaGrad)" dot={{ fill: trendColor, r: 4, strokeWidth: 0 }} activeDot={{ r: 6 }}/>
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Clinical History Log */}
      <div style={{ background: "rgba(255,255,255,0.02)", border: "1px solid var(--border)", borderRadius: 16, overflow: "hidden" }}>
        <div style={{ padding: "1.25rem 1.5rem", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <FileText size={16} color="var(--text-muted)" />
          <span style={{ fontSize: "0.85rem", fontWeight: 600, color: "var(--text-secondary)" }}>Clinical History Log</span>
        </div>

        {woundHistory.map((session: any, index: number) => {
          const isBaseline = index === woundHistory.length - 1;
          const prevArea = !isBaseline ? (woundHistory[index + 1]?.area_cm2 || 0) : 0;
          const area = session.area_cm2 || 0;
          const delta = !isBaseline ? area - prevArea : 0;
          const isExpanded = expandedRow === index;
          const isHighRisk = session.infection_risk === "HIGH" || session.infection_risk === "CRITICAL";

          return (
            <div key={session.id || index} style={{ borderBottom: index < woundHistory.length - 1 ? "1px solid var(--border)" : "none" }}>
              {/* Row Header */}
              <div onClick={() => setExpandedRow(isExpanded ? null : index)}
                style={{ display: "grid", gridTemplateColumns: "64px 56px 1fr auto 36px", alignItems: "center", gap: "1rem", padding: "1rem 1.5rem", cursor: "pointer", background: isExpanded ? "rgba(255,255,255,0.015)" : "transparent", transition: "background 0.15s" }}
                onMouseEnter={e => { if (!isExpanded) e.currentTarget.style.background = "rgba(255,255,255,0.01)"; }}
                onMouseLeave={e => { if (!isExpanded) e.currentTarget.style.background = "transparent"; }}
              >
                <div>
                  <div style={{ fontSize: "0.8rem", fontWeight: 600, color: "var(--text-primary)" }}>{session.session_date?.substring(5, 10)}</div>
                  <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", marginTop: 2 }}>S-{session.session_number}</div>
                  {isBaseline && <div style={{ fontSize: "0.65rem", background: "rgba(180,139,108,0.15)", color: "var(--tertiary)", padding: "1px 5px", borderRadius: 4, marginTop: 4, display: "inline-block" }}>Baseline</div>}
                </div>

                <div style={{ width: 56, height: 56, borderRadius: 8, overflow: "hidden", background: "rgba(0,0,0,0.3)", border: "1px solid var(--border)", flexShrink: 0 }}>
                  {session.image_url
                    ? <img src={session.image_url} alt="scan" style={{ width: "100%", height: "100%", objectFit: "cover" }}/>
                    : <div style={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-muted)", fontSize: "0.6rem" }}>No photo</div>
                  }
                </div>

                <div>
                  <div style={{ fontSize: "1.05rem", fontWeight: 600 }}>{area.toFixed(2)} cm²</div>
                  <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: 2, textTransform: "capitalize" }}>{session.dominant_tissue || "—"}</div>
                  {isHighRisk && <div style={{ display: "flex", alignItems: "center", gap: 3, color: "#f87171", fontSize: "0.7rem", marginTop: 3 }}><AlertCircle size={10}/> High infection risk</div>}
                </div>

                <div style={{ textAlign: "right" }}>
                  {!isBaseline && (
                    <div style={{ display: "flex", alignItems: "center", gap: 3, color: delta < 0 ? "#4ade80" : "#fb923c", fontWeight: 700, fontSize: "0.9rem", justifyContent: "flex-end" }}>
                      {delta < 0 ? <ArrowDownRight size={14}/> : <ArrowUpRight size={14}/>}
                      {Math.abs(delta).toFixed(2)} cm²
                    </div>
                  )}
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: 2 }}>BWAT {session.bwat_total || "—"}</div>
                </div>

                <div style={{ color: "var(--text-muted)" }}>
                  {isExpanded ? <ChevronUp size={16}/> : <ChevronDown size={16}/>}
                </div>
              </div>

              {/* Expanded Body */}
              {isExpanded && (
                <div className="animate-fade-in" style={{ padding: "1.5rem", background: "rgba(0,0,0,0.15)", borderTop: "1px solid var(--border)" }}>

                  {/* AI Clinical Report */}
                  <div style={{ background: "rgba(180,139,108,0.06)", border: "1px solid rgba(180,139,108,0.2)", borderRadius: 12, padding: "1.25rem", marginBottom: "1.5rem" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "1rem" }}>
                      <Activity size={15} color="var(--tertiary)"/>
                      <span style={{ fontSize: "0.75rem", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--tertiary)" }}>AI Clinical Report</span>
                    </div>

                    {session.patient_message ? (
                      <div style={{ marginBottom: "1rem", padding: "1rem", background: "rgba(255,255,255,0.03)", borderRadius: 8 }}>
                        <div style={{ fontSize: "0.65rem", color: "var(--tertiary)", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: "0.4rem" }}>For You</div>
                        <p style={{ fontSize: "0.95rem", lineHeight: 1.7, color: "var(--text-primary)" }}>{session.patient_message}</p>
                      </div>
                    ) : null}

                    {session.clinician_report ? (
                      <div style={{ padding: "0.85rem 1rem", background: "rgba(0,0,0,0.2)", borderRadius: 8, borderLeft: "3px solid var(--tertiary)" }}>
                        <div style={{ fontSize: "0.65rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: "0.4rem" }}>Clinical Synthesis</div>
                        <p style={{ fontSize: "0.875rem", lineHeight: 1.6, color: "var(--text-secondary)" }}>{session.clinician_report}</p>
                      </div>
                    ) : (
                      <p style={{ fontSize: "0.85rem", color: "var(--text-muted)", fontStyle: "italic" }}>No AI report for this session.</p>
                    )}

                    {/* Care Plan */}
                    {(session.care_plan?.dressing_type || session.care_plan?.product_name) && (
                      <div style={{ marginTop: "1rem", padding: "1rem", background: "rgba(0,0,0,0.2)", borderRadius: 8 }}>
                        <div style={{ fontSize: "0.65rem", color: "var(--text-muted)", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: "0.75rem" }}>Care Plan</div>
                        {session.care_plan?.dressing_type && (
                          <p style={{ fontSize: "0.875rem", color: "var(--text-secondary)", marginBottom: "0.5rem" }}>
                            <span style={{ color: "var(--text-muted)" }}>Dressing: </span>{session.care_plan.dressing_type}
                          </p>
                        )}
                        {session.care_plan?.product_name && (
                          <a href={`https://www.google.com/search?tbm=shop&q=${encodeURIComponent(session.care_plan.product_search_query || session.care_plan.product_name)}`}
                            target="_blank" rel="noreferrer" 
                            style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginTop: "1rem", background: "linear-gradient(145deg, rgba(180,139,108,0.15) 0%, rgba(180,139,108,0.05) 100%)", padding: "1rem", borderRadius: "10px", border: "1px solid rgba(180,139,108,0.2)", textDecoration: "none", transition: "all 0.2s ease" }}
                            className="hover-lift">
                            <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                              <div style={{ background: "rgba(180,139,108,0.2)", padding: "0.5rem", borderRadius: "8px" }}><Pill size={16} color="var(--tertiary)"/></div>
                              <div>
                                <div style={{ fontSize: "0.7rem", color: "var(--tertiary)", textTransform: "uppercase", fontWeight: 600, letterSpacing: "0.05em" }}>Pharmacy Suggestion</div>
                                <div style={{ fontWeight: 500, color: "var(--text-primary)", fontSize: "0.95rem" }}>{session.care_plan.product_name}</div>
                              </div>
                            </div>
                            <span style={{ color: "var(--tertiary)", fontSize: "0.8rem", fontWeight: 500 }}>Find →</span>
                          </a>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Metrics Grid */}
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "1rem" }}>
                    {/* Scan image */}
                    {session.image_url && (
                      <div style={{ gridRow: "span 2", borderRadius: 10, overflow: "hidden", border: "1px solid var(--border)" }}>
                        <img src={session.image_url} alt="Wound scan" style={{ width: "100%", height: "100%", objectFit: "cover", display: "block", minHeight: 160 }}/>
                      </div>
                    )}

                    {/* BWAT */}
                    <div style={{ background: "rgba(0,0,0,0.2)", borderRadius: 10, padding: "1rem", border: "1px solid var(--border)" }}>
                      <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", marginBottom: "0.5rem" }}>BWAT SCORE</div>
                      <div style={{ fontSize: "1.6rem", fontWeight: 700 }}>{session.bwat_total || "—"}</div>
                      <div style={{ fontSize: "0.8rem", color: "var(--text-muted)", textTransform: "capitalize" }}>{session.bwat_severity || "unknown"}</div>
                    </div>

                    {/* Infection */}
                    <div style={{ background: "rgba(0,0,0,0.2)", borderRadius: 10, padding: "1rem", border: `1px solid ${isHighRisk ? "rgba(248,113,113,0.3)" : "var(--border)"}` }}>
                      <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", marginBottom: "0.5rem" }}>INFECTION RISK</div>
                      <div style={{ fontSize: "1.2rem", fontWeight: 700, color: isHighRisk ? "#f87171" : "#4ade80" }}>{session.infection_risk || "Low"}</div>
                    </div>

                    {/* TIME Framework */}
                    <div style={{ background: "rgba(0,0,0,0.2)", borderRadius: 10, padding: "1rem", border: "1px solid var(--border)" }}>
                      <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", marginBottom: "0.75rem" }}>T.I.M.E FRAMEWORK</div>
                      <div style={{ display: "grid", gap: "0.4rem" }}>
                        {["T", "I", "M", "E"].map(k => (
                          <div key={k} style={{ display: "flex", gap: "0.5rem", fontSize: "0.8rem" }}>
                            <span style={{ fontWeight: 700, color: "var(--tertiary)", width: 12 }}>{k}</span>
                            <span style={{ color: "var(--text-muted)" }}>{(session.TIME as any)?.[k] || "Not assessed"}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
