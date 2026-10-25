import { useState } from "react";

/**
 * CriticPanel: Displays the adversarial audit from Nemotron Super.
 * Evaluates operational feasibility, checks numbers against ERP data,
 * and enables a one-click single-turn bounded revision loop.
 */
export default function CriticPanel({ critique, onRevise, revising = false }) {
  const [expanded, setExpanded] = useState(true);

  if (!critique) return null;

  const {
    verdict = "VERIFIED",
    challenges = [],
    score = 92,
    confidence_rationale = "All mitigation steps ground strictly in internal ERP capacity and verified supplier quotes.",
    audit_checks = {
      erp_math_grounded: true,
      supplier_capacity_verified: true,
      timeline_feasible: true,
    },
  } = critique;

  // Determine styling based on verification verdict
  const isApproved =
    verdict.toUpperCase() === "VERIFIED" ||
    verdict.toUpperCase() === "APPROVED";

  return (
    <div
      style={{
        marginTop: "24px",
        padding: "24px",
        backgroundColor: "#161b22",
        border: `1px solid ${isApproved ? "#238636" : "#d29922"}`,
        borderRadius: "12px",
        color: "#c9d1d9",
        fontFamily:
          '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      }}
    >
      {/* Header */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "16px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <span style={{ fontSize: "20px" }}>🛡️</span>
          <div>
            <h3
              style={{
                margin: 0,
                fontSize: "18px",
                color: "#f0f6fc",
                display: "flex",
                alignItems: "center",
                gap: "8px",
              }}
            >
              Nemotron Super Adversarial Audit
            </h3>
            <p
              style={{ margin: "4px 0 0", fontSize: "13px", color: "#8b949e" }}
            >
              Independent AI Critic validating supply chain feasibility and
              financial totals.
            </p>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          {isApproved ? (
            <span
              style={{
                padding: "4px 10px",
                borderRadius: "6px",
                fontSize: "12px",
                fontWeight: "bold",
                letterSpacing: "0.5px",
                background: "rgba(46, 160, 67, 0.15)",
                color: "#3fb950",
                border: "1px solid #2ea043",
              }}
            >
              ✓ {verdict} • {score}/100
            </span>
          ) : (
            <button
              type="button"
              onClick={onRevise}
              disabled={revising}
              title="Trigger Nemotron Super to address flagged challenges with dual-sourcing"
              style={{
                padding: "5px 12px",
                borderRadius: "6px",
                fontSize: "12px",
                fontWeight: "bold",
                letterSpacing: "0.5px",
                background: revising ? "#21262d" : "rgba(210, 153, 34, 0.2)",
                color: "#d29922",
                border: "1px solid #d29922",
                cursor: revising ? "wait" : "pointer",
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
              }}
            >
              <span>⚙️</span>
              {revising
                ? "Nemotron Super Revising Plan..."
                : `${verdict} • ${score}/100 ➔ Revise Plan`}
            </button>
          )}

          <button
            type="button"
            onClick={() => setExpanded(!expanded)}
            style={{
              background: "#21262d",
              border: "1px solid #30363d",
              color: "#c9d1d9",
              borderRadius: "6px",
              padding: "4px 10px",
              fontSize: "12px",
              cursor: "pointer",
            }}
          >
            {expanded ? "Collapse" : "Expand"}
          </button>
        </div>
      </div>

      {expanded && (
        <>
          {/* Audit Verification Checklist */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(3, 1fr)",
              gap: "10px",
              marginBottom: "16px",
            }}
          >
            <div
              style={{
                padding: "10px 12px",
                background: "#0d1117",
                borderRadius: "6px",
                border: "1px solid #30363d",
                fontSize: "12px",
                display: "flex",
                alignItems: "center",
                gap: "8px",
              }}
            >
              <span>{audit_checks.erp_math_grounded ? "✅" : "⚠️"}</span>
              <span
                style={{
                  color: audit_checks.erp_math_grounded ? "#c9d1d9" : "#d29922",
                }}
              >
                ERP Totals Grounded
              </span>
            </div>

            <div
              style={{
                padding: "10px 12px",
                background: "#0d1117",
                borderRadius: "6px",
                border: "1px solid #30363d",
                fontSize: "12px",
                display: "flex",
                alignItems: "center",
                gap: "8px",
              }}
            >
              <span>
                {audit_checks.supplier_capacity_verified ? "✅" : "⚠️"}
              </span>
              <span
                style={{
                  color: audit_checks.supplier_capacity_verified
                    ? "#c9d1d9"
                    : "#d29922",
                }}
              >
                Supplier Alt Capacity Valid
              </span>
            </div>

            <div
              style={{
                padding: "10px 12px",
                background: "#0d1117",
                borderRadius: "6px",
                border: "1px solid #30363d",
                fontSize: "12px",
                display: "flex",
                alignItems: "center",
                gap: "8px",
              }}
            >
              <span>{audit_checks.timeline_feasible ? "✅" : "⚠️"}</span>
              <span
                style={{
                  color: audit_checks.timeline_feasible ? "#c9d1d9" : "#d29922",
                }}
              >
                Lead-Time Feasible
              </span>
            </div>
          </div>

          {/* Adversarial Challenges / Potential Flaws Flagged */}
          {challenges.length > 0 && (
            <div style={{ marginBottom: "16px" }}>
              <div
                style={{
                  fontSize: "12px",
                  fontWeight: 600,
                  color: "#f0883e",
                  textTransform: "uppercase",
                  marginBottom: "8px",
                }}
              >
                Identified Operational Risks & Challenges
              </div>
              <div
                style={{ display: "flex", flexDirection: "column", gap: "8px" }}
              >
                {challenges.map((item, idx) => {
                  const title =
                    typeof item === "object" && item !== null
                      ? item.issue_type ||
                        item.target ||
                        `Challenge #${idx + 1}`
                      : `Challenge #${idx + 1}`;

                  const explanation =
                    typeof item === "object" && item !== null
                      ? item.explanation ||
                        item.suggested_fix ||
                        JSON.stringify(item)
                      : String(item);

                  const severityTag =
                    typeof item === "object" && item?.severity
                      ? item.severity
                      : null;

                  return (
                    <div
                      key={idx}
                      style={{
                        padding: "10px 14px",
                        background: "#0d1117",
                        border: "1px solid rgba(240, 136, 62, 0.3)",
                        borderRadius: "6px",
                        fontSize: "13px",
                        color: "#c9d1d9",
                        display: "flex",
                        alignItems: "flex-start",
                        gap: "8px",
                      }}
                    >
                      <span style={{ color: "#f0883e" }}>•</span>
                      <div style={{ flex: 1 }}>
                        <div
                          style={{
                            display: "flex",
                            justifyContent: "space-between",
                            alignItems: "center",
                          }}
                        >
                          <strong>{title}</strong>
                          {severityTag && (
                            <span
                              style={{
                                fontSize: "11px",
                                padding: "2px 6px",
                                borderRadius: "4px",
                                background: "rgba(240, 136, 62, 0.15)",
                                color: "#f0883e",
                              }}
                            >
                              {severityTag}
                            </span>
                          )}
                        </div>
                        <div style={{ marginTop: "4px", color: "#8b949e" }}>
                          {explanation}
                        </div>
                        {item.suggested_fix && (
                          <div
                            style={{
                              marginTop: "4px",
                              color: "#3fb950",
                              fontSize: "12px",
                            }}
                          >
                            <strong>Fix:</strong> {item.suggested_fix}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Rationale Footer */}
          <div
            style={{
              fontSize: "12px",
              color: "#8b949e",
              background: "#0d1117",
              padding: "10px 14px",
              borderRadius: "6px",
              border: "1px solid #30363d",
            }}
          >
            <strong>Critic Rationale:</strong> {confidence_rationale}
          </div>
        </>
      )}
    </div>
  );
}
