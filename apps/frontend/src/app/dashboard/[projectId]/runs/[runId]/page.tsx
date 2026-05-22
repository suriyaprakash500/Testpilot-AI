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

  const toggleExpand = (id: string) => {
    setExpandedIds((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const loadData = async () => {
    try {
      const data = await api.getRunDetails(runId);
      setRun(data.run);
      setTestCases(data.testCases);
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

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <a
            href={`/dashboard/${projectId}`}
            className="p-1.5 rounded-md transition-colors"
            style={{ color: "var(--text-muted)" }}
            onMouseEnter={(e) => (e.currentTarget.style.color = "var(--text-primary)")}
            onMouseLeave={(e) => (e.currentTarget.style.color = "var(--text-muted)")}
          >
            <ArrowLeft size={18} />
          </a>
          <div>
            <h1 className="text-xl font-bold" style={{ color: "var(--text-primary)" }}>
              Test Run #{run.id.slice(0, 8)}
            </h1>
            <p className="text-xs mt-0.5" style={{ color: "var(--text-muted)" }}>
              Trigger: <span className="capitalize">{run.trigger}</span> • Status: <span className="capitalize font-semibold">{run.status}</span> • {new Date(run.createdAt).toLocaleString()}
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
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all duration-200 cursor-pointer"
          style={{ background: "rgba(239, 68, 68, 0.1)", border: "1px solid rgba(239, 68, 68, 0.2)", color: "var(--error)" }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = "rgba(239, 68, 68, 0.2)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "rgba(239, 68, 68, 0.1)";
          }}
        >
          <Trash2 size={14} />
          Delete Run
        </button>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mb-8">
        <div className="glass p-4">
          <div className="text-2xl font-bold" style={{ color: "var(--text-primary)" }}>{total}</div>
          <div className="text-xs" style={{ color: "var(--text-muted)" }}>Total Cases</div>
        </div>
        <div className="glass p-4">
          <div className="text-2xl font-bold" style={{ color: "var(--success)" }}>{passed}</div>
          <div className="text-xs" style={{ color: "var(--text-muted)" }}>Passed</div>
        </div>
        <div className="glass p-4">
          <div className="text-2xl font-bold" style={{ color: "var(--error)" }}>{failed}</div>
          <div className="text-xs" style={{ color: "var(--text-muted)" }}>Failed</div>
        </div>
        <div className="glass p-4">
          <div className="text-2xl font-bold" style={{ color: "var(--accent)" }}>
            {passRate}%
          </div>
          <div className="text-xs" style={{ color: "var(--text-muted)" }}>Pass Rate</div>
        </div>
      </div>

      {/* Agent Pipeline Progress */}
      <div className="glass p-4 mb-8">
        <h3 className="text-sm font-medium mb-3" style={{ color: "var(--text-secondary)" }}>Execution Pipeline</h3>
        <div className="flex flex-wrap items-center gap-2">
          {[
            { label: "Analyze", done: run.status !== "pending" },
            { label: "Plan", done: run.status !== "pending" && run.status !== "executing" },
            { label: "Execute", done: run.status === "completed" || run.status === "failed" },
            { label: "Report", done: run.status === "completed" },
          ].map((step, i) => (
            <div key={step.label} className="flex items-center gap-2">
              <div className="flex items-center gap-1.5">
                <div
                  className="w-5 h-5 rounded-full flex items-center justify-center text-xs"
                  style={{
                    background: step.done ? "var(--success)" : "var(--bg-tertiary)",
                    color: step.done ? "white" : "var(--text-muted)",
                  }}
                >
                  {step.done ? "✓" : i + 1}
                </div>
                <span className="text-xs" style={{ color: step.done ? "var(--text-primary)" : "var(--text-muted)" }}>
                  {step.label}
                </span>
              </div>
              {i < 3 && (
                <div className="w-8 h-px" style={{ background: step.done ? "var(--success)" : "var(--border)" }} />
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Test Results */}
      <h2 className="text-base font-semibold mb-4" style={{ color: "var(--text-primary)" }}>
        Test Results
      </h2>

      {testCases.length === 0 ? (
        <div className="glass p-8 text-center">
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            {run.status === "pending"
              ? "Waiting in queue to start..."
              : run.status === "executing"
              ? "Running tests and generating assertions..."
              : "No test cases were generated."}
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {testCases.map((tc, i) => (
            <div
              key={tc.id}
              className="glass overflow-hidden animate-slide-up"
              style={{ animationDelay: `${i * 0.03}s` }}
            >
              <div
                className={`flex items-start justify-between p-4 ${
                  tc.status === "failed" ? "cursor-pointer hover:bg-white/[0.02] transition-colors" : ""
                }`}
                onClick={() => tc.status === "failed" && toggleExpand(tc.id)}
              >
                <div className="flex items-start gap-3 mr-4">
                  {tc.status === "passed" ? (
                    <CheckCircle2 size={16} className="mt-0.5 flex-shrink-0" style={{ color: "var(--success)" }} />
                  ) : (
                    <XCircle size={16} className="mt-0.5 flex-shrink-0" style={{ color: "var(--error)" }} />
                  )}
                  <div className="flex flex-col">
                    <span className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
                      {tc.name}
                    </span>
                    {tc.status === "failed" && tc.error && (
                      <span className="text-xs mt-1 font-mono" style={{ color: "var(--error)", opacity: 0.85 }}>
                        Reason: {getShortErrorReason(tc.error)}
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-3 flex-shrink-0">
                  <span className="text-xs font-mono" style={{ color: "var(--text-muted)" }}>
                    {tc.duration}ms
                  </span>
                  {tc.status === "failed" && (
                    expandedIds[tc.id] ? (
                      <ChevronUp size={16} style={{ color: "var(--text-muted)" }} />
                    ) : (
                      <ChevronDown size={16} style={{ color: "var(--text-muted)" }} />
                    )
                  )}
                </div>
              </div>

              {/* Failure details with AI insights */}
              {tc.status === "failed" && tc.error && expandedIds[tc.id] && (
                <div className="px-4 pb-4 space-y-3 animate-fade-in" style={{ borderTop: "1px solid var(--border)" }}>
                  {/* Error */}
                  <div className="flex items-start gap-2 pt-3">
                    <Terminal size={14} className="mt-0.5 flex-shrink-0" style={{ color: "var(--error)" }} />
                    <div className="w-full">
                      <div className="text-xs font-medium mb-1" style={{ color: "var(--error)" }}>Error</div>
                      <code className="text-xs block p-2 rounded w-full overflow-x-auto whitespace-pre-wrap font-mono" style={{ background: "var(--bg-primary)", color: "var(--text-secondary)" }}>
                        {tc.error}
                      </code>
                    </div>
                  </div>

                  {/* AI Root Cause / Insights */}
                  {tc.logs && (
                    <div className="flex items-start gap-2">
                      <Lightbulb size={14} className="mt-0.5 flex-shrink-0" style={{ color: "var(--warning)" }} />
                      <div>
                        <div className="text-xs font-medium mb-1" style={{ color: "var(--warning)" }}>AI Debug Insights</div>
                        <p className="text-xs whitespace-pre-wrap" style={{ color: "var(--text-secondary)" }}>{tc.logs}</p>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
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
