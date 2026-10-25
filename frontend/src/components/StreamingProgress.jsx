export default function StreamingProgress({ currentStage, logs = [] }) {
  const stages = [
    { key: "research", label: "Tavily Web Research", icon: "🌐" },
    { key: "extraction", label: "Nemotron Nano Extraction", icon: "🧠" },
    { key: "exposure", label: "SQLite ERP Joins", icon: "⚡" },
    { key: "strategy", label: "Nemotron Super Strategy", icon: "📋" },
    { key: "critic", label: "Nemotron Super Critic Audit", icon: "🛡️" },
  ];

  const getStageStatus = (stageKey) => {
    const stageOrder = [
      "research",
      "extraction",
      "exposure",
      "strategy",
      "critic",
      "done",
    ];
    const currentIndex = stageOrder.indexOf(currentStage);
    const thisIndex = stageOrder.indexOf(stageKey);

    if (thisIndex < currentIndex || currentStage === "done") return "completed";
    if (thisIndex === currentIndex) return "active";
    return "pending";
  };

  return (
    <div
      style={{
        maxWidth: "1100px",
        margin: "16px auto",
        padding: "16px 20px",
        backgroundColor: "#161b22",
        border: "1px solid #30363d",
        borderRadius: "10px",
        fontFamily:
          '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: "8px",
          marginBottom: "12px",
          flexWrap: "wrap",
        }}
      >
        {stages.map((st) => {
          const status = getStageStatus(st.key);
          const color =
            status === "completed"
              ? "#3fb950"
              : status === "active"
                ? "#58a6ff"
                : "#484f58";

          return (
            <div
              key={st.key}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "6px",
                fontSize: "12px",
                color: color,
                fontWeight: status === "active" ? 600 : 400,
              }}
            >
              <span>{st.icon}</span>
              <span>{st.label}</span>
              {status === "completed" && (
                <span style={{ fontSize: "11px" }}>✓</span>
              )}
            </div>
          );
        })}
      </div>

      {logs.length > 0 && (
        <div
          style={{
            fontSize: "12px",
            color: "#8b949e",
            borderTop: "1px solid #21262d",
            paddingTop: "8px",
            fontFamily: "monospace",
          }}
        >
          &gt; {logs[logs.length - 1]}
        </div>
      )}
    </div>
  );
}
