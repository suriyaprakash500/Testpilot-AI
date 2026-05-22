"use client";

import { use, useState, useEffect } from "react";
import { Play, Clock, CheckCircle2, XCircle, AlertTriangle, ChevronRight, ArrowLeft, Trash2 } from "lucide-react";
import { api, type Project, type TestRun } from "../../../lib/api";

const STATUS_STYLES: Record<string, { icon: typeof CheckCircle2; color: string; label: string }> = {
  completed: { icon: CheckCircle2, color: "var(--success)", label: "Completed" },
  failed: { icon: XCircle, color: "var(--error)", label: "Failed" },
  executing: { icon: Play, color: "var(--accent)", label: "Running" },
  pending: { icon: Clock, color: "var(--warning)", label: "Pending" },
};

export default function ProjectDetailPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = use(params);

  const [project, setProject] = useState<Project | null>(null);
  const [runs, setRuns] = useState<TestRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [runningTest, setRunningTest] = useState(false);

  const loadData = async () => {
    try {
      const [projData, runsData] = await Promise.all([
        api.getProject(projectId),
        api.getRuns(projectId),
      ]);
      setProject(projData);
      setRuns(runsData);
    } catch (err: any) {
      setError(err.message || "Failed to load project details");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    // Poll for status updates every 5 seconds if there are running or pending tests
    const timer = setInterval(() => {
      if (runs.some(r => r.status === "pending" || r.status === "executing")) {
        api.getRuns(projectId).then(setRuns).catch(() => {});
      }
    }, 5000);

    return () => clearInterval(timer);
  }, [projectId, runs]);

  const handleRunTests = async () => {
    setRunningTest(true);
    try {
      await api.triggerRun(projectId);
      const runsData = await api.getRuns(projectId);
      setRuns(runsData);
    } catch (err: any) {
      alert(err.message || "Failed to start test run");
    } finally {
      setRunningTest(false);
    }
  };

  if (loading) {
    return (
      <div className="p-8 min-h-screen flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-indigo-500" />
          <p style={{ color: "var(--text-secondary)" }}>Loading project details...</p>
        </div>
      </div>
    );
  }

  if (error || !project) {
    return (
      <div className="p-8">
        <div className="flex items-center gap-3 mb-6">
          <a href="/dashboard" className="p-1.5 rounded-md transition-colors" style={{ color: "var(--text-muted)" }}>
            <ArrowLeft size={18} />
          </a>
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
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center gap-3 mb-2">
        <a
          href="/dashboard"
          className="p-1.5 rounded-md transition-colors"
          style={{ color: "var(--text-muted)" }}
          onMouseEnter={(e) => (e.currentTarget.style.color = "var(--text-primary)")}
          onMouseLeave={(e) => (e.currentTarget.style.color = "var(--text-muted)")}
        >
          <ArrowLeft size={18} />
        </a>
        <h1 className="text-2xl font-bold" style={{ color: "var(--text-primary)" }}>
          {project.name}
        </h1>
        <span
          className="px-2 py-0.5 rounded-full text-xs font-medium border"
          style={{ 
            background: project.status === "active" ? "rgba(34,197,94,0.1)" : "rgba(107,114,128,0.1)", 
            color: project.status === "active" ? "var(--success)" : "var(--text-muted)",
            borderColor: project.status === "active" ? "rgba(34,197,94,0.2)" : "var(--border)"
          }}
        >
          {project.status}
        </span>
      </div>
      <p className="text-sm mb-8 ml-9" style={{ color: "var(--text-muted)" }}>
        {project.repoUrl}
      </p>

      {/* Actions */}
      <div className="flex items-center gap-3 mb-6">
        <button
          id="trigger-run-btn"
          disabled={runningTest}
          onClick={handleRunTests}
          className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 cursor-pointer"
          style={{ background: "var(--gradient-1)", color: "white", opacity: runningTest ? 0.7 : 1 }}
        >
          <Play size={14} />
          {runningTest ? "Starting Run..." : "Run Tests"}
        </button>
        <a
          href={project.websiteUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 border"
          style={{ background: "var(--bg-secondary)", borderColor: "var(--border)", color: "var(--text-secondary)" }}
        >
          Visit Website
        </a>
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
            className="text-xs text-indigo-400 font-semibold hover:underline"
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
              <a
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
                  <button
                    onClick={async (e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      if (confirm("Are you sure you want to delete this test run? This cannot be undone.")) {
                        try {
                          await api.deleteRun(run.id);
                          setRuns((prev) => prev.filter((r) => r.id !== run.id));
                        } catch (err: any) {
                          alert(err.message || "Failed to delete test run");
                        }
                      }
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
              </a>
            );
          })}
        </div>
      )}
    </div>
  );
}
