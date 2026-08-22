"use client";

import Link from "next/link";
import { use, useState, useEffect } from "react";
import { 
  Play, 
  Clock, 
  CheckCircle2, 
  XCircle, 
  AlertTriangle, 
  ChevronRight, 
    ArrowLeft,
  Trash2,
  Square
} from "lucide-react";
import { api, getErrorMessage, type Project, type TestRun, type UpdateProjectInput } from "../../../lib/api";

const STATUS_STYLES: Record<string, { icon: typeof CheckCircle2; color: string; label: string }> = {
  completed: { icon: CheckCircle2, color: "var(--success)", label: "Completed" },
  failed: { icon: XCircle, color: "var(--error)", label: "Failed" },
  executing: { icon: Play, color: "var(--accent)", label: "Running" },
  pending: { icon: Clock, color: "var(--warning)", label: "Pending" },
  analyzing: { icon: Play, color: "var(--accent)", label: "Analyzing" },
  cancelled: { icon: XCircle, color: "var(--text-muted)", label: "Cancelled" },
  cancelling: { icon: Clock, color: "var(--warning)", label: "Cancelling..." },
  completed_with_failures: { icon: AlertTriangle, color: "var(--warning)", label: "Partial Failures" },
};

const ACTIVE_RUN_STATUSES = new Set(["analyzing", "pending", "executing", "cancelling"]);

export default function ProjectDetailPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = use(params);
  
  const isValidProjectId = Boolean(projectId && /^[a-zA-Z0-9_-]+$/.test(projectId));

  const [project, setProject] = useState<Project | null>(null);
  const [runs, setRuns] = useState<TestRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [runningTest, setRunningTest] = useState(false);
  const [credEmail, setCredEmail] = useState("");
  const [credPassword, setCredPassword] = useState("");
  const [savingCreds, setSavingCreds] = useState(false);
  const [credsSaved, setCredsSaved] = useState(false);

  useEffect(() => {
    if (!isValidProjectId) {
      return;
    }

    let isMounted = true;

    async function loadData() {
      try {
        const [projData, runsData] = await Promise.all([
          api.getProject(projectId),
          api.getRuns(projectId),
        ]);
        if (isMounted) {
          setProject(projData);
          setRuns(runsData);
        }
      } catch (err: unknown) {
        if (isMounted) {
          setError(getErrorMessage(err, "Failed to load project details."));
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    loadData();

    // Poll for status updates every 5 seconds
    const timer = setInterval(() => {
      api.getRuns(projectId)
        .then((latestRuns) => {
          if (isMounted) {
            setRuns(latestRuns);
          }
        })
        .catch(() => {});
    }, 5000);

    return () => {
      isMounted = false;
      clearInterval(timer);
    };
  }, [projectId, isValidProjectId]);

  const handleRunTests = async () => {
    if (!isValidProjectId) return;
    setRunningTest(true);
    try {
      await api.triggerRun(projectId);
      const runsData = await api.getRuns(projectId);
      setRuns(runsData);
    } catch (err: unknown) {
      alert(getErrorMessage(err, "Failed to start test run."));
    } finally {
      setRunningTest(false);
    }
  };

  const handleSaveCredentials = async () => {
    setSavingCreds(true);
    setCredsSaved(false);
    try {
      const updates: UpdateProjectInput = {};
      if (credEmail) updates.testEmail = credEmail;
      if (credPassword) updates.testPassword = credPassword;
      await api.updateProject(projectId, updates);
      setCredsSaved(true);
      setCredEmail("");
      setCredPassword("");
      setTimeout(() => setCredsSaved(false), 3000);
    } catch (err: unknown) {
      alert(getErrorMessage(err, "Failed to save credentials."));
    } finally {
      setSavingCreds(false);
    }
  };

    const handleDeleteRun = async (runId: string) => {
    if (confirm("Are you sure you want to delete this test run? This cannot be undone.")) {
      try {
        await api.deleteRun(runId);
        setRuns((prev) => prev.filter((r) => r.id !== runId));
      } catch (err: unknown) {
        alert(getErrorMessage(err, "Failed to delete test run."));
      }
    }
  };

  const handleCancelRun = async (runId: string) => {
    try {
      await api.cancelRun(runId);
      setRuns((prev) => prev.map((r) => (r.id === runId ? { ...r, status: "cancelling" as const } : r)));
    } catch (err: unknown) {
      alert(getErrorMessage(err, "Failed to cancel test run."));
    }
  };

  if (!isValidProjectId) {
    return (
      <div className="p-8">
        <div className="p-4 rounded-lg flex items-center gap-3" style={{ background: "rgba(239,68,68,0.1)", border: "1px solid var(--error)" }}>
          <AlertTriangle size={18} style={{ color: "var(--error)" }} />
          <span className="text-sm" style={{ color: "var(--error)" }}>Invalid Project ID format</span>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="p-8 min-h-screen flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-indigo-500" />
          <p style={{ color: "var(--text-secondary)" }}>Loading details...</p>
        </div>
      </div>
    );
  }

  if (error || !project) {
    return (
      <div className="p-8">
        <div className="flex items-center gap-3 mb-6">
          <Link href="/dashboard" className="p-1.5 rounded-md transition-colors" style={{ color: "var(--text-muted)" }}>
            <ArrowLeft size={18} />
          </Link>
          <span style={{ color: "var(--text-primary)" }}>Back to Projects</span>
        </div>
        <div className="p-4 rounded-lg flex items-center gap-3" style={{ background: "rgba(239,68,68,0.1)", border: "1px solid var(--error)" }}>
          <AlertTriangle size={18} style={{ color: "var(--error)" }} />
          <span className="text-sm" style={{ color: "var(--error)" }}>{error || "Project not found"}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div className="border-b pb-4" style={{ borderColor: "var(--border)" }}>
        <div className="flex items-center gap-3">
          <Link
            href="/dashboard"
            className="p-1 rounded-md transition-colors"
            style={{ color: "var(--text-muted)" }}
            onMouseEnter={(e) => (e.currentTarget.style.color = "var(--text-primary)")}
            onMouseLeave={(e) => (e.currentTarget.style.color = "var(--text-muted)")}
          >
            <ArrowLeft size={16} />
          </Link>
          <h1 className="text-lg font-bold tracking-tight" style={{ color: "var(--text-primary)" }}>
            {project.name}
          </h1>
          <span
            className="px-2 py-0.5 rounded-full text-[10px] font-mono border"
            style={{ 
              background: project.status === "active" ? "rgba(16,185,129,0.06)" : "rgba(100,116,139,0.06)", 
              color: project.status === "active" ? "var(--success)" : "var(--text-muted)",
              borderColor: project.status === "active" ? "rgba(16,185,129,0.15)" : "var(--border)"
            }}
          >
            {project.status.toUpperCase()}
          </span>
        </div>
        <p className="text-[11px] font-mono mt-1.5 ml-7" style={{ color: "var(--text-muted)" }}>
          {project.repoUrl}
        </p>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-3">
        <button
          id="trigger-run-btn"
          disabled={runningTest}
          onClick={handleRunTests}
          className="flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all duration-200 cursor-pointer shadow-[0_0_12px_rgba(139,92,246,0.15)]"
          style={{ background: "var(--gradient-1)", color: "white", opacity: runningTest ? 0.7 : 1 }}
        >
          <Play size={12} />
          {runningTest ? "Spawning Agents..." : "Trigger E2E Execution"}
        </button>
        <a
          href={project.websiteUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all duration-200 border"
          style={{ background: "var(--bg-secondary)", borderColor: "var(--border)", color: "var(--text-secondary)" }}
        >
          Visit Website
        </a>
      </div>

      {/* Test Credentials Settings */}
      <div className="glass p-4">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>
              Test Credentials
            </h3>
            <p className="text-[10px] mt-0.5" style={{ color: "var(--text-muted)" }}>
              Auto-login before E2E tests on auth-protected apps
            </p>
          </div>
          {credsSaved && (
            <span className="text-[10px] font-semibold text-emerald-400 animate-fade-in">✓ Saved</span>
          )}
        </div>
        <div className="flex items-end gap-3">
          <div className="flex-1">
            <label className="text-[10px] font-mono block mb-1" style={{ color: "var(--text-muted)" }}>Email</label>
            <input
              type="email"
              placeholder={project.testEmail || "test@example.com"}
              value={credEmail}
              onChange={(e) => setCredEmail(e.target.value)}
              className="w-full px-3 py-1.5 rounded-lg text-xs outline-none transition-all"
              style={{ background: "var(--bg-primary)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
              onFocus={(e) => {
                e.target.style.borderColor = "var(--accent)";
              }}
              onBlur={(e) => {
                e.target.style.borderColor = "var(--border)";
              }}
            />
          </div>
          <div className="flex-1">
            <label className="text-[10px] font-mono block mb-1" style={{ color: "var(--text-muted)" }}>Password</label>
            <input
              type="password"
              placeholder={project.testEmail ? "••••••••" : "Password"}
              value={credPassword}
              onChange={(e) => setCredPassword(e.target.value)}
              className="w-full px-3 py-1.5 rounded-lg text-xs outline-none transition-all"
              style={{ background: "var(--bg-primary)", border: "1px solid var(--border)", color: "var(--text-primary)" }}
              onFocus={(e) => {
                e.target.style.borderColor = "var(--accent)";
              }}
              onBlur={(e) => {
                e.target.style.borderColor = "var(--border)";
              }}
            />
          </div>
          <button
            disabled={savingCreds || (!credEmail && !credPassword)}
            onClick={handleSaveCredentials}
            className="px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer"
            style={{ background: "var(--gradient-1)", color: "white", opacity: savingCreds || (!credEmail && !credPassword) ? 0.5 : 1 }}
          >
            {savingCreds ? "Saving..." : "Save"}
          </button>
        </div>
      </div>

      {/* Runs */}
      <h2 className="text-base font-semibold mb-4" style={{ color: "var(--text-primary)" }}>
        Test Runs
      </h2>

      {runs.length === 0 ? (
        <div className="glass p-8 text-center flex flex-col items-center justify-center gap-2">
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
            No test runs have been triggered for this project yet.
          </p>
          <button
            className="text-xs text-indigo-400 font-semibold hover:underline cursor-pointer"
            onClick={handleRunTests}
          >
            Trigger first test run
          </button>
        </div>
      ) : (
        <div className="space-y-2">
          {runs.map((run, i) => {
            const statusConfig = STATUS_STYLES[run.status] || STATUS_STYLES["pending"]!;
            const StatusIcon = statusConfig.icon;

            return (
              <Link
                key={run.id}
                href={`/dashboard/${projectId}/runs/${run.id}`}
                className="glass flex items-center justify-between p-4 transition-all duration-200 animate-slide-up block"
                style={{ animationDelay: `${i * 0.05}s` }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = "var(--border-hover)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = "var(--border)";
                }}
              >
                <div className="flex items-center gap-4">
                  <StatusIcon size={18} style={{ color: statusConfig.color }} />
                  <div>
                    <div className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
                      Run #{run.id.slice(0, 8)}
                    </div>
                    <div className="flex items-center gap-3 mt-0.5">
                      <span className="text-xs" style={{ color: "var(--text-muted)", textTransform: "capitalize" }}>
                        Trigger: {run.trigger}
                      </span>
                      <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                        Started: {new Date(run.createdAt).toLocaleString()}
                      </span>
                      {run.completedAt && (
                        <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                          Duration: {Math.round((new Date(run.completedAt).getTime() - new Date(run.createdAt).getTime()) / 1000)}s
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                                <div className="flex items-center gap-4">
                  <span className="text-xs font-semibold px-2 py-0.5 rounded border" style={{
                    borderColor: statusConfig.color,
                    color: statusConfig.color,
                    background: `${statusConfig.color}15`,
                    textTransform: "uppercase"
                  }}>
                    {statusConfig.label}
                  </span>
                  {ACTIVE_RUN_STATUSES.has(run.status) && (
                    <button
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        handleCancelRun(run.id);
                      }}
                      disabled={run.status === "cancelling"}
                      className="p-1.5 rounded transition-colors cursor-pointer flex items-center justify-center"
                      style={{ color: "var(--warning)", background: "transparent", border: "none", opacity: run.status === "cancelling" ? 0.4 : 1 }}
                      onMouseEnter={(e) => {
                        if (!e.currentTarget.disabled) e.currentTarget.style.background = "rgba(245,158,11,0.1)";
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.background = "transparent";
                      }}
                      title="Cancel Run"
                    >
                      <Square size={14} />
                    </button>
                  )}
                  <button
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      handleDeleteRun(run.id);
                    }}
                    className="p-1.5 rounded transition-colors cursor-pointer flex items-center justify-center"
                    style={{ color: "var(--text-muted)", background: "transparent", border: "none" }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.color = "var(--error)";
                      e.currentTarget.style.background = "rgba(239,68,68,0.1)";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.color = "var(--text-muted)";
                      e.currentTarget.style.background = "transparent";
                    }}
                    title="Delete Run"
                  >
                    <Trash2 size={14} />
                  </button>
                  <ChevronRight size={14} style={{ color: "var(--text-muted)" }} />
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
