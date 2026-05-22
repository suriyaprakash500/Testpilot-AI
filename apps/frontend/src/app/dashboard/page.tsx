"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Plus, GitBranch, Clock, ChevronRight, AlertTriangle, ExternalLink } from "lucide-react";
import { api, type Project } from "../../lib/api";

export default function DashboardPage() {
  const router = useRouter();
  const [projectsList, setProjectsList] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Modal states
  const [showNewProject, setShowNewProject] = useState(false);
  const [newRepoUrl, setNewRepoUrl] = useState("");
  const [newWebsiteUrl, setNewWebsiteUrl] = useState("");
  const [creating, setCreating] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);

  useEffect(() => {
    const token = localStorage.getItem("token");
    if (!token) {
      router.push("/");
      return;
    }

    async function loadProjects() {
      try {
        const data = await api.getProjects();
        setProjectsList(data);
      } catch (err: any) {
        setError(err.message || "Failed to load projects");
      } finally {
        setLoading(false);
      }
    }

    loadProjects();
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
      });
      setProjectsList((prev) => [...prev, newProj]);
      setShowNewProject(false);
      setNewRepoUrl("");
      setNewWebsiteUrl("");
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
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: "var(--text-primary)" }}>
            Projects
          </h1>
          <p className="text-sm mt-1" style={{ color: "var(--text-secondary)" }}>
            Manage your connected repositories and test runs
          </p>
        </div>
        <button
          id="new-project-btn"
          className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 cursor-pointer"
          style={{ background: "var(--gradient-1)", color: "white" }}
          onClick={() => setShowNewProject(true)}
        >
          <Plus size={16} />
          New Project
        </button>
      </div>

      {error && (
        <div className="p-4 mb-6 rounded-lg flex items-center gap-3" style={{ background: "rgba(239,68,68,0.1)", border: "1px solid var(--error)" }}>
          <AlertTriangle size={18} style={{ color: "var(--error)" }} />
          <span className="text-sm" style={{ color: "var(--error)" }}>{error}</span>
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        {[
          { label: "Connected Projects", value: projectsList.length.toString(), color: "var(--text-primary)" },
          { label: "Status Monitor", value: "All Active", color: "var(--success)" },
          { label: "Platform Version", value: "v1.0.0", color: "var(--accent)" },
          { label: "Environment", value: "Dev / Sandbox", color: "var(--warning)" },
        ].map((stat) => (
          <div key={stat.label} className="glass p-4">
            <div className="text-2xl font-bold" style={{ color: stat.color }}>
              {stat.value}
            </div>
            <div className="text-xs mt-1" style={{ color: "var(--text-muted)" }}>
              {stat.label}
            </div>
          </div>
        ))}
      </div>

      {/* Project Cards */}
      {projectsList.length === 0 ? (
        <div className="glass p-12 text-center flex flex-col items-center justify-center gap-4">
          <div className="text-4xl">📦</div>
          <div>
            <h3 className="text-lg font-semibold mb-1" style={{ color: "var(--text-primary)" }}>No projects connected</h3>
            <p className="text-sm max-w-sm mx-auto" style={{ color: "var(--text-secondary)" }}>
              Connect your first GitHub repository and website URL to start running automated AI tests.
            </p>
          </div>
          <button
            className="px-4 py-2 rounded-lg text-sm font-semibold transition-all duration-200"
            style={{ background: "var(--gradient-1)", color: "white" }}
            onClick={() => setShowNewProject(true)}
          >
            Connect Project
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          {projectsList.map((project, i) => (
            <a
              key={project.id}
              href={`/dashboard/${project.id}`}
              className="glass flex items-center justify-between p-5 transition-all duration-200 animate-slide-up block"
              style={{ animationDelay: `${i * 0.05}s` }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = "var(--border-hover)";
                e.currentTarget.style.transform = "translateX(2px)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = "var(--border)";
                e.currentTarget.style.transform = "translateX(0)";
              }}
            >
              <div className="flex items-center gap-4">
                <div
                  className="w-10 h-10 rounded-lg flex items-center justify-center text-lg"
                  style={{ background: "var(--accent-glow)" }}
                >
                  🚀
                </div>
                <div>
                  <div className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                    {project.name}
                  </div>
                  <div className="flex items-center gap-3 mt-1">
                    <span className="flex items-center gap-1 text-xs" style={{ color: "var(--text-muted)" }}>
                      <GitBranch size={12} />
                      {project.repoUrl.split("/").slice(-2).join("/")}
                    </span>
                    <span className="flex items-center gap-1 text-xs" style={{ color: "var(--text-muted)" }}>
                      <ExternalLink size={12} />
                      {project.websiteUrl}
                    </span>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-6">
                <ChevronRight size={16} style={{ color: "var(--text-muted)" }} />
              </div>
            </a>
          ))}
        </div>
      )}

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
