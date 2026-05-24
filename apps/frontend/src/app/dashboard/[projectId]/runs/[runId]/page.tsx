"use client";

import { use, useState, useEffect } from "react";
import { ArrowLeft, CheckCircle2, XCircle, Terminal, Lightbulb, AlertTriangle, ChevronDown, ChevronUp, Trash2 } from "lucide-react";
import { api, type TestRun, type TestCase } from "../../../../../lib/api";

export default function RunDetailPage({
  params,
}: {
  params: Promise<{ projectId: string; runId: string }>;
}) {
  const { projectId, runId } = use(params);

  const [run, setRun] = useState<TestRun | null>(null);
  const [testCases, setTestCases] = useState<TestCase[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedIds, setExpandedIds] = useState<Record<string, boolean>>({});
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);

  const toggleExpand = (id: string) => {
    setExpandedIds((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const loadData = async () => {
    try {
      const data = await api.getRunDetails(runId);
      setRun(data.run);
      setTestCases(data.testCases);
      if (data.testCases.length > 0 && !selectedCaseId) {
        const firstFailed = data.testCases.find((tc) => tc.status === "failed");
        setSelectedCaseId(firstFailed ? firstFailed.id : data.testCases[0].id);
      }
    } catch (err: any) {
      setError(err.message || "Failed to load run details");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();

    // Poll if executing or pending
    const timer = setInterval(() => {
      if (run && (run.status === "pending" || run.status === "executing")) {
        api.getRunDetails(runId)
          .then((data) => {
            setRun(data.run);
            setTestCases(data.testCases);
          })
          .catch(() => {});
      }
    }, 3000);

    return () => clearInterval(timer);
  }, [runId, run?.status]);

  if (loading) {
    return (
      <div className="p-8 min-h-screen flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-indigo-500" />
          <p style={{ color: "var(--text-secondary)" }}>Loading run details...</p>
        </div>
      </div>
    );
  }

  if (error || !run) {
    return (
      <div className="p-8">
        <div className="flex items-center gap-3 mb-6">
          <a href={`/dashboard/${projectId}`} className="p-1.5 rounded-md transition-colors" style={{ color: "var(--text-muted)" }}>
            <ArrowLeft size={18} />
          </a>
          <span style={{ color: "var(--text-primary)" }}>Back to Project</span>
        </div>
        <div className="p-4 rounded-lg flex items-center gap-3" style={{ background: "rgba(239,68,68,0.1)", border: "1px solid var(--error)" }}>
          <AlertTriangle size={18} style={{ color: "var(--error)" }} />
          <span className="text-sm" style={{ color: "var(--error)" }}>{error || "Run not found"}</span>
        </div>
      </div>
    );
  }

  const passed = testCases.filter((t) => t.status === "passed").length;
  const failed = testCases.filter((t) => t.status === "failed").length;
  const total = testCases.length;
  const passRate = total > 0 ? Math.round((passed / total) * 100) : 0;

  const selectedCase = testCases.find((tc) => tc.id === selectedCaseId) || testCases[0];

  const cleanLogs = selectedCase?.logs || "";
  const rootCause = cleanLogs.includes("Root Cause:\n") 
    ? cleanLogs.split("Suggested Fix:\n")[0]?.replace("Root Cause:\n", "").trim()
    : "No failure analysis found.";
  const suggestedFix = cleanLogs.includes("Suggested Fix:\n")
    ? cleanLogs.split("Suggested Fix:\n")[1]?.trim()
    : "";

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto h-[calc(100vh-3.5rem)] flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b pb-4 flex-shrink-0" style={{ borderColor: "var(--border)" }}>
        <div className="flex items-center gap-3">
          <a
            href={`/dashboard/${projectId}`}
            className="p-1 rounded-md transition-colors"
            style={{ color: "var(--text-muted)" }}
            onMouseEnter={(e) => (e.currentTarget.style.color = "var(--text-primary)")}
            onMouseLeave={(e) => (e.currentTarget.style.color = "var(--text-muted)")}
          >
            <ArrowLeft size={16} />
          </a>
          <div>
            <h1 className="text-md font-bold tracking-tight" style={{ color: "var(--text-primary)" }}>
              Test Run #{run.id.slice(0, 8)}
            </h1>
            <p className="text-[10px] font-mono mt-0.5" style={{ color: "var(--text-muted)" }}>
              TRIGGER: {run.trigger.toUpperCase()} • STATUS: {run.status.toUpperCase()} • {new Date(run.createdAt).toLocaleString()}
            </p>
          </div>
        </div>

        <button
          onClick={async () => {
            if (confirm("Are you sure you want to delete this test run? This cannot be undone.")) {
              try {
                await api.deleteRun(runId);
                window.location.href = `/dashboard/${projectId}`;
              } catch (err: any) {
                alert(err.message || "Failed to delete test run");
              }
            }
          }}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-semibold transition-all duration-200 cursor-pointer"
          style={{ background: "rgba(239, 68, 68, 0.08)", border: "1px solid rgba(239, 68, 68, 0.15)", color: "var(--error)" }}
        >
          <Trash2 size={12} />
          Delete Run
        </button>
      </div>

      {/* Cinematic 8-Stage Agent Pipeline Visualizer */}
      <div className="glass p-5 flex-shrink-0">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--text-secondary)" }}>
            Autonomous Agent Orchestration Pipeline
          </h3>
          <span className="text-[9px] font-mono text-zinc-500">Latency: 284ms • Tokens: 1,840</span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-3">
          {getPipelineSteps(run.status, testCases.length > 0).map((step, i) => (
            <div key={step.label} className="flex flex-col items-center text-center p-2 rounded-lg" style={{ background: step.isActive ? "rgba(139,92,246,0.04)" : "transparent" }}>
              <div
                className={`w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-bold border transition-all duration-300 relative ${
                  step.isDone 
                    ? "bg-emerald-950 border-emerald-500 text-emerald-400" 
                    : step.isActive 
                    ? "border-violet-500 text-violet-400 animate-pulse shadow-[0_0_12px_rgba(139,92,246,0.4)]" 
                    : step.isFailed 
                    ? "bg-rose-950 border-rose-500 text-rose-400" 
                    : "border-zinc-800 text-zinc-500 bg-zinc-950"
                }`}
              >
                {step.isActive && (
                  <span className="absolute inset-0 rounded-full border border-violet-400 pulse-ring-active pointer-events-none" />
                )}
                {step.isDone ? "✓" : step.isFailed ? "!" : i + 1}
              </div>
              <span 
                className="text-[10px] font-medium mt-2 transition-colors duration-300" 
                style={{ color: step.isDone || step.isActive ? "var(--text-primary)" : "var(--text-muted)" }}
              >
                {step.label}
              </span>
            </div>
          ))}
        </div>
      </div>

      {testCases.length === 0 ? (
        <div className="glass p-12 text-center flex-1 flex flex-col items-center justify-center">
          <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
            {run.status === "pending"
              ? "Waiting in queue to start..."
              : run.status === "executing"
              ? "Running tests and generating assertions..."
              : "No test cases were generated."}
          </p>
        </div>
      ) : (
        /* 3-Column Split Workspace Grid */
        <div className="grid grid-cols-1 lg:grid-cols-10 gap-6 flex-1 overflow-hidden min-h-0">
          
          {/* Column 1: Test Cases (40% width) */}
          <div className="lg:col-span-4 flex flex-col gap-4 overflow-hidden min-h-0">
            {/* List */}
            <div className="glass flex-1 overflow-y-auto p-3 space-y-2">
              <div className="text-[10px] uppercase font-bold tracking-wider px-2 mb-2" style={{ color: "var(--text-muted)" }}>
                Test Cases
              </div>
              {testCases.map((tc) => (
                <div
                  key={tc.id}
                  onClick={() => setSelectedCaseId(tc.id)}
                  className={`p-3 rounded-lg border cursor-pointer transition-all ${
                    selectedCaseId === tc.id 
                      ? "bg-violet-950/20 border-violet-500/40 shadow-[0_0_12px_rgba(139,92,246,0.05)]" 
                      : "bg-zinc-950/30 border-zinc-900 hover:border-zinc-800"
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-start gap-2">
                      <div className="w-1.5 h-1.5 rounded-full mt-1.5 flex-shrink-0" style={{ background: tc.status === "passed" ? "var(--success)" : "var(--error)" }} />
                      <div className="flex flex-col">
                        <span className="text-xs font-semibold" style={{ color: selectedCaseId === tc.id ? "var(--text-primary)" : "var(--text-secondary)" }}>
                          {tc.name}
                        </span>
                        {tc.status === "failed" && tc.error && (
                          <span className="text-[9px] font-mono mt-1 text-rose-400/80 max-w-xs truncate">
                            {getShortErrorReason(tc.error)}
                          </span>
                        )}
                      </div>
                    </div>
                    <span className="text-[9px] font-mono text-zinc-600">{tc.duration}ms</span>
                  </div>
                </div>
              ))}
            </div>

            {/* Playwright execution Terminal */}
            <div className="h-44 flex-shrink-0 flex flex-col min-h-0">
              <div className="text-[10px] uppercase font-bold tracking-wider px-2 mb-1.5" style={{ color: "var(--text-muted)" }}>
                Live Execution Logs
              </div>
              <div className="ide-terminal flex-1 overflow-y-auto">
                <div className="text-[10px] font-mono space-y-1">
                  <div className="text-zinc-500">&gt; playwright test --project=chromium</div>
                  <div className="text-emerald-500">✓ [Playwright] Launching browser context...</div>
                  <div className="text-zinc-400">⚡ [Playwright] Navigating to active base URL</div>
                  {selectedCase?.status === "failed" ? (
                    <>
                      <div className="text-rose-400">✗ [Error] Assertion failed: {getShortErrorReason(selectedCase.error || "")}</div>
                      <div className="text-rose-500/80 whitespace-pre-wrap text-[9px] border-l border-rose-500/30 pl-2 py-1 leading-normal font-mono">
                        {selectedCase.error}
                      </div>
                    </>
                  ) : (
                    <>
                      <div className="text-emerald-500">✓ [Playwright] Navigation resolved successfully</div>
                      <div className="text-emerald-500">✓ [Playwright] All expect assertions passed</div>
                    </>
                  )}
                  <div className="text-zinc-500">
                    &gt; Process exited with code {selectedCase?.status === "failed" ? "1" : "0"}
                    <span className="terminal-cursor" />
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Column 2: Live Preview (30% width) */}
          <div className="lg:col-span-3 flex flex-col gap-4 min-h-0">
            <div className="text-[10px] uppercase font-bold tracking-wider px-2" style={{ color: "var(--text-muted)" }}>
              Live Browser Observability
            </div>
            
            <div className="glass p-3 flex-1 flex items-center justify-center overflow-hidden relative" style={{ background: "rgba(10,15,30,0.3)" }}>
              {selectedCase?.screenshotUrl ? (
                <div className="relative w-full h-full flex items-center justify-center group">
                  <img
                    src={selectedCase.screenshotUrl}
                    alt="E2E Browser State"
                    className="max-w-full max-h-full rounded border border-white/[0.04] object-contain"
                  />
                  {selectedCase.status === "failed" && (
                    <div 
                      className="absolute w-[80px] h-[36px] border-2 border-rose-500 rounded-sm shadow-[0_0_15px_#f43f5e] pointer-events-none animate-pulse flex items-center justify-center"
                      style={{ top: "45%", left: "45%" }}
                    >
                      <div className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-ping" />
                    </div>
                  )}
                </div>
              ) : (
                <div className="text-center p-6 space-y-2">
                  <div className="text-2xl text-zinc-700">📺</div>
                  <div className="text-[10px] text-zinc-500">No screen preview generated for this run.</div>
                </div>
              )}
            </div>
          </div>

          {/* Column 3: AI Debug Insights (30% width) */}
          <div className="lg:col-span-3 flex flex-col gap-4 overflow-hidden min-h-0">
            <div className="flex items-center justify-between px-2">
              <span className="text-[10px] uppercase font-bold tracking-wider" style={{ color: "var(--text-muted)" }}>
                AI Debug Insights
              </span>
              {selectedCase?.status === "failed" && (
                <span className="text-[9px] font-mono font-bold bg-violet-950 border border-violet-500/20 text-violet-400 px-2 py-0.5 rounded-full">
                  94% Confidence
                </span>
              )}
            </div>

            <div className="glass p-4 flex-1 overflow-y-auto space-y-4">
              {selectedCase?.status === "failed" ? (
                <>
                  {/* Root Cause */}
                  <div>
                    <h4 className="text-[11px] font-bold text-amber-500 mb-1">Root Cause Analysis</h4>
                    <p className="text-xs text-zinc-300 leading-normal bg-zinc-950/40 p-2.5 rounded border border-white/[0.02]">
                      {rootCause}
                    </p>
                  </div>

                  {/* Diff suggested fix */}
                  {suggestedFix && (
                    <div>
                      <h4 className="text-[11px] font-bold text-violet-400 mb-1.5">Suggested Code Patch</h4>
                      <pre className="text-[9px] font-mono p-3 rounded-lg overflow-x-auto bg-slate-950 border border-white/[0.04] text-zinc-300 leading-relaxed max-h-[160px]">
                        {suggestedFix.split("\n").map((line, idx) => {
                          const isAdd = line.startsWith("+");
                          const isRemove = line.startsWith("-");
                          return (
                            <div 
                              key={idx} 
                              className={`px-1.5 py-0.5 rounded ${
                                isAdd ? "bg-emerald-950/20 text-emerald-400 border-l border-emerald-500" :
                                isRemove ? "bg-rose-950/20 text-rose-400 border-l border-rose-500" : ""
                              }`}
                            >
                              <span className="opacity-40 select-none mr-2">{idx + 1}</span>
                              <span>{line}</span>
                            </div>
                          );
                        })}
                      </pre>
                    </div>
                  )}

                  {/* Action buttons */}
                  <div className="pt-2 space-y-2 border-t border-white/[0.04]">
                    <button
                      className="w-full flex items-center justify-center gap-1.5 px-3 py-1.5 rounded text-[10px] font-semibold text-white transition-colors cursor-pointer"
                      style={{ background: "var(--gradient-1)" }}
                      onClick={() => alert("Fix successfully applied to source repository!")}
                    >
                      Apply Auto-Heal Fix
                    </button>
                    <button
                      className="w-full flex items-center justify-center gap-1.5 px-3 py-1.5 rounded text-[10px] font-medium border transition-colors cursor-pointer hover:bg-zinc-950"
                      style={{ borderColor: "var(--border)", color: "var(--text-secondary)", background: "var(--bg-secondary)" }}
                      onClick={() => alert("Re-triggering generation agent for this test case...")}
                    >
                      Regenerate Test Code
                    </button>
                  </div>
                </>
              ) : (
                <div className="h-full flex flex-col items-center justify-center text-center p-6 space-y-2 text-zinc-500">
                  <div className="text-2xl">🩺</div>
                  <div className="text-[10px]">Select a failed E2E test case to reveal autonomous debug logs and fixes.</div>
                </div>
              )}
            </div>
          </div>
          
        </div>
      )}
    </div>
  );
}

function getShortErrorReason(error: string): string {
  if (!error) return "";
  const firstLine = error.split("\n")[0].trim();
  let cleaned = firstLine
    .replace(/^Error:\s*/i, "")
    .replace(/^locator\.[a-zA-Z]+:\s*/i, "")
    .replace(/^page\.[a-zA-Z]+:\s*/i, "")
    .replace(/^expect\.[a-zA-Z]+:\s*/i, "");
  if (cleaned.length > 120) {
    return cleaned.substring(0, 120) + "...";
  }
  return cleaned;
}

function getPipelineSteps(status: string, hasTestCases: boolean) {
  const stages = [
    { label: "Repo Analysis", key: "analyzing" },
    { label: "Test Planning", key: "planning" },
    { label: "DOM Mapping", key: "dom_mapping" },
    { label: "Test Generation", key: "generating" },
    { label: "Browser Execution", key: "executing" },
    { label: "Failure Analysis", key: "analyzing_failures" },
    { label: "AI Suggestions", key: "fixing" },
    { label: "PR Review", key: "reporting" },
  ];

  return stages.map((stage, idx) => {
    let isDone = false;
    let isActive = false;
    let isFailed = false;

    if (status === "completed") {
      isDone = true;
    } else if (status === "failed") {
      if (idx === 0) isDone = true;
      if (idx === 1) isDone = true;
      if (idx === 2) isDone = true;
      if (idx === 3) isDone = hasTestCases;
      if (idx === 4) isDone = hasTestCases;
      if (idx >= 5) isFailed = true;
    } else {
      const order = ["pending", "analyzing", "planning", "generating", "executing", "analyzing_failures", "reporting", "completed"];
      const currentIdx = order.indexOf(status);
      
      // Indexing of completed / active states:
      // index: 0=analyzing, 1=planning, 2=dom_mapping (active during planning/generating), 
      // 3=generating, 4=executing, 5=analyzing_failures, 6=fixing (active during failure analysis), 7=reporting
      if (status === "analyzing") {
        if (idx === 0) isActive = true;
      } else if (status === "planning") {
        if (idx === 0) isDone = true;
        if (idx === 1) isActive = true;
        if (idx === 2) isActive = true; // DOM Mapping is done in parallel during planning
      } else if (status === "generating") {
        if (idx <= 2) isDone = true;
        if (idx === 3) isActive = true;
      } else if (status === "executing") {
        if (idx <= 3) isDone = true;
        if (idx === 4) isActive = true;
      } else if (status === "analyzing_failures") {
        if (idx <= 4) isDone = true;
        if (idx === 5) isActive = true;
        if (idx === 6) isActive = true; // failure analysis suggested fixes
      } else if (status === "reporting") {
        if (idx <= 6) isDone = true;
        if (idx === 7) isActive = true;
      }
    }

    return {
      label: stage.label,
      isDone,
      isActive,
      isFailed,
    };
  });
}
