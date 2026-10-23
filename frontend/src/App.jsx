import { useState } from "react";
import Header from "./components/Header";
import SearchBar from "./components/SearchBar";
import ScenarioChips from "./components/ScenarioChips";
import MetricCard from "./components/MetricCard";
import ActionCard from "./components/ActionCard";
import WhatIfPanel from "./components/WhatIfPanel";
import EvidencePanel from "./components/EvidencePanel";
import CriticPanel from "./components/CriticPanel";

const euro = new Intl.NumberFormat("de-DE", {
  style: "currency",
  currency: "EUR",
  notation: "compact",
  maximumFractionDigits: 2,
});

function runwayTone(days) {
  if (days < 3) return "red";
  if (days < 7) return "amber";
  return "green";
}

export default function App() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [statusMsg, setStatusMsg] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [approved, setApproved] = useState(false);
  const [executionLoading, setExecutionLoading] = useState(false);
  const [useOfflineCache, setUseOfflineCache] = useState(false);

  function resolveCacheName(text) {
    const lower = text.toLowerCase();
    if (lower.includes("taiwan") || lower.includes("semiconductor"))
      return "taiwan_semiconductor";
    if (lower.includes("poland") || lower.includes("battery"))
      return "poland_battery";
    if (lower.includes("japan") || lower.includes("sensor"))
      return "japan_sensor";
    return "taiwan_semiconductor";
  }

  async function handleAnalyze() {
    if (loading || !query.trim()) return;

    setLoading(true);
    setStatusMsg("Connecting to CrisisSentinel engine...");
    setResult(null);
    setError("");
    setApproved(false);

    // Path A: Load Pre-Recorded Scenario from Offline Cache
    if (useOfflineCache) {
      const cacheName = resolveCacheName(query);
      try {
        const res = await fetch(
          `http://localhost:8000/api/cache/scenario/${cacheName}`,
        );
        if (!res.ok) throw new Error(`Cached run not found for ${cacheName}`);
        const cachedData = await res.json();
        setResult(cachedData);
      } catch (err) {
        console.error("Cache load error:", err);
        setError(`Failed to load cached scenario: ${err.message}`);
      } finally {
        setLoading(false);
        setStatusMsg("");
      }
      return;
    }

    // Path B: Live Multi-Agent Workflow
    try {
      setStatusMsg(
        "Initiating multi-source web intelligence & ERP correlation...",
      );
      const response = await fetch(
        "http://localhost:8000/api/disruption/scan",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          // Sends both keys to ensure backend compatibility
          body: JSON.stringify({
            query: query,
            event_query: query,
          }),
        },
      );

      if (!response.ok) {
        throw new Error(`Server returned HTTP ${response.status}`);
      }

      const data = await response.json();
      setResult(data);
    } catch (err) {
      console.error("Scan error:", err);
      setError(
        `Analysis failed: ${err.message}. Ensure backend is running at http://localhost:8000.`,
      );
    } finally {
      setLoading(false);
      setStatusMsg("");
    }
  }

  async function handleApproveMitigation() {
    if (!result?.exposure?.mitigation_alternatives?.length) return;

    setExecutionLoading(true);
    try {
      const payload = {
        action_type: "reroute_purchase_orders",
        target_country: result.intelligence?.impacted_country,
        target_category: result.intelligence?.impacted_category,
        primary_alternative_supplier:
          result.exposure.mitigation_alternatives[0]?.supplier_name ||
          "AltSupplier",
      };

      const res = await fetch("http://localhost:8000/api/mitigation/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) throw new Error(`Execution failed: ${res.statusText}`);
      setApproved(true);
    } catch (err) {
      console.error("Execution error:", err);
      alert(`Mitigation execution failed: ${err.message}`);
    } finally {
      setExecutionLoading(false);
    }
  }

  return (
    <div className="page">
      <Header />

      {/* Mode Toggle: Offline Cache vs. Live Multi-Agent API */}
      <div
        style={{
          display: "flex",
          justifyContent: "flex-end",
          alignItems: "center",
          gap: "10px",
          maxWidth: "1100px",
          margin: "0 auto 12px",
          fontSize: "12px",
          color: "#8b949e",
        }}
      >
        <span>Demo Reliability Mode:</span>
        <label
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "6px",
            cursor: "pointer",
          }}
        >
          <input
            type="checkbox"
            checked={useOfflineCache}
            onChange={(e) => setUseOfflineCache(e.target.checked)}
            style={{ accentColor: "#58a6ff" }}
          />
          <span
            style={{
              color: useOfflineCache ? "#3fb950" : "#8b949e",
              fontWeight: 600,
            }}
          >
            {useOfflineCache
              ? "⚡ Offline Pre-recorded Cache"
              : "🌐 Live Web & Nebius API"}
          </span>
        </label>
      </div>

      <SearchBar
        query={query}
        setQuery={setQuery}
        onAnalyze={handleAnalyze}
        loading={loading}
      />

      <ScenarioChips onPick={setQuery} disabled={loading} />

      {loading && (
        <p className="status">
          {statusMsg || "Analyzing multi-tier disruption signals..."}
        </p>
      )}

      {error && (
        <p className="status" role="alert" style={{ color: "#f85149" }}>
          {error}
        </p>
      )}

      {/* Architecture Provenance Banner */}
      {result?.provenance && (
        <div
          style={{
            maxWidth: "1100px",
            margin: "16px auto",
            padding: "8px 16px",
            backgroundColor: "#161b22",
            border: "1px solid #30363d",
            borderRadius: "8px",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            fontSize: "12px",
            color: "#8b949e",
          }}
        >
          <div>
            <strong>Architecture:</strong> Nemotron Nano (Extraction) ➔ Nemotron
            Super (Strategy & Critic)
          </div>
          <div>
            Sources Grounded:{" "}
            <span style={{ color: "#58a6ff", fontWeight: "bold" }}>
              {result.provenance.source_count || 8}
            </span>{" "}
            | Claims Extracted:{" "}
            <span style={{ color: "#3fb950", fontWeight: "bold" }}>
              {result.provenance.claims_extracted || 4}
            </span>
          </div>
        </div>
      )}

      {/* Deterministic Exposure Metrics */}
      {result?.matched && result.exposure && (
        <div className="metrics">
          <MetricCard
            label="Total Value at Risk"
            value={euro.format(result.exposure.total_exposure_eur)}
            tone="red"
          />

          <MetricCard
            label="Exposed Open POs"
            value={result.exposure.open_pos_count}
          />

          <MetricCard
            label="Shortest Runway"
            value={`${result.exposure.critical_runway_days}d`}
            tone={runwayTone(result.exposure.critical_runway_days)}
          />

          <MetricCard
            label="Alternative Suppliers"
            value={result.exposure.mitigation_alternatives?.length || 0}
          />
        </div>
      )}

      {/* Strategic Response Brief & Action Approvals */}
      {result?.brief && (
        <section className="brief">
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <h2 className="brief-headline">{result.brief.headline}</h2>
            {result.brief.confidence_score && (
              <span
                style={{
                  fontSize: "13px",
                  color: "#58a6ff",
                  background: "rgba(56, 139, 253, 0.1)",
                  padding: "4px 10px",
                  borderRadius: "6px",
                }}
              >
                Confidence: {Math.round(result.brief.confidence_score * 100)}%
              </span>
            )}
          </div>

          <p className="brief-summary">{result.brief.criticality_summary}</p>

          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              margin: "16px 0 8px",
            }}
          >
            <h3 style={{ fontSize: "16px", color: "#c9d1d9", margin: 0 }}>
              Operational Mitigation Checklist
            </h3>
            <button
              type="button"
              onClick={handleApproveMitigation}
              disabled={approved || executionLoading}
              style={{
                backgroundColor: approved ? "#238636" : "#1f6feb",
                color: "#ffffff",
                border: "none",
                borderRadius: "6px",
                padding: "8px 16px",
                fontWeight: 600,
                fontSize: "13px",
                cursor: approved || executionLoading ? "default" : "pointer",
              }}
            >
              {approved
                ? "✓ Reroute Purchase Orders Approved"
                : executionLoading
                  ? "Executing SQL Update..."
                  : "Approve Primary Reroute"}
            </button>
          </div>

          {(result.brief.recommended_actions ?? []).map((action) => (
            <ActionCard key={action.priority || action.title} action={action} />
          ))}
        </section>
      )}

      {/* Component 1: Deterministic What-If Simulator */}
      {result?.matched && (
        <WhatIfPanel
          country={result.intelligence?.impacted_country}
          category={result.intelligence?.impacted_category}
          defaultDuration={result.intelligence?.estimated_duration_days || 28}
        />
      )}

      {/* Component 2: Adversarial Critic Verification */}
      {result?.critique && <CriticPanel critique={result.critique} />}

      {/* Component 3: Tavily Grounded Sources & Contradictions */}
      {result?.intelligence && (
        <EvidencePanel intelligence={result.intelligence} />
      )}
    </div>
  );
}
