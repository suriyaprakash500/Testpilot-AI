"use client";

import Link from "next/link";
import { use, useState, useEffect } from "react";
import { ArrowLeft, CheckCircle2, XCircle, Trash2, Terminal, Code, Copy, Check } from "lucide-react";
import { api, getErrorMessage, type TestRun, type TestCase } from "../../../../../lib/api";

const TERMINAL_STATUSES = ["completed", "failed", "cancelled"];

function getPipelineSteps(status: string) {
  const stages = [
    "Repo Analysis",
    "Live Inspection",
    "Code Analysis",
    "App Understanding",
    "Test Planning",
    "Playwright Gen",
    "Browser Execution",
  ];
  const order = [
    "repo_analysis",
    "page_inspection",
    "code_analysis",
    "app_understanding",
    "test_planning",
    "playwright_gen",
    "execution",
    "completed",
  ];
  const currentIdx = order.indexOf(status);

  return stages.map((label, idx) => ({
    label,
    isDone: status === "completed" ? true : idx < currentIdx,
    isActive: status !== "completed" && idx === currentIdx,
    isFailed: status === "failed" && idx >= currentIdx && currentIdx !== -1,
  }));
}

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
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"logs" | "code">("logs");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let isMounted = true;

    async function loadData() {
      try {
        const data = await api.getRunDetails(runId);
        if (isMounted) {
          setRun(data.run);
          setTestCases(data.testCases);
          if (data.testCases.length > 0) {
            const firstFailed = data.testCases.find((tc) => tc.status === "failed");
            setSelectedCaseId(firstFailed ? firstFailed.id : data.testCases[0]?.id || null);
          }
        }
      } catch (err: unknown) {
        if (isMounted) {
          setError(getErrorMessage(err, "Failed to load run details."));
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    loadData();

    const timer = setInterval(() => {
      api.getRunDetails(runId)
        .then((data) => {
          if (isMounted && data.run) {
            setRun(data.run);
            setTestCases(data.testCases);
            if (TERMINAL_STATUSES.includes(data.run.status)) {
              clearInterval(timer);
            }
          }
        })
        .catch(() => {});
    }, 2000);

    return () => {
      isMounted = false;
      clearInterval(timer);
    };
  }, [runId]);

  const handleCopyCode = (code: string) => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDeleteRun = async () => {
    if (confirm("Delete this test run?")) {
      try {
        await api.deleteRun(runId);
        window.location.href = `/dashboard/${projectId}`;
      } catch (err: unknown) {
        alert(getErrorMessage(err, "Failed to delete test run."));
      }
    }
  };

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
        <Link href={`/dashboard/${projectId}`} className="flex items-center gap-2 mb-6 text-sm" style={{ color: "var(--text-muted)" }}>
          <ArrowLeft size={16} /> Back to Project
        </Link>
        <p className="text-sm" style={{ color: "var(--error)" }}>{error || "Run not found"}</p>
      </div>
    );
  }

  const passed = testCases.filter((t) => t.status === "passed").length;
  const failed = testCases.filter((t) => t.status === "failed").length;
  const total = testCases.length;
  const selectedCase = testCases.find((tc) => tc.id === selectedCaseId) || testCases[0];

  return (
    <div className="p-6 max-w-7xl mx-auto h-[calc(100vh-3.5rem)] flex flex-col gap-5">
      {/* Header */}
      <div className="flex items-center justify-between border-b pb-4 flex-shrink-0" style={{ borderColor: "var(--border)" }}>
        <div className="flex items-center gap-3">
          <Link
            href={`/dashboard/${projectId}`}
            className="p-1 rounded-md transition-colors"
            style={{ color: "var(--text-muted)" }}
            onMouseEnter={(e) => {
              e.currentTarget.style.color = "var(--text-primary)";
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.color = "var(--text-muted)";
            }}
          >
            <ArrowLeft size={16} />
          </Link>
          <div>
            <h1 className="text-md font-bold tracking-tight" style={{ color: "var(--text-primary)" }}>
              Test Run #{run.id.slice(0, 8)}
            </h1>
            <p className="text-[10px] font-mono mt-0.5" style={{ color: "var(--text-muted)" }}>
              {run.trigger.toUpperCase()} • {run.status.toUpperCase()} • {new Date(run.createdAt).toLocaleString()}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {total > 0 && (
            <div className="flex items-center gap-3 text-xs" style={{ color: "var(--text-secondary)" }}>
              <span className="text-emerald-400 font-semibold">{passed} passed</span>
              {failed > 0 && <span className="text-rose-400 font-semibold">{failed} failed</span>}
              <span style={{ color: "var(--text-muted)" }}>{total} total</span>
            </div>
          )}
          <button
            onClick={handleDeleteRun}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[10px] font-semibold cursor-pointer"
            style={{ background: "rgba(239, 68, 68, 0.08)", border: "1px solid rgba(239, 68, 68, 0.15)", color: "var(--error)" }}
          >
            <Trash2 size={12} />
            Delete
          </button>
        </div>
      </div>

      {/* Pipeline Steps */}
      <div className="glass p-4 flex-shrink-0">
        <div className="flex justify-between items-center mb-3">
          <h3 className="text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--text-secondary)" }}>
            Agent Pipeline
          </h3>
          <span className="text-[9px] font-mono" style={{ color: "var(--text-muted)" }}>
            {run.status.toUpperCase()}
          </span>
        </div>
        <div className="grid grid-cols-7 gap-3">
          {getPipelineSteps(run.status).map((step, i) => (
            <div key={step.label} className="flex flex-col items-center text-center gap-2">
              <div
                className={`w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-bold border transition-all duration-300 relative ${step.isDone
                    ? "bg-emerald-950 border-emerald-500 text-emerald-400"
                    : step.isActive
                      ? "border-violet-500 text-violet-400 animate-pulse shadow-[0_0_12px_rgba(139,92,246,0.4)]"
                      : step.isFailed
                        ? "bg-rose-950 border-rose-500 text-rose-400"
                        : "border-zinc-800 text-zinc-600 bg-zinc-950"
                  }`}
              >
                {step.isActive && (
                  <span className="absolute inset-0 rounded-full border border-violet-400 pulse-ring-active pointer-events-none" />
                )}
                {step.isDone ? "✓" : step.isFailed ? "!" : i + 1}
              </div>
              <span className="text-[10px] font-medium" style={{ color: step.isDone || step.isActive ? "var(--text-primary)" : "var(--text-muted)" }}>
                {step.label}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Content Area */}
      {testCases.length === 0 ? (
        <div className="glass p-12 text-center flex-1 flex flex-col items-center justify-center">
          <div className="animate-spin rounded-full h-6 w-6 border-t-2 border-b-2 border-indigo-500 mb-3" />
          <p className="text-xs" style={{ color: "var(--text-secondary)" }}>
            {run.status === "completed" ? "No test cases were generated." : "Running pipeline..."}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-5 gap-4 flex-1 overflow-hidden min-h-0">
          {/* Test Case List */}
          <div className="lg:col-span-2 glass overflow-y-auto p-3 space-y-1.5">
            <div className="text-[10px] uppercase font-bold tracking-wider px-2 mb-2 flex items-center justify-between" style={{ color: "var(--text-muted)" }}>
              <span>Test Cases</span>
              <span>{passed}/{total} passed</span>
            </div>
            {testCases.map((tc) => (
              <div
                key={tc.id}
                onClick={() => setSelectedCaseId(tc.id)}
                className={`p-3 rounded-lg border cursor-pointer transition-all ${selectedCaseId === tc.id
                    ? "bg-violet-950/20 border-violet-500/40"
                    : "bg-zinc-950/30 border-zinc-900 hover:border-zinc-700"
                  }`}
              >
                <div className="flex items-start gap-2">
                  {tc.status === "passed" ? (
                    <CheckCircle2 size={12} className="mt-0.5 flex-shrink-0 text-emerald-400" />
                  ) : (
                    <XCircle size={12} className="mt-0.5 flex-shrink-0 text-rose-400" />
                  )}
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-medium truncate" style={{ color: selectedCaseId === tc.id ? "var(--text-primary)" : "var(--text-secondary)" }}>
                      {tc.name}
                    </p>
                    {tc.error && (
                      <p className="text-[9px] font-mono mt-0.5 text-rose-400/80 truncate">
                        {tc.error.split("\n")[0]}
                      </p>
                    )}
                  </div>
                  <span className="text-[9px] font-mono flex-shrink-0" style={{ color: "var(--text-muted)" }}>{tc.duration}ms</span>
                </div>
              </div>
            ))}
          </div>

          {/* Tab Viewer */}
          <div className="lg:col-span-3 flex flex-col gap-3 min-h-0 overflow-hidden">
            {selectedCase && (
              <>
                <div className="flex items-center justify-between px-1 flex-shrink-0">
                  <div className="flex items-center gap-2">
                    {selectedCase.status === "passed" ? (
                      <CheckCircle2 size={13} className="text-emerald-400" />
                    ) : (
                      <XCircle size={13} className="text-rose-400" />
                    )}
                    <span className="text-sm font-semibold truncate" style={{ color: "var(--text-primary)" }}>
                      {selectedCase.name}
                    </span>
                  </div>

                  {/* Tab Selector */}
                  <div className="flex items-center gap-1.5 p-0.5 rounded-lg border text-[10px] font-medium" style={{ background: "var(--bg-secondary)", borderColor: "var(--border)" }}>
                    <button
                      onClick={() => setActiveTab("logs")}
                      className={`flex items-center gap-1 px-2.5 py-1 rounded-md transition-all cursor-pointer ${activeTab === "logs"
                          ? "bg-zinc-800 text-white font-semibold"
                          : "text-zinc-400 hover:text-zinc-200"
                        }`}
                    >
                      <Terminal size={10} />
                      Execution Logs
                    </button>
                    <button
                      onClick={() => setActiveTab("code")}
                      className={`flex items-center gap-1 px-2.5 py-1 rounded-md transition-all cursor-pointer ${activeTab === "code"
                          ? "bg-zinc-800 text-white font-semibold"
                          : "text-zinc-400 hover:text-zinc-200"
                        }`}
                    >
                      <Code size={10} />
                      Generated Code
                    </button>
                  </div>
                </div>

                {activeTab === "logs" ? (
                  <div className="ide-terminal flex-1 overflow-y-auto">
                    <div className="text-[10px] font-mono space-y-1 leading-relaxed">
                      {selectedCase.logs ? (
                        selectedCase.logs.split("\n").map((line, i) => (
                          <div
                            key={i}
                            className={
                              line.startsWith("✗") || line.toLowerCase().startsWith("error")
                                ? "text-rose-400"
                                : line.startsWith("✓")
                                  ? "text-emerald-400"
                                  : line.startsWith("⚡")
                                    ? "text-violet-400"
                                    : "text-zinc-400"
                            }
                          >
                            {line}
                          </div>
                        ))
                      ) : (
                        <div className="text-zinc-500">No logs available.</div>
                      )}
                      {selectedCase.error && (
                        <div className="mt-2 border-l-2 border-rose-500/50 pl-2 text-rose-400 whitespace-pre-wrap">
                          {selectedCase.error}
                        </div>
                      )}
                      <div className="text-zinc-600">
                        &gt; exit {selectedCase.status === "passed" ? "0" : "1"}
                        <span className="terminal-cursor" />
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="ide-terminal flex-1 overflow-y-auto relative flex flex-col">
                    <button
                      onClick={() => handleCopyCode(selectedCase.code || "")}
                      className="absolute top-3 right-3 p-1.5 rounded border transition-all duration-150 cursor-pointer text-zinc-400 hover:text-white bg-slate-900 border-white/[0.06] hover:bg-slate-800"
                      title="Copy Playwright Script"
                    >
                      {copied ? <Check size={11} className="text-emerald-400" /> : <Copy size={11} />}
                    </button>
                    <pre className="text-[10px] font-mono text-zinc-300 leading-relaxed overflow-x-auto select-text p-1">
                      {selectedCase.code || "# No code generated for this scenario."}
                    </pre>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
