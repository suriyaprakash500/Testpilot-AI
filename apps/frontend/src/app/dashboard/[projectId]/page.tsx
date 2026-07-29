"use client";

import { use, useState, useEffect } from "react";
import { 
  Play, Clock, CheckCircle2, XCircle, AlertTriangle, ChevronRight, ArrowLeft, Trash2,
  Bot, GitBranch, FolderGit, Tv, Terminal, Sparkles, RefreshCw, Cpu, Layers, Code, PlaySquare, ShieldAlert
} from "lucide-react";
import { api, type Project, type TestRun, type PipelinesData } from "../../../lib/api";

const STATUS_STYLES: Record<string, { icon: typeof CheckCircle2; color: string; label: string }> = {
  completed: { icon: CheckCircle2, color: "var(--success)", label: "Completed" },
  failed: { icon: XCircle, color: "var(--error)", label: "Failed" },
  executing: { icon: Play, color: "var(--accent)", label: "Running" },
  pending: { icon: Clock, color: "var(--warning)", label: "Pending" },
};

// ============================================================
// Premium Feature Mockup Renderers
// ============================================================

function AgentsMockup() {
  const [activeStates, setActiveStates] = useState({
    repoAnalysis: false,
    testPlanning: false,
    playwrightGen: false,
    browserExecution: false,
    failureAnalysis: false,
    githubIntegration: false,
  });

  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    const fetchStates = async () => {
      try {
        const data = await api.getActiveAgents();
        if (active) {
          setActiveStates(data);
          setLoading(false);
        }
      } catch (err) {
        console.error("Failed to load active agents:", err);
      }
    };

    fetchStates();
    const interval = setInterval(fetchStates, 3000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  const agentsList = [
    {
      id: "agent-1",
      name: "DOM Mapper Agent",
      type: "repo-analysis",
      status: (activeStates.repoAnalysis || activeStates.testPlanning || activeStates.browserExecution) ? "active" : "idle",
      icon: Cpu,
      desc: "Scans and builds interactive locator maps of target UI components.",
      task: (activeStates.repoAnalysis || activeStates.testPlanning || activeStates.browserExecution)
        ? "Mapping codebase structure & active DOM nodes..."
        : "Idle - waiting for runs",
      tokens: (activeStates.repoAnalysis || activeStates.testPlanning || activeStates.browserExecution) ? "142k" : "0",
      load: (activeStates.repoAnalysis || activeStates.testPlanning || activeStates.browserExecution) ? "78%" : "0%"
    },
    {
      id: "agent-2",
      name: "Healer Agent",
      type: "failure-analysis",
      status: activeStates.failureAnalysis ? "active" : "idle",
      icon: Sparkles,
      desc: "Listens to execution failures and generates healing code patches in real-time.",
      task: activeStates.failureAnalysis ? "Diagnosing locator failures & self-healing..." : "Idle - waiting for failures",
      tokens: activeStates.failureAnalysis ? "420k" : "0",
      load: activeStates.failureAnalysis ? "88%" : "0%"
    },
    {
      id: "agent-3",
      name: "Playwright Gen Agent",
      type: "playwright-gen",
      status: activeStates.playwrightGen ? "active" : "idle",
      icon: Code,
      desc: "Converts natural language user instructions into robust Playwright assertions.",
      task: activeStates.playwrightGen ? "Writing executable Playwright tests..." : "Idle - waiting for plan",
      tokens: activeStates.playwrightGen ? "98k" : "0",
      load: activeStates.playwrightGen ? "45%" : "0%"
    },
    {
      id: "agent-4",
      name: "PR Review Agent",
      type: "github-integration",
      status: activeStates.githubIntegration ? "active" : "idle",
      icon: GitBranch,
      desc: "Wraps healed code into GitHub PRs and posts summaries to Slack/GitHub.",
      task: activeStates.githubIntegration ? "Syncing test code and creating pull requests..." : "Idle - waiting for codebase updates",
      tokens: activeStates.githubIntegration ? "54k" : "0",
      load: activeStates.githubIntegration ? "32%" : "0%"
    }
  ];

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center p-12">
        <div className="animate-spin rounded-full h-6 w-6 border-t-2 border-b-2 border-indigo-500 mb-2" />
        <p className="text-xs" style={{ color: "var(--text-secondary)" }}>Connecting to agent orchestrator...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="border-b pb-4" style={{ borderColor: "var(--border)" }}>
        <div className="flex items-center gap-3">
          <Bot size={22} style={{ color: "var(--accent-purple)" }} />
          <h1 className="text-xl font-bold tracking-tight" style={{ color: "var(--text-primary)" }}>
            Autonomous Agent Orchestrator
          </h1>
          <span className="px-2 py-0.5 rounded-full text-[10px] font-mono border" style={{ 
            background: Object.values(activeStates).some(Boolean) ? "rgba(16,185,129,0.06)" : "rgba(139,92,246,0.06)", 
            color: Object.values(activeStates).some(Boolean) ? "var(--success)" : "var(--accent-purple)", 
            borderColor: Object.values(activeStates).some(Boolean) ? "rgba(16,185,129,0.15)" : "rgba(139,92,246,0.15)" 
          }}>
            {Object.values(activeStates).some(Boolean) ? "CLUSTER ACTIVE" : "CLUSTER STANDBY"}
          </span>
        </div>
        <p className="text-[12px] mt-1 ml-9" style={{ color: "var(--text-muted)" }}>
          Currently orchestrating 4 specialized agent pipelines based on test run executions
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {agentsList.map((agent) => {
          const AgentIcon = agent.icon;
          const isActive = agent.status === "active";
          return (
            <div key={agent.id} className="glass p-5 flex flex-col justify-between space-y-4">
              <div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="p-2 rounded-lg" style={{ background: isActive ? "rgba(139,92,246,0.1)" : "var(--bg-secondary)", border: "1px solid var(--border)" }}>
                      <AgentIcon size={18} style={{ color: isActive ? "var(--accent-purple)" : "var(--text-muted)" }} />
                    </div>
                    <div>
                      <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{agent.name}</h3>
                      <span className="text-[10px] font-mono" style={{ color: "var(--text-muted)" }}>{agent.type.toUpperCase()}</span>
                    </div>
                  </div>
                  <span className="flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold border" style={{
                    background: isActive ? "rgba(16,185,129,0.06)" : "var(--bg-secondary)",
                    borderColor: isActive ? "var(--success)" : "var(--border)",
                    color: isActive ? "var(--success)" : "var(--text-muted)"
                  }}>
                    {isActive && <span className="w-1.5 h-1.5 rounded-full pulse-ring-active" style={{ background: "var(--success)" }} />}
                    {agent.status.toUpperCase()}
                  </span>
                </div>
                <p className="text-[12px] mt-3 leading-relaxed" style={{ color: "var(--text-secondary)" }}>
                  {agent.desc}
                </p>
              </div>

              <div className="pt-3 border-t flex flex-col gap-2" style={{ borderColor: "var(--border)" }}>
                <div className="flex items-center justify-between text-[11px] font-mono">
                  <span style={{ color: "var(--text-muted)" }}>Current Task:</span>
                  <span style={{ color: isActive ? "var(--text-primary)" : "var(--text-muted)" }} className={isActive ? "truncate max-w-[200px]" : ""}>
                    {agent.task}
                  </span>
                </div>
                <div className="flex items-center justify-between text-[11px] font-mono">
                  <span style={{ color: "var(--text-muted)" }}>Token Usage:</span>
                  <span style={{ color: "var(--text-secondary)" }}>{agent.tokens} / hr</span>
                </div>
                <div className="flex items-center justify-between text-[11px] font-mono">
                  <span style={{ color: "var(--text-muted)" }}>Load:</span>
                  <span style={{ color: "var(--text-secondary)" }}>{agent.load}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function PipelinesMockup() {
  const [data, setData] = useState<PipelinesData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    const fetchPipelines = async () => {
      try {
        const res = await api.getPipelines();
        if (active) {
          setData(res);
          setLoading(false);
        }
      } catch (err) {
        console.error("Failed to load pipelines data:", err);
      }
    };

    fetchPipelines();
    const interval = setInterval(fetchPipelines, 5000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  const formatDuration = (start: string, end: string | null) => {
    if (!start) return "N/A";
    const startTime = new Date(start).getTime();
    const endTime = end ? new Date(end).getTime() : Date.now();
    const diff = Math.max(0, endTime - startTime);
    const seconds = Math.floor(diff / 1000);
    if (seconds < 60) return `${seconds}s`;
    const minutes = Math.floor(seconds / 60);
    return `${minutes}m ${seconds % 60}s`;
  };

  const getStatusLabel = (status: string | undefined) => {
    if (!status) return "INACTIVE";
    if (status === "completed") return "PASSED";
    if (status === "failed") return "FAILED";
    if (status === "cancelled") return "CANCELLED";
    return "EXECUTING";
  };

  const formatRelativeTime = (dateStr: string | undefined) => {
    if (!dateStr) return "Never run";
    const diffMs = Date.now() - new Date(dateStr).getTime();
    const diffSec = Math.floor(diffMs / 1000);
    if (diffSec < 60) return "just now";
    const diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHrs = Math.floor(diffMin / 60);
    if (diffHrs < 24) return `${diffHrs}h ago`;
    const diffDays = Math.floor(diffHrs / 24);
    return `${diffDays}d ago`;
  };

  const pipelinesList = [
    {
      name: "Staging Sanity Pipeline",
      trigger: "Commit Push (main / manual)",
      run: data?.manual,
    },
    {
      name: "PR Verification Pipeline",
      trigger: "PR Sync/Open (webhook)",
      run: data?.webhook,
    },
    {
      name: "Nightly Production Smoke Test",
      trigger: "Schedule (00:00 UTC)",
      run: data?.schedule,
    }
  ];

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center p-12">
        <div className="animate-spin rounded-full h-6 w-6 border-t-2 border-b-2 border-indigo-500 mb-2" />
        <p className="text-xs" style={{ color: "var(--text-secondary)" }}>Connecting to pipeline orchestrator...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="border-b pb-4" style={{ borderColor: "var(--border)" }}>
        <div className="flex items-center gap-3">
          <GitBranch size={22} style={{ color: "var(--accent-indigo)" }} />
          <h1 className="text-xl font-bold tracking-tight" style={{ color: "var(--text-primary)" }}>
            Automated E2E Pipelines
          </h1>
          <span className="px-2 py-0.5 rounded-full text-[10px] font-mono border" style={{ background: "rgba(99,102,241,0.06)", color: "var(--accent-indigo)", borderColor: "rgba(99,102,241,0.15)" }}>
            3 CONFIGURED
          </span>
        </div>
        <p className="text-[12px] mt-1 ml-9" style={{ color: "var(--text-muted)" }}>
          Manage continuous integration workflows and automated schedules
        </p>
      </div>

      <div className="space-y-3">
        {pipelinesList.map((pipe, index) => {
          const run = pipe.run;
          const statusLabel = getStatusLabel(run?.status);
          const isRunPassed = statusLabel === "PASSED" || statusLabel === "INACTIVE";
          const isExecuting = statusLabel === "EXECUTING";

          return (
            <div key={index} className="glass p-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div className="flex items-start gap-3">
                <div className="p-2 rounded-lg mt-0.5" style={{ 
                  background: isExecuting 
                    ? "rgba(139,92,246,0.06)" 
                    : isRunPassed 
                      ? "rgba(16,185,129,0.06)" 
                      : "rgba(239,68,68,0.06)", 
                  border: "1px solid var(--border)" 
                }}>
                  {isExecuting ? (
                    <div className="animate-spin rounded-full h-4 w-4 border-t-2 border-b-2 border-indigo-500" />
                  ) : isRunPassed ? (
                    <CheckCircle2 size={16} style={{ color: "var(--success)" }} />
                  ) : (
                    <XCircle size={16} style={{ color: "var(--error)" }} />
                  )}
                </div>
                <div>
                  <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{pipe.name}</h3>
                  <div className="flex items-center gap-3 mt-1 text-[11px]" style={{ color: "var(--text-muted)" }}>
                    <span>Trigger: {pipe.trigger}</span>
                    <span>•</span>
                    <span>Last Run: {formatRelativeTime(run?.createdAt)}</span>
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-between md:justify-end gap-6 text-right font-mono text-[11px]">
                <div>
                  <span style={{ color: "var(--text-muted)" }}>Specs Executed:</span>
                  <span className="ml-2" style={{ color: "var(--text-secondary)" }}>{run?.casesCount ?? 0}</span>
                </div>
                <div>
                  <span style={{ color: "var(--text-muted)" }}>Avg Latency:</span>
                  <span className="ml-2" style={{ color: "var(--text-secondary)" }}>{run ? formatDuration(run.createdAt, run.completedAt) : "0s"}</span>
                </div>
                <span className="px-2 py-0.5 rounded border text-[10px] font-semibold" style={{
                  borderColor: isExecuting 
                    ? "var(--accent-purple)" 
                    : isRunPassed 
                      ? "var(--success)" 
                      : "var(--error)",
                  color: isExecuting 
                    ? "var(--accent-purple)" 
                    : isRunPassed 
                      ? "var(--success)" 
                      : "var(--error)",
                  background: isExecuting 
                    ? "rgba(139,92,246,0.06)" 
                    : isRunPassed 
                      ? "rgba(16,185,129,0.06)" 
                      : "rgba(239,68,68,0.06)"
                }}>
                  {statusLabel}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      <div className="glass p-5">
        <h3 className="text-sm font-semibold mb-4" style={{ color: "var(--text-primary)" }}>Pipeline Blueprint (Visual Flow)</h3>
        <div className="flex flex-col md:flex-row items-center justify-between gap-4 p-4 rounded-lg bg-[#020408] border border-violet-500/10 overflow-x-auto">
          <div className="flex items-center gap-2 px-3 py-1.5 rounded border border-violet-500/20 bg-violet-500/5 text-xs font-mono">
            <Cpu size={12} className="text-violet-400" />
            Repo Analysis
          </div>
          <ChevronRight size={14} className="text-violet-500 hidden md:block" />
          <div className="flex items-center gap-2 px-3 py-1.5 rounded border border-violet-500/20 bg-violet-500/5 text-xs font-mono">
            <Layers size={12} className="text-violet-400" />
            Test Planning
          </div>
          <ChevronRight size={14} className="text-indigo-500 hidden md:block" />
          <div className="flex items-center gap-2 px-3 py-1.5 rounded border border-indigo-500/20 bg-indigo-500/5 text-xs font-mono">
            <Code size={12} className="text-indigo-400" />
            Playwright Gen
          </div>
          <ChevronRight size={14} className="text-emerald-500 hidden md:block" />
          <div className="flex items-center gap-2 px-3 py-1.5 rounded border border-emerald-500/20 bg-emerald-500/5 text-xs font-mono">
            <PlaySquare size={12} className="text-emerald-400" />
            Browser Execute
          </div>
          <ChevronRight size={14} className="text-rose-500 hidden md:block" />
          <div className="flex items-center gap-2 px-3 py-1.5 rounded border border-rose-500/20 bg-rose-500/5 text-xs font-mono">
            <ShieldAlert size={12} className="text-rose-400" />
            Failure Analysis & Heal
          </div>
        </div>
      </div>
    </div>
  );
}

function ReposMockup() {
  const [repos, setRepos] = useState<Array<{
    projectId: string;
    repoUrl: string;
    repoName: string;
    projectName: string;
    framework: string;
    language: string;
    analyzedAt: string | null;
  }>>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    const fetchRepos = async () => {
      try {
        const res = await api.getRepositories();
        if (active) {
          setRepos(res);
          setLoading(false);
        }
      } catch (err) {
        console.error("Failed to load repositories data:", err);
      }
    };

    fetchRepos();
  }, []);

  const formatRelativeTime = (dateStr: string | null) => {
    if (!dateStr) return "Never run";
    const diffMs = Date.now() - new Date(dateStr).getTime();
    const diffSec = Math.floor(diffMs / 1000);
    if (diffSec < 60) return "just now";
    const diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHrs = Math.floor(diffMin / 60);
    if (diffHrs < 24) return `${diffHrs}h ago`;
    const diffDays = Math.floor(diffHrs / 24);
    return `${diffDays}d ago`;
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center p-12">
        <div className="animate-spin rounded-full h-6 w-6 border-t-2 border-b-2 border-indigo-500 mb-2" />
        <p className="text-xs" style={{ color: "var(--text-secondary)" }}>Connecting to codebase scanning registry...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="border-b pb-4" style={{ borderColor: "var(--border)" }}>
        <div className="flex items-center gap-3">
          <FolderGit size={22} style={{ color: "var(--accent-purple)" }} />
          <h1 className="text-xl font-bold tracking-tight" style={{ color: "var(--text-primary)" }}>
            Connected Codebases
          </h1>
          <span className="px-2 py-0.5 rounded-full text-[10px] font-mono border" style={{ background: "rgba(139,92,246,0.06)", color: "var(--accent-purple)", borderColor: "rgba(139,92,246,0.15)" }}>
            {repos.length} {repos.length === 1 ? "REPO" : "REPOS"}
          </span>
        </div>
        <p className="text-[12px] mt-1 ml-9" style={{ color: "var(--text-muted)" }}>
          Identify test paths, components, and manage automated schema extraction
        </p>
      </div>

      <div className="flex items-center gap-3">
        <button className="px-3 py-1.5 rounded-lg text-xs font-semibold shadow-[0_0_12px_rgba(139,92,246,0.15)] opacity-50 cursor-not-allowed" disabled style={{ background: "var(--gradient-1)", color: "white" }}>
          Connect Repository
        </button>
        <button 
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors hover:border-zinc-500 cursor-pointer" 
          style={{ background: "var(--bg-secondary)", borderColor: "var(--border)", color: "var(--text-secondary)" }}
          onClick={() => {
            alert("Re-triggering repository scans for all workspaces...");
          }}
        >
          <RefreshCw size={12} />
          Re-trigger Codebase Scans
        </button>
      </div>

      {repos.length === 0 ? (
        <div className="glass p-12 text-center flex flex-col items-center justify-center gap-4">
          <FolderGit size={40} style={{ color: "var(--text-muted)" }} />
          <div>
            <h3 className="text-sm font-semibold mb-1" style={{ color: "var(--text-primary)" }}>No connected repositories</h3>
            <p className="text-xs max-w-xs mx-auto" style={{ color: "var(--text-secondary)" }}>
              Add a project in the main workspace to scan its git codebase structure.
            </p>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {repos.map((repo, i) => (
            <div key={i} className="glass p-5 flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2.5">
                  <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{repo.repoName}</h3>
                  <span className="px-1.5 py-0.5 rounded bg-zinc-900 border border-violet-500/20 text-[9px] font-mono text-violet-400">
                    main
                  </span>
                </div>
                <p className="text-xs" style={{ color: "var(--text-muted)" }}>
                  Framework discovered: <span className="font-mono text-zinc-300">{repo.framework}</span> • Last codebase audit: {formatRelativeTime(repo.analyzedAt)}
                </p>
              </div>

              <div className="flex items-center gap-3">
                <span className="flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold border" style={{
                  background: "rgba(16,185,129,0.06)",
                  borderColor: "var(--success)",
                  color: "var(--success)"
                }}>
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                  DISCOVERED & SYNCED
                </span>
                <a href={`/dashboard/${repo.projectId}`} className="text-xs text-indigo-400 font-semibold hover:underline">
                  Configure Settings
                </a>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function SessionsMockup() {
  const [session, setSession] = useState<{
    runId: string;
    status: string;
    projectName: string;
    websiteUrl: string;
    testCaseName: string;
  } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    const fetchSession = async () => {
      try {
        const res = await api.getActiveSession();
        if (active) {
          setSession(res);
          setLoading(false);
        }
      } catch (err) {
        console.error("Failed to load active session:", err);
      }
    };

    fetchSession();
    const interval = setInterval(fetchSession, 3000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center p-12">
        <div className="animate-spin rounded-full h-6 w-6 border-t-2 border-b-2 border-indigo-500 mb-2" />
        <p className="text-xs" style={{ color: "var(--text-secondary)" }}>Connecting to live canvas...</p>
      </div>
    );
  }

  const isSessionActive = session !== null;

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="border-b pb-4" style={{ borderColor: "var(--border)" }}>
        <div className="flex items-center gap-3">
          <Tv size={22} style={{ color: "var(--accent-purple)" }} />
          <h1 className="text-xl font-bold tracking-tight" style={{ color: "var(--text-primary)" }}>
            Live Execution Canvas
          </h1>
          <span className="px-2 py-0.5 rounded-full text-[10px] font-mono border" style={{ 
            background: isSessionActive ? "rgba(16,185,129,0.06)" : "rgba(139,92,246,0.06)", 
            color: isSessionActive ? "var(--success)" : "var(--text-muted)", 
            borderColor: isSessionActive ? "rgba(16,185,129,0.15)" : "var(--border)" 
          }}>
            {isSessionActive ? "RUNNER ACTIVE" : "STANDBY"}
          </span>
        </div>
        <p className="text-[12px] mt-1 ml-9" style={{ color: "var(--text-muted)" }}>
          {isSessionActive 
            ? `Attached to project workspace: ${session.projectName}`
            : "Watch autonomous AI agents interact and heal your application live"}
        </p>
      </div>

      <div className="glass p-1 overflow-hidden relative" style={{ height: "420px" }}>
        <div className="h-8 flex items-center justify-between px-3 border-b bg-slate-950/60" style={{ borderColor: "var(--border)" }}>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-rose-500/80" />
            <span className="w-2.5 h-2.5 rounded-full bg-amber-500/80" />
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500/80" />
          </div>
          <div className="px-3 py-0.5 rounded bg-zinc-900 border border-violet-500/10 text-[10px] font-mono w-96 text-center text-zinc-400 truncate">
            {isSessionActive ? session.websiteUrl : "about:blank"}
          </div>
          <span className="text-[10px] font-mono text-zinc-500">{isSessionActive ? "Playwright Webkit" : "Browser Off"}</span>
        </div>

        <div className="absolute inset-0 top-8 flex flex-col items-center justify-center bg-slate-950/90 select-none">
          <div className="flex flex-col items-center gap-3">
            {isSessionActive ? (
              <>
                <div className="w-10 h-10 rounded-full flex items-center justify-center border border-emerald-500/30 bg-emerald-500/10 animate-pulse">
                  <Tv size={18} className="text-emerald-400" />
                </div>
                <p className="text-xs font-mono tracking-widest text-emerald-400 animate-pulse">
                  CONNECTING ACTIVE VNC STREAM...
                </p>
                <p className="text-[10px] text-zinc-300 font-mono">
                  {session.projectName} : Run #{session.runId.slice(0, 8)}
                </p>
                <p className="text-[10px] text-zinc-500 font-mono italic max-w-md text-center truncate">
                  Executing: {session.testCaseName}
                </p>
              </>
            ) : (
              <>
                <div className="w-10 h-10 rounded-full flex items-center justify-center border border-zinc-500/20 bg-zinc-500/5">
                  <Tv size={18} className="text-zinc-500" />
                </div>
                <p className="text-xs font-mono tracking-widest text-zinc-500">
                  SYSTEM STANDBY
                </p>
                <p className="text-[10px] text-zinc-600 max-w-xs text-center">
                  No active browser execution. Trigger a test run from any project workspace to see live interactions here.
                </p>
              </>
            )}
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between p-4 glass">
        <div className="flex items-center gap-3">
          <span className="w-2 h-2 rounded-full pulse-ring-active" style={{ background: isSessionActive ? "var(--success)" : "var(--text-muted)" }} />
          <span className="text-xs font-mono text-zinc-300">
            {isSessionActive 
              ? "VNC Port: 5901 (AES Encrypted WebRTC)" 
              : "VNC Connection: Offline"}
          </span>
        </div>
        <div className="flex gap-2">
          <button className={`px-3 py-1 rounded border text-xs font-semibold ${isSessionActive ? "bg-indigo-600 border-indigo-500 text-white cursor-pointer hover:bg-indigo-500" : "bg-zinc-900 border-zinc-800 text-zinc-500 cursor-not-allowed"}`} disabled={!isSessionActive}>
            Take Remote Control
          </button>
          <button className={`px-3 py-1 rounded border text-xs font-semibold ${isSessionActive ? "bg-zinc-900 border-zinc-800 text-zinc-200 cursor-pointer hover:bg-zinc-850" : "bg-zinc-900 border-zinc-800 text-zinc-500 cursor-not-allowed"}`} disabled={!isSessionActive}>
            Inspect DOM Node
          </button>
        </div>
      </div>
    </div>
  );
}

function DebuggerMockup() {
  return (
    <div className="space-y-6 animate-fade-in">
      <div className="border-b pb-4" style={{ borderColor: "var(--border)" }}>
        <div className="flex items-center gap-3">
          <Terminal size={22} style={{ color: "var(--accent-purple)" }} />
          <h1 className="text-xl font-bold tracking-tight" style={{ color: "var(--text-primary)" }}>
            AI Locator & DOM Debugger
          </h1>
          <span className="px-2 py-0.5 rounded-full text-[10px] font-mono border" style={{ background: "rgba(139,92,246,0.06)", color: "var(--accent-purple)", borderColor: "rgba(139,92,246,0.15)" }}>
            REASONING ENGINE ONLINE
          </span>
        </div>
        <p className="text-[12px] mt-1 ml-9" style={{ color: "var(--text-muted)" }}>
          Inspect selectors, query active DOM layers, and preview AI self-healing corrections
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="glass p-5 lg:col-span-1 space-y-4">
          <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Selector Diagnostics</h3>
          <div className="space-y-3">
            <div>
              <label className="text-[10px] uppercase font-bold tracking-wider text-zinc-500 font-mono block mb-1">Target Locator (Broken or Old)</label>
              <input
                type="text"
                defaultValue="button.btn-primary[type='submit']"
                className="w-full px-3 py-1.5 rounded bg-zinc-950 border border-zinc-800 text-xs font-mono focus:outline-none focus:border-indigo-500 text-zinc-300"
              />
            </div>
            <div>
              <label className="text-[10px] uppercase font-bold tracking-wider text-zinc-500 font-mono block mb-1">Target URL</label>
              <input
                type="text"
                defaultValue="https://demo.testpilot.ai/dashboard"
                className="w-full px-3 py-1.5 rounded bg-zinc-950 border border-zinc-800 text-xs font-mono focus:outline-none focus:border-indigo-500 text-zinc-300"
              />
            </div>
            <button
              className="w-full py-2 rounded text-xs font-semibold shadow-[0_0_12px_rgba(139,92,246,0.15)] flex items-center justify-center gap-2"
              style={{ background: "var(--gradient-1)", color: "white" }}
              onClick={() => alert("Diagnosing locator with current DOM snapshots...")}
            >
              <Sparkles size={12} />
              Analyze & Heal Locator
            </button>
          </div>
        </div>

        <div className="glass p-5 lg:col-span-2 space-y-4">
          <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Heal Recommendation</h3>
          
          <div className="p-4 rounded-lg bg-emerald-500/5 border border-emerald-500/20 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-emerald-400 flex items-center gap-1.5">
                <CheckCircle2 size={14} />
                HEAL SUCCESSFUL
              </span>
              <span className="text-[10px] font-mono text-emerald-500">Confidence: 98.4%</span>
            </div>
            <p className="text-xs text-zinc-300 leading-relaxed">
              The selector `button.btn-primary` failed because the class names were changed during Tailwind migration. 
              TestPilot mapped the element using text density & accessibility tree.
            </p>
            
            <div className="grid grid-cols-2 gap-4 pt-2 font-mono text-[11px]">
              <div>
                <span className="text-zinc-500 block mb-0.5">Original:</span>
                <code className="text-rose-400 block px-2 py-1 rounded bg-zinc-950 truncate border border-rose-500/10">button.btn-primary[type='submit']</code>
              </div>
              <div>
                <span className="text-zinc-500 block mb-0.5">Healed (Playwright recommended):</span>
                <code className="text-emerald-400 block px-2 py-1 rounded bg-zinc-950 truncate border border-emerald-500/10">button:has-text("Invite Member")</code>
              </div>
            </div>
          </div>

          <div className="space-y-2">
            <span className="text-[10px] uppercase font-bold tracking-wider text-zinc-500 font-mono block">Match Properties</span>
            <div className="grid grid-cols-3 gap-2 text-center text-xs font-mono">
              <div className="p-2 rounded bg-zinc-950 border border-zinc-800">
                <span className="text-zinc-500 block text-[9px]">TAG NAME</span>
                <span className="text-zinc-300 font-semibold">BUTTON</span>
              </div>
              <div className="p-2 rounded bg-zinc-950 border border-zinc-800">
                <span className="text-zinc-500 block text-[9px]">INTERACTIVE</span>
                <span className="text-emerald-400 font-semibold">TRUE</span>
              </div>
              <div className="p-2 rounded bg-zinc-950 border border-zinc-800">
                <span className="text-zinc-500 block text-[9px]">A11Y ROLE</span>
                <span className="text-indigo-400 font-semibold">button</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="ide-terminal p-4 h-48 overflow-y-auto space-y-1">
        <div className="text-violet-400 font-semibold text-xs mb-1">=== DIAGNOSTICS LOG ===</div>
        <div className="text-zinc-500 font-mono text-[11px]">[12:44:02.102] Querying DOM snapshots for demo.testpilot.ai/dashboard</div>
        <div className="text-zinc-500 font-mono text-[11px]">[12:44:02.156] Locating selector 'button.btn-primary' ... NOT FOUND (0 elements matched)</div>
        <div className="text-zinc-500 font-mono text-[11px]">[12:44:02.214] Triggering fallback fuzzy-matching agent ...</div>
        <div className="text-indigo-400 font-mono text-[11px]">[12:44:02.408] Matching against accessibility tree coordinates</div>
        <div className="text-indigo-400 font-mono text-[11px]">[12:44:02.455] Accessibility match found! Coordinates: (x: 1042, y: 154)</div>
        <div className="text-emerald-400 font-mono text-[11px]">[12:44:02.498] Extracted target text: "Invite Member"</div>
        <div className="text-emerald-400 font-mono text-[11px]">[12:44:02.502] Recommended locator: button:has-text("Invite Member") <span className="terminal-cursor" /></div>
      </div>
    </div>
  );
}

// ============================================================
// Main Component
// ============================================================

export default function ProjectDetailPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = use(params);
  
  const reservedPaths = ["agents", "pipelines", "repos", "sessions", "debugger"];
  const isReserved = reservedPaths.includes(projectId);
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

  const loadData = async () => {
    if (isReserved || !isValidProjectId) {
      setLoading(false);
      return;
    }
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
    if (isReserved) {
      setLoading(false);
      return;
    }
    if (!isValidProjectId) {
      setError("Invalid Project ID format");
      setLoading(false);
      return;
    }
    loadData();
    // Poll for status updates every 5 seconds if there are running or pending tests
    const timer = setInterval(() => {
      if (runs.some(r => r.status === "pending" || r.status === "executing")) {
        api.getRuns(projectId).then(setRuns).catch(() => {});
      }
    }, 5000);

    return () => clearInterval(timer);
  }, [projectId, runs, isReserved, isValidProjectId]);

  const handleRunTests = async () => {
    if (isReserved || !isValidProjectId) return;
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
          <p style={{ color: "var(--text-secondary)" }}>Loading details...</p>
        </div>
      </div>
    );
  }

  if (isReserved) {
    return (
      <div className="p-8 max-w-5xl mx-auto space-y-6">
        {projectId === "agents" && <AgentsMockup />}
        {projectId === "pipelines" && <PipelinesMockup />}
        {projectId === "repos" && <ReposMockup />}
        {projectId === "sessions" && <SessionsMockup />}
        {projectId === "debugger" && <DebuggerMockup />}
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
    <div className="p-8 max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div className="border-b pb-4" style={{ borderColor: "var(--border)" }}>
        <div className="flex items-center gap-3">
          <a
            href="/dashboard"
            className="p-1 rounded-md transition-colors"
            style={{ color: "var(--text-muted)" }}
            onMouseEnter={(e) => (e.currentTarget.style.color = "var(--text-primary)")}
            onMouseLeave={(e) => (e.currentTarget.style.color = "var(--text-muted)")}
          >
            <ArrowLeft size={16} />
          </a>
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
              onFocus={(e) => (e.target.style.borderColor = "var(--accent)")}
              onBlur={(e) => (e.target.style.borderColor = "var(--border)")}
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
              onFocus={(e) => (e.target.style.borderColor = "var(--accent)")}
              onBlur={(e) => (e.target.style.borderColor = "var(--border)")}
            />
          </div>
          <button
            disabled={savingCreds || (!credEmail && !credPassword)}
            onClick={async () => {
              setSavingCreds(true);
              setCredsSaved(false);
              try {
                const updates: any = {};
                if (credEmail) updates.testEmail = credEmail;
                if (credPassword) updates.testPassword = credPassword;
                await api.updateProject(projectId, updates);
                setCredsSaved(true);
                setCredEmail("");
                setCredPassword("");
                setTimeout(() => setCredsSaved(false), 3000);
              } catch (err: any) {
                alert(err.message || "Failed to save credentials");
              } finally {
                setSavingCreds(false);
              }
            }}
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
