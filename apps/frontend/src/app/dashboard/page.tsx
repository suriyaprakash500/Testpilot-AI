"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Plus, GitBranch, ChevronRight, AlertTriangle, ExternalLink, Layers } from "lucide-react";
import { api, type Project, type AnalyticsData } from "../../lib/api";

export default function DashboardPage() {
  const router = useRouter();
  const [projectsList, setProjectsList] = useState<Project[]>([]);
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Modal states
  const [showNewProject, setShowNewProject] = useState(false);
  const [newRepoUrl, setNewRepoUrl] = useState("");
  const [newWebsiteUrl, setNewWebsiteUrl] = useState("");
  const [newTestEmail, setNewTestEmail] = useState("");
  const [newTestPassword, setNewTestPassword] = useState("");
  const [creating, setCreating] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);

  const formatTimeSaved = (ms: number): string => {
    if (!ms || ms <= 0) return "0h";
    const hours = ms / 3600000;
    if (hours >= 0.1) {
      return `${hours.toFixed(1)} hrs`;
    }
    const minutes = ms / 60000;
    if (minutes >= 0.1) {
      return `${minutes.toFixed(1)} mins`;
    }
    return `${(ms / 1000).toFixed(0)}s`;
  };

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      router.push("/");
      return;
    }

    async function loadDashboardData() {
      try {
        const [projectsData, analyticsData] = await Promise.all([
          api.getProjects(),
          api.getAnalytics(),
        ]);
        setProjectsList(projectsData);
        setAnalytics(analyticsData);
      } catch (err: any) {
        setError(err.message || "Failed to load dashboard data");
      } finally {
        setLoading(false);
      }
    }

    loadDashboardData();
  }, [router]);

  const handleCreateProject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newRepoUrl || !newWebsiteUrl) return;

    setCreating(true);
    setModalError(null);

    try {
      const newProj = await api.createProject({
        repoUrl: newRepoUrl,
        websiteUrl: newWebsiteUrl,
        ...(newTestEmail ? { testEmail: newTestEmail } : {}),
        ...(newTestPassword ? { testPassword: newTestPassword } : {}),
      });
      setProjectsList((prev) => [...prev, newProj]);
      setShowNewProject(false);
      setNewRepoUrl("");
      setNewWebsiteUrl("");
      setNewTestEmail("");
      setNewTestPassword("");
    } catch (err: any) {
      setModalError(err.message || "Failed to create project");
    } finally {
      setCreating(false);
    }
  };

  if (loading) {
    return (
      <div className="p-8 min-h-screen flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-indigo-500" />
          <p style={{ color: "var(--text-secondary)" }}>Loading projects...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-8 space-y-8 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between border-b pb-6" style={{ borderColor: "var(--border)" }}>
        <div>
          <h1 className="text-xl font-bold tracking-tight" style={{ color: "var(--text-primary)" }}>
            Autonomous QA Workspaces
          </h1>
          <p className="text-xs mt-1" style={{ color: "var(--text-secondary)" }}>
            Review connected repositories and execution metrics
          </p>
        </div>
        <button
          id="new-project-btn"
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold cursor-pointer transition-all hover:opacity-90 shadow-[0_0_12px_rgba(139,92,246,0.2)]"
          style={{ background: "var(--gradient-1)", color: "white" }}
          onClick={() => setShowNewProject(true)}
        >
          <Plus size={14} />
          Connect Repository
        </button>
      </div>

      {error && (
        <div className="p-4 rounded-lg flex items-center gap-3" style={{ background: "rgba(239,68,68,0.06)", border: "1px solid var(--error)" }}>
          <AlertTriangle size={16} style={{ color: "var(--error)" }} />
          <span className="text-xs" style={{ color: "var(--error)" }}>{error}</span>
        </div>
      )}

      {/* Hero Metrics Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
        {[
          { label: "Total Tests Executed", value: analytics ? String(analytics.totalCases) : "0", detail: "Evaluated assertions" },
          { label: "Average Pass Rate", value: analytics ? `${analytics.averagePassRate}%` : "0%", detail: "Pass efficiency" },
          { label: "Total Time Saved", value: analytics ? formatTimeSaved(analytics.totalTimeSavedMs) : "0 hrs", detail: "Parallel runs" },
          { label: "Failed Run Alerts", value: analytics ? String(analytics.failedRunAlerts) : "0", detail: "Requires attention" },
          { label: "Total Suite Runs", value: analytics ? String(analytics.totalRuns) : "0", detail: "All-time executions" },
        ].map((stat) => (
          <div key={stat.label} className="glass p-4 relative overflow-hidden group hover:translate-y-[-2px] duration-300">
            <div className="text-[10px] tracking-tight uppercase" style={{ color: "var(--text-muted)" }}>
              {stat.label}
            </div>
            <div className="text-xl font-bold mt-2" style={{ color: "var(--text-primary)" }}>
              {stat.value}
            </div>
            <div className="text-[9px] mt-1.5 font-mono" style={{ color: "var(--text-secondary)" }}>
              {stat.detail}
            </div>
          </div>
        ))}
      </div>

      {/* Workspace List */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>
            Active Workspaces
          </h2>
          <span className="text-[10px] font-mono text-zinc-500">{projectsList.length} Connected</span>
        </div>

        {projectsList.length === 0 ? (
          <div className="glass p-12 text-center flex flex-col items-center justify-center gap-4">
            <div className="w-12 h-12 rounded-full bg-zinc-900 border border-zinc-800 flex items-center justify-center text-xl">📦</div>
            <div>
              <h3 className="text-sm font-semibold mb-1" style={{ color: "var(--text-primary)" }}>No connected repositories</h3>
              <p className="text-xs max-w-xs mx-auto" style={{ color: "var(--text-secondary)" }}>
                Connect your repository to start generating Playwright tests automatically.
              </p>
            </div>
            <button
              className="px-4 py-2 rounded-lg text-xs font-semibold transition-all duration-200 cursor-pointer"
              style={{ background: "var(--gradient-1)", color: "white" }}
              onClick={() => setShowNewProject(true)}
            >
              Connect Workspace
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            {projectsList.map((project, i) => (
              <a
                key={project.id}
                href={`/dashboard/${project.id}`}
                className="glass flex items-center justify-between p-4 transition-all duration-200 animate-slide-up block"
                style={{ animationDelay: `${i * 0.05}s` }}
              >
                <div className="flex items-center gap-4">
                  <div
                    className="w-9 h-9 rounded-lg flex items-center justify-center border flex-shrink-0"
                    style={{ background: "var(--accent-glow)", borderColor: "rgba(139, 92, 246, 0.15)" }}
                  >
                    <Layers size={16} style={{ color: "var(--accent-purple)" }} />
                  </div>
                  <div>
                    <div className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                      {project.name}
                    </div>
                    <div className="flex items-center gap-4 mt-1 font-mono text-[10px]" style={{ color: "var(--text-secondary)" }}>
                      <span className="flex items-center gap-1">
                        <GitBranch size={10} style={{ color: "var(--text-muted)" }} />
                        {project.repoUrl.split("/").slice(-2).join("/")}
                      </span>
                      <span className="flex items-center gap-1">
                        <ExternalLink size={10} style={{ color: "var(--text-muted)" }} />
                        {project.websiteUrl}
                      </span>
                    </div>
                  </div>
                </div>

                <ChevronRight size={14} style={{ color: "var(--text-muted)" }} />
              </a>
            ))}
          </div>
        )}
      </div>

      {/* New Project Modal */}
      {showNewProject && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center"
          style={{ background: "rgba(0,0,0,0.6)", backdropFilter: "blur(4px)" }}
          onClick={() => setShowNewProject(false)}
        >
          <form
            onSubmit={handleCreateProject}
            className="glass w-full max-w-md p-6 animate-slide-up"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="text-lg font-semibold mb-4" style={{ color: "var(--text-primary)" }}>
              New Project
            </h2>

            {modalError && (
              <div className="p-3 mb-4 rounded-lg text-xs" style={{ background: "rgba(239,68,68,0.1)", border: "1px solid var(--error)", color: "var(--error)" }}>
                {modalError}
              </div>
            )}

            <div className="space-y-4">
              <div>
                <label className="text-sm font-medium mb-1.5 block" style={{ color: "var(--text-secondary)" }}>
                  GitHub Repository URL
                </label>
                <input
                  id="modal-repo-url"
                  type="url"
                  required
                  placeholder="https://github.com/username/repo"
                  value={newRepoUrl}
                  onChange={(e) => setNewRepoUrl(e.target.value)}
                  className="w-full px-3 py-2.5 rounded-lg text-sm outline-none transition-all"
                  style={{
                    background: "var(--bg-primary)",
                    border: "1px solid var(--border)",
                    color: "var(--text-primary)",
                  }}
                  onFocus={(e) => (e.target.style.borderColor = "var(--accent)")}
                  onBlur={(e) => (e.target.style.borderColor = "var(--border)")}
                />
              </div>
              <div>
                <label className="text-sm font-medium mb-1.5 block" style={{ color: "var(--text-secondary)" }}>
                  Website URL
                </label>
                <input
                  id="modal-website-url"
                  type="url"
                  required
                  placeholder="https://your-app.vercel.app"
                  value={newWebsiteUrl}
                  onChange={(e) => setNewWebsiteUrl(e.target.value)}
                  className="w-full px-3 py-2.5 rounded-lg text-sm outline-none transition-all"
                  style={{
                    background: "var(--bg-primary)",
                    border: "1px solid var(--border)",
                    color: "var(--text-primary)",
                  }}
                  onFocus={(e) => (e.target.style.borderColor = "var(--accent)")}
                  onBlur={(e) => (e.target.style.borderColor = "var(--border)")}
                />
              </div>

              {/* Test Credentials */}
              <div className="border-t pt-3 mt-1" style={{ borderColor: "var(--border)" }}>
                <label className="text-xs font-medium mb-2 block" style={{ color: "var(--text-muted)" }}>
                  Test Credentials (Optional) — for auto-login on auth-protected apps
                </label>
                <div className="grid grid-cols-2 gap-3">
                  <input
                    id="modal-test-email"
                    type="email"
                    placeholder="test@example.com"
                    value={newTestEmail}
                    onChange={(e) => setNewTestEmail(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg text-sm outline-none transition-all"
                    style={{
                      background: "var(--bg-primary)",
                      border: "1px solid var(--border)",
                      color: "var(--text-primary)",
                    }}
                    onFocus={(e) => (e.target.style.borderColor = "var(--accent)")}
                    onBlur={(e) => (e.target.style.borderColor = "var(--border)")}
                  />
                  <input
                    id="modal-test-password"
                    type="password"
                    placeholder="Password"
                    value={newTestPassword}
                    onChange={(e) => setNewTestPassword(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg text-sm outline-none transition-all"
                    style={{
                      background: "var(--bg-primary)",
                      border: "1px solid var(--border)",
                      color: "var(--text-primary)",
                    }}
                    onFocus={(e) => (e.target.style.borderColor = "var(--accent)")}
                    onBlur={(e) => (e.target.style.borderColor = "var(--border)")}
                  />
                </div>
              </div>
              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  className="flex-1 px-4 py-2.5 rounded-lg text-sm font-medium cursor-pointer"
                  style={{ background: "var(--bg-tertiary)", color: "var(--text-secondary)" }}
                  onClick={() => setShowNewProject(false)}
                >
                  Cancel
                </button>
                <button
                  id="create-project-btn"
                  type="submit"
                  disabled={creating}
                  className="flex-1 px-4 py-2.5 rounded-lg text-sm font-semibold cursor-pointer"
                  style={{ background: "var(--gradient-1)", color: "white", opacity: creating ? 0.7 : 1 }}
                >
                  {creating ? "Creating..." : "Create Project"}
                </button>
              </div>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
