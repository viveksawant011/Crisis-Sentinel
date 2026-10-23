import { useState } from "react";

/**
 * EvidencePanel: Displays live Tavily sources, extracted facts, and contradiction resolutions.
 * Demonstrates grounded, multi-source verification with clickable provenance.
 */
export default function EvidencePanel({ intelligence }) {
  const [activeTab, setActiveTab] = useState("claims"); // 'claims' | 'sources' | 'contradictions'

  if (!intelligence) return null;

  const {
    claims = [],
    sources = [],
    contradictions = [],
    event = "External Disruption Event",
    impacted_country,
    impacted_category,
    severity = "medium",
  } = intelligence;

  // Severity color tags
  const severityColors = {
    critical: {
      bg: "rgba(248, 81, 73, 0.15)",
      text: "#f85149",
      border: "#f85149",
    },
    high: {
      bg: "rgba(240, 136, 62, 0.15)",
      text: "#f0883e",
      border: "#f0883e",
    },
    medium: {
      bg: "rgba(210, 153, 34, 0.15)",
      text: "#d29922",
      border: "#d29922",
    },
    low: { bg: "rgba(56, 139, 253, 0.15)", text: "#58a6ff", border: "#58a6ff" },
  };

  const badge = severityColors[severity.toLowerCase()] || severityColors.medium;

  return (
    <div
      style={{
        marginTop: "24px",
        padding: "24px",
        backgroundColor: "#161b22",
        border: "1px solid #30363d",
        borderRadius: "12px",
        color: "#c9d1d9",
        fontFamily:
          '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      }}
    >
      {/* Header with Live Signal Badges */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          marginBottom: "16px",
        }}
      >
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span style={{ fontSize: "18px" }}>🔍</span>
            <h3 style={{ margin: 0, fontSize: "18px", color: "#f0f6fc" }}>
              {event || "Multi-Source Evidence & Intelligence"}
            </h3>
          </div>
          <p style={{ margin: "4px 0 0", fontSize: "13px", color: "#8b949e" }}>
            Live Tavily web research extracted by Nemotron Nano into structured
            claims with source grounding.
          </p>
        </div>

        <div style={{ display: "flex", gap: "8px" }}>
          {impacted_country && (
            <span
              style={{
                padding: "3px 8px",
                borderRadius: "4px",
                fontSize: "11px",
                background: "#21262d",
                color: "#c9d1d9",
                border: "1px solid #30363d",
              }}
            >
              📍 {impacted_country}
            </span>
          )}
          {impacted_category && (
            <span
              style={{
                padding: "3px 8px",
                borderRadius: "4px",
                fontSize: "11px",
                background: "#21262d",
                color: "#c9d1d9",
                border: "1px solid #30363d",
              }}
            >
              📦 {impacted_category}
            </span>
          )}
          <span
            style={{
              padding: "3px 8px",
              borderRadius: "4px",
              fontSize: "11px",
              textTransform: "uppercase",
              fontWeight: "bold",
              background: badge.bg,
              color: badge.text,
              border: `1px solid ${badge.border}`,
            }}
          >
            {severity}
          </span>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div
        style={{
          display: "flex",
          gap: "12px",
          borderBottom: "1px solid #21262d",
          paddingBottom: "8px",
          marginBottom: "16px",
        }}
      >
        <button
          type="button"
          onClick={() => setActiveTab("claims")}
          style={{
            background: "none",
            border: "none",
            color: activeTab === "claims" ? "#58a6ff" : "#8b949e",
            borderBottom: activeTab === "claims" ? "2px solid #58a6ff" : "none",
            padding: "6px 12px",
            cursor: "pointer",
            fontSize: "13px",
            fontWeight: 600,
          }}
        >
          Extracted Claims ({claims.length})
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("sources")}
          style={{
            background: "none",
            border: "none",
            color: activeTab === "sources" ? "#58a6ff" : "#8b949e",
            borderBottom:
              activeTab === "sources" ? "2px solid #58a6ff" : "none",
            padding: "6px 12px",
            cursor: "pointer",
            fontSize: "13px",
            fontWeight: 600,
          }}
        >
          Live Sources ({sources.length})
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("contradictions")}
          style={{
            background: "none",
            border: "none",
            color: activeTab === "contradictions" ? "#f0883e" : "#8b949e",
            borderBottom:
              activeTab === "contradictions" ? "2px solid #f0883e" : "none",
            padding: "6px 12px",
            cursor: "pointer",
            fontSize: "13px",
            fontWeight: 600,
          }}
        >
          Contradictions ({contradictions.length})
        </button>
      </div>

      {/* Tab 1: Claims List */}
      {activeTab === "claims" && (
        <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
          {claims.length === 0 ? (
            <div
              style={{ color: "#8b949e", fontSize: "13px", padding: "12px 0" }}
            >
              No claims extracted.
            </div>
          ) : (
            claims.map((claim, idx) => (
              <div
                key={claim.claim_id || idx}
                style={{
                  padding: "12px 16px",
                  backgroundColor: "#0d1117",
                  border: "1px solid #30363d",
                  borderRadius: "8px",
                  fontSize: "13px",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "flex-start",
                    marginBottom: "6px",
                  }}
                >
                  <span style={{ fontWeight: 600, color: "#f0f6fc" }}>
                    {claim.claim_id || `Fact #${idx + 1}`}: {claim.text}
                  </span>
                  {claim.type && (
                    <span
                      style={{
                        fontSize: "11px",
                        color: "#8b949e",
                        background: "#21262d",
                        padding: "2px 6px",
                        borderRadius: "4px",
                      }}
                    >
                      {claim.type}
                    </span>
                  )}
                </div>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    fontSize: "11px",
                    color: "#8b949e",
                  }}
                >
                  <span>Source Attribution:</span>
                  {(claim.source_ids || []).map((sid, sIdx) => (
                    <span
                      key={sIdx}
                      style={{
                        color: "#58a6ff",
                        background: "rgba(56, 139, 253, 0.1)",
                        padding: "1px 5px",
                        borderRadius: "3px",
                      }}
                    >
                      {sid}
                    </span>
                  ))}
                  {claim.value && (
                    <span
                      style={{
                        marginLeft: "auto",
                        color: "#3fb950",
                        fontWeight: 500,
                      }}
                    >
                      Value: {claim.value}
                    </span>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Tab 2: Sources Chips & Links */}
      {activeTab === "sources" && (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
            gap: "12px",
          }}
        >
          {sources.length === 0 ? (
            <div style={{ color: "#8b949e", fontSize: "13px" }}>
              No raw sources retrieved.
            </div>
          ) : (
            sources.map((src, idx) => (
              <div
                key={src.source_id || idx}
                style={{
                  padding: "12px",
                  backgroundColor: "#0d1117",
                  border: "1px solid #30363d",
                  borderRadius: "8px",
                  fontSize: "12px",
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "space-between",
                }}
              >
                <div>
                  <div
                    style={{
                      fontWeight: 600,
                      color: "#f0f6fc",
                      marginBottom: "4px",
                    }}
                  >
                    [{src.source_id || `S${idx + 1}`}]{" "}
                    {src.title || "Live Search Hit"}
                  </div>
                  <p
                    style={{
                      color: "#8b949e",
                      margin: 0,
                      maxHeight: "60px",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                    }}
                  >
                    {src.content
                      ? `${src.content.substring(0, 140)}...`
                      : "No preview available."}
                  </p>
                </div>
                {src.url && (
                  <a
                    href={src.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{
                      marginTop: "8px",
                      color: "#58a6ff",
                      textDecoration: "none",
                      fontSize: "11px",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "4px",
                    }}
                  >
                    <span>Inspect Raw Source</span> ↗
                  </a>
                )}
              </div>
            ))
          )}
        </div>
      )}

      {/* Tab 3: Contradiction Resolution Card */}
      {activeTab === "contradictions" && (
        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          {contradictions.length === 0 ? (
            <div
              style={{
                padding: "16px",
                background: "rgba(46, 160, 67, 0.1)",
                border: "1px solid #2ea043",
                borderRadius: "8px",
                color: "#3fb950",
                fontSize: "13px",
              }}
            >
              ✓ All Tavily news sources corroborate with zero conflicting
              timeline or capacity statements.
            </div>
          ) : (
            contradictions.map((c, idx) => (
              <div
                key={idx}
                style={{
                  padding: "16px",
                  backgroundColor: "#0d1117",
                  border: "1px solid #f0883e",
                  borderRadius: "8px",
                  fontSize: "13px",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    color: "#f0883e",
                    fontWeight: "bold",
                    marginBottom: "8px",
                  }}
                >
                  <span>⚠️</span> Conflicting Information Identified Across
                  Sources
                </div>
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "1fr 1fr",
                    gap: "12px",
                    marginBottom: "12px",
                  }}
                >
                  <div
                    style={{
                      background: "#161b22",
                      padding: "10px",
                      borderRadius: "6px",
                      border: "1px solid #30363d",
                    }}
                  >
                    <div
                      style={{
                        color: "#8b949e",
                        fontSize: "11px",
                        marginBottom: "4px",
                      }}
                    >
                      Claim A
                    </div>
                    <div>{c.claim_a || "Initial news reports"}</div>
                  </div>
                  <div
                    style={{
                      background: "#161b22",
                      padding: "10px",
                      borderRadius: "6px",
                      border: "1px solid #30363d",
                    }}
                  >
                    <div
                      style={{
                        color: "#8b949e",
                        fontSize: "11px",
                        marginBottom: "4px",
                      }}
                    >
                      Claim B
                    </div>
                    <div>{c.claim_b || "Subsequent update reports"}</div>
                  </div>
                </div>
                <div
                  style={{
                    background: "rgba(56, 139, 253, 0.1)",
                    border: "1px solid #58a6ff",
                    padding: "10px 14px",
                    borderRadius: "6px",
                    color: "#58a6ff",
                  }}
                >
                  <strong>Resolved Assessment:</strong>{" "}
                  {c.resolution ||
                    "Adopting conservative disruption duration bounds for risk mitigation planning."}
                </div>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
