"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Clock, Play, CheckCircle2, XCircle, ChevronRight, Trash2, Square, AlertTriangle, Wrench, RefreshCw, GitPullRequest } from "lucide-react";
import { api, getErrorMessage, type TestRun } from "../../../lib/api";

const STATUS_STYLES: Record<string, { icon: typeof CheckCircle2; color: string; label: string }> = {
  completed: { icon: CheckCircle2, color: "var(--success)", label: "Completed" },
  failed: { icon: XCircle, color: "var(--error)", label: "Failed" },
  executing: { icon: Play, color: "var(--accent)", label: "Running" },
  pending: { icon: Clock, color: "var(--warning)", label: "Pending" },
  analyzing: { icon: Play, color: "var(--accent)", label: "Analyzing" },
  evaluating: { icon: Play, color: "var(--accent)", label: "Evaluating" },
  analyzing_failures: { icon: AlertTriangle, color: "var(--warning)", label: "Triaging Failures" },
  repairing: { icon: Wrench, color: "var(--warning)", label: "Auto-Repairing" },
  retrying: { icon: RefreshCw, color: "var(--accent)", label: "Retrying" },
  creating_pr: { icon: GitPullRequest, color: "var(--success)", label: "Creating PR" },
  cancelled: { icon: XCircle, color: "var(--text-muted)", label: "Cancelled" },
  cancelling: { icon: Clock, color: "var(--warning)", label: "Cancelling..." },
  completed_with_failures: { icon: AlertTriangle, color: "var(--warning)", label: "Partial Failures" },
};

const ACTIVE_RUN_STATUSES = new Set([
  "analyzing",
  "pending",
  "executing",
  "evaluating",
  "analyzing_failures",
  "repairing",
  "retrying",
  "creating_pr",
  "cancelling",
]);

interface RunWithProject extends TestRun {
  projectName: string;
}

export default function RunsPage() {
  const [runs, setRuns] = useState<RunWithProject[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadAllRuns() {
      try {
        const projects = await api.getProjects();
        const runsPromises = projects.map(async (project) => {
          const projectRuns = await api.getRuns(project.id);
          return projectRuns.map((run) => ({
            ...run,
            projectName: project.name,
          }));
        });
        const allRunsNested = await Promise.all(runsPromises);
        const allRuns = allRunsNested.flat().sort((a, b) => 
          new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
        );
        setRuns(allRuns);
      } catch (err: unknown) {
        setError(getErrorMessage(err, "Failed to load test runs."));
      } finally {
        setLoading(false);
      }
    }
    loadAllRuns();
  }, []);

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

  if (loading) {
    return (
      <div className="p-8 min-h-screen flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-indigo-500" />
          <p style={{ color: "var(--text-secondary)" }}>Loading test runs...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold" style={{ color: "var(--text-primary)" }}>Test Runs</h1>
        <p className="text-sm mt-1" style={{ color: "var(--text-secondary)" }}>
          History of all test runs triggered manually or via webhooks
        </p>
      </div>

      {error && (
        <div className="p-4 mb-6 rounded-lg text-sm" style={{ background: "rgba(239,68,68,0.1)", border: "1px solid var(--error)", color: "var(--error)" }}>
          {error}
        </div>
      )}

      {runs.length === 0 ? (
        <div className="glass p-12 text-center flex flex-col items-center gap-4">
          <div className="text-4xl">🧪</div>
          <div>
            <h3 className="text-lg font-semibold mb-1" style={{ color: "var(--text-primary)" }}>No test runs found</h3>
            <p className="text-sm max-w-sm mx-auto" style={{ color: "var(--text-secondary)" }}>
              Once you start running tests on your projects, your runs will be logged here.
            </p>
          </div>
          <Link href="/dashboard" className="px-4 py-2 rounded-lg text-sm font-semibold transition-all duration-200" style={{ background: "var(--gradient-1)", color: "white" }}>
            Go to Projects
          </Link>
        </div>
      ) : (
        <div className="space-y-2">
          {runs.map((run) => {
            const statusConfig = STATUS_STYLES[run.status] || STATUS_STYLES["pending"]!;
            const StatusIcon = statusConfig.icon;

            return (
              <Link
                key={run.id}
                href={`/dashboard/${run.projectId}/runs/${run.id}`}
                className="glass flex items-center justify-between p-4 transition-all duration-200 block"
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
                      Run #{run.id.slice(0, 8)} — {run.projectName}
                    </div>
                    <div className="flex items-center gap-3 mt-0.5">
                      <span className="text-xs" style={{ color: "var(--text-muted)", textTransform: "capitalize" }}>
                        Trigger: {run.trigger}
                      </span>
                      <span className="text-xs" style={{ color: "var(--text-muted)" }}>
                        {new Date(run.createdAt).toLocaleString()}
                      </span>
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
