import { useState } from "react";
import Header from "./components/Header";
import SearchBar from "./components/SearchBar";
import ScenarioChips from "./components/ScenarioChips";
import MetricCard from "./components/MetricCard";
import ActionCard from "./components/ActionCard";
import WhatIfPanel from "./components/WhatIfPanel";
import EvidencePanel from "./components/EvidencePanel";
import CriticPanel from "./components/CriticPanel";
import StreamingProgress from "./components/StreamingProgress";

const euro = new Intl.NumberFormat("de-DE", {
  style: "currency",
  currency: "EUR",
  notation: "compact",
  maximumFractionDigits: 2,
});

function runwayTone(days) {
  if (days == null) return "green";
  if (days < 3) return "red";
  if (days < 7) return "amber";
  return "green";
}

export default function App() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [revising, setRevising] = useState(false);
  const [currentStage, setCurrentStage] = useState("");
  const [streamLogs, setStreamLogs] = useState([]);
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
    setCurrentStage("research");
    setStreamLogs(["Connecting to CrisisSentinel engine..."]);
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
        setCurrentStage("done");
      } catch (err) {
        console.error("Cache load error:", err);
        setError(`Failed to load cached scenario: ${err.message}`);
      } finally {
        setLoading(false);
      }
      return;
    }

    // Path B: Live Multi-Agent Workflow with SSE Progress Streaming
    let eventSource = null;
    try {
      // Connect to the Server-Sent Events stream for live orchestration telemetry
      eventSource = new EventSource(
        `http://localhost:8000/api/disruption/scan/stream?query=${encodeURIComponent(
          query,
        )}`,
      );

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.stage) setCurrentStage(data.stage);
          if (data.message) {
            setStreamLogs((prev) => [...prev, data.message]);
          }
          if (data.stage === "done") {
            eventSource.close();
          }
        } catch {
          // ignore parsing heartbeats
        }
      };

      eventSource.onerror = () => {
        if (eventSource) eventSource.close();
      };

      // Concurrent request to the full scan intelligence & strategy pipeline
      const response = await fetch(
        "http://localhost:8000/api/disruption/scan",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
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
      setCurrentStage("done");
    } catch (err) {
      console.error("Scan error:", err);
      setError(
        `Analysis failed: ${err.message}. Ensure backend is running at http://localhost:8000.`,
      );
    } finally {
      if (eventSource) eventSource.close();
      setLoading(false);
    }
  }

  async function handleApproveMitigation() {
    if (!result?.exposure?.mitigation_alternatives?.length) return;

    setExecutionLoading(true);
    try {
      const primaryAlt = result.exposure.mitigation_alternatives[0];
      const exposedPoIds = (result.exposure.affected_open_pos || []).map(
        (po) => po.po_id || po.id,
      );

      const altSupplierId =
        primaryAlt.alt_supplier_id || primaryAlt.supplier_id || "s_eurosemi";

      const payload = {
        po_ids: exposedPoIds,
        alt_supplier_id: altSupplierId,
        target_country: result.intelligence?.impacted_country,
        target_category: result.intelligence?.impacted_category,
      };

      const res = await fetch("http://localhost:8000/api/mitigation/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const errDetail = await res.text();
        throw new Error(`Server returned ${res.status}: ${errDetail}`);
      }

      const data = await res.json();

      if (data.updated_exposure) {
        setResult((prev) => ({
          ...prev,
          exposure: data.updated_exposure,
        }));
      }

      setApproved(true);
    } catch (err) {
      console.error("Execution error:", err);
      alert(`Mitigation execution failed: ${err.message}`);
    } finally {
      setExecutionLoading(false);
    }
  }

  async function handleReviseMitigation() {
    if (!result?.brief || !result?.critique) return;

    setRevising(true);
    try {
      const res = await fetch("http://localhost:8000/api/mitigation/revise", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: query,
          brief: result.brief,
          critique: result.critique,
          exposure: result.exposure,
          claims: result.intelligence?.claims || [],
        }),
      });

      if (!res.ok) {
        const errText = await res.text();
        throw new Error(`Revision request failed (${res.status}): ${errText}`);
      }

      const data = await res.json();

      setResult((prev) => ({
        ...prev,
        brief: data.brief,
        critique: data.critique,
      }));
    } catch (err) {
      console.error("Revision error:", err);
      alert(`Failed to revise strategy: ${err.message}`);
    } finally {
      setRevising(false);
    }
  }

  async function handleResetDemo() {
    try {
      const res = await fetch("http://localhost:8000/api/demo/reset", {
        method: "POST",
      });
      if (!res.ok) throw new Error("Reset failed");
      setApproved(false);
      setResult(null);
      setQuery("");
      setCurrentStage("");
      setStreamLogs([]);
      alert("ERP state reset to clean baseline.");
    } catch (err) {
      console.error("Reset error:", err);
      alert("Failed to reset demo state.");
    }
  }

  return (
    <div className="page">
      <Header />

      {/* Mode Toggle: Offline Cache vs. Live Multi-Agent API & Demo Reset */}
      <div
        style={{
          display: "flex",
          justifyContent: "flex-end",
          alignItems: "center",
          gap: "14px",
          maxWidth: "1100px",
          margin: "0 auto 12px",
          fontSize: "12px",
          color: "#8b949e",
        }}
      >
        <button
          type="button"
          onClick={handleResetDemo}
          title="Reset SQLite database back to pre-disruption baseline"
          style={{
            background: "#21262d",
            border: "1px solid #30363d",
            color: "#c9d1d9",
            borderRadius: "6px",
            padding: "4px 10px",
            fontSize: "12px",
            cursor: "pointer",
            display: "inline-flex",
            alignItems: "center",
            gap: "5px",
          }}
        >
          <span>↺</span> Reset DB Baseline
        </button>

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

      {/* Real-time Multi-Agent Stage Stepper */}
      {loading && (
        <StreamingProgress currentStage={currentStage} logs={streamLogs} />
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
            value={
              result.exposure.critical_runway_days != null
                ? `${result.exposure.critical_runway_days}d`
                : "Safe (0 exposed)"
            }
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

      {/* Component 2: Adversarial Critic Verification & Revision Loop */}
      {result?.critique && (
        <CriticPanel
          critique={result.critique}
          onRevise={handleReviseMitigation}
          revising={revising}
        />
      )}

      {/* Component 3: Tavily Grounded Sources & Contradictions */}
      {result?.intelligence && (
        <EvidencePanel intelligence={result.intelligence} />
      )}
    </div>
  );
}
