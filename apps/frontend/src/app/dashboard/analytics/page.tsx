"use client";

import { useState, useEffect } from "react";
import { TrendingUp, CheckCircle, AlertCircle, RefreshCw, BarChart2, ShieldAlert } from "lucide-react";
import { api, type AnalyticsData } from "../../../lib/api";

export default function AnalyticsPage() {
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchAnalytics = async () => {
    try {
      setLoading(true);
      const res = await api.getAnalytics();
      setData(res);
      setError(null);
    } catch (err: any) {
      setError(err.message || "Failed to load analytics");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAnalytics();
  }, []);

  const formatTimeSaved = (ms: number): string => {
    if (!ms || ms <= 0) return "0h";
    const hours = ms / 3600000;
    if (hours >= 0.1) {
      return `${hours.toFixed(1)}h`;
    }
    const minutes = ms / 60000;
    if (minutes >= 0.1) {
      return `${minutes.toFixed(1)}m`;
    }
    return `${(ms / 1000).toFixed(0)}s`;
  };

  if (loading) {
    return (
      <div className="p-8 min-h-screen flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-indigo-500" />
          <p style={{ color: "var(--text-secondary)" }}>Loading workspace analytics...</p>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="p-8">
        <div className="mb-8 flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold" style={{ color: "var(--text-primary)" }}>Analytics</h1>
            <p className="text-sm mt-1" style={{ color: "var(--text-secondary)" }}>
              Workspace metrics and execution statistics.
            </p>
          </div>
          <button
            onClick={fetchAnalytics}
            className="flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium cursor-pointer transition-colors hover:border-zinc-500"
            style={{ border: "1px solid var(--border)", color: "var(--text-secondary)", background: "var(--bg-secondary)" }}
          >
            <RefreshCw size={14} /> Retry
          </button>
        </div>
        <div className="p-4 rounded-lg flex items-center gap-3" style={{ background: "rgba(239,68,68,0.1)", border: "1px solid var(--error)" }}>
          <AlertCircle size={18} style={{ color: "var(--error)" }} />
          <span className="text-sm" style={{ color: "var(--error)" }}>{error || "Failed to fetch analytics"}</span>
        </div>
      </div>
    );
  }

  const hasData = data.projects.length > 0;

  return (
    <div className="p-8">
      <div className="mb-8 flex justify-between items-center">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: "var(--text-primary)" }}>Analytics</h1>
          <p className="text-sm mt-1" style={{ color: "var(--text-secondary)" }}>
            Insights on your test suites performance, reliability, and code quality over time.
          </p>
        </div>
        <button
          onClick={fetchAnalytics}
          className="flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-medium cursor-pointer transition-colors hover:border-zinc-500"
          style={{ border: "1px solid var(--border)", color: "var(--text-secondary)", background: "var(--bg-secondary)" }}
        >
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      {/* Stats Summary Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="glass p-6">
          <div className="flex justify-between items-start mb-4">
            <div>
              <span className="text-xs" style={{ color: "var(--text-muted)" }}>Average Pass Rate</span>
              <h3 className="text-3xl font-bold mt-1" style={{ color: "var(--success)" }}>
                {data.averagePassRate}%
              </h3>
            </div>
            <div className="p-2 rounded-lg border" style={{ background: "rgba(16,185,129,0.06)", borderColor: "rgba(16,185,129,0.15)" }}>
              <CheckCircle size={20} style={{ color: "var(--success)" }} />
            </div>
          </div>
          <span className="text-xs" style={{ color: "var(--text-muted)" }}>
            Calculated across evaluated test cases
          </span>
        </div>

        <div className="glass p-6">
          <div className="flex justify-between items-start mb-4">
            <div>
              <span className="text-xs" style={{ color: "var(--text-muted)" }}>Total Run Time Saved</span>
              <h3 className="text-3xl font-bold mt-1" style={{ color: "var(--accent)" }}>
                {formatTimeSaved(data.totalTimeSavedMs)}
              </h3>
            </div>
            <div className="p-2 rounded-lg border" style={{ background: "var(--accent-glow)", borderColor: "rgba(139,92,246,0.15)" }}>
              <TrendingUp size={20} style={{ color: "var(--accent)" }} />
            </div>
          </div>
          <span className="text-xs" style={{ color: "var(--text-muted)" }}>
            Saved via parallel agent execution
          </span>
        </div>

        <div className="glass p-6">
          <div className="flex justify-between items-start mb-4">
            <div>
              <span className="text-xs" style={{ color: "var(--text-muted)" }}>Failed Run Alerts</span>
              <h3 className="text-3xl font-bold mt-1" style={{ color: "var(--error)" }}>
                {data.failedRunAlerts}
              </h3>
            </div>
            <div className="p-2 rounded-lg border" style={{ background: "rgba(244,63,94,0.06)", borderColor: "rgba(244,63,94,0.15)" }}>
              <ShieldAlert size={20} style={{ color: "var(--error)" }} />
            </div>
          </div>
          <span className="text-xs" style={{ color: "var(--text-muted)" }}>
            Failed runs requiring attention
          </span>
        </div>
      </div>

      {!hasData ? (
        <div className="glass p-12 text-center flex flex-col items-center justify-center gap-4">
          <BarChart2 size={48} style={{ color: "var(--text-muted)" }} />
          <div>
            <h3 className="text-lg font-semibold mb-1" style={{ color: "var(--text-primary)" }}>No data available</h3>
            <p className="text-sm max-w-sm mx-auto" style={{ color: "var(--text-secondary)" }}>
              Create a project and start a test run to generate workspace analytics metrics.
            </p>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Projects Performance Table */}
          <div className="glass p-6">
            <h3 className="text-base font-semibold mb-4" style={{ color: "var(--text-primary)" }}>
              Project Performance
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr style={{ borderBottom: "1px solid var(--border)" }}>
                    <th className="pb-3" style={{ color: "var(--text-muted)" }}>Project</th>
                    <th className="pb-3 text-center" style={{ color: "var(--text-muted)" }}>Runs</th>
                    <th className="pb-3 text-right" style={{ color: "var(--text-muted)" }}>Pass Rate</th>
                    <th className="pb-3 text-right" style={{ color: "var(--text-muted)" }}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {data.projects.map((p) => {
                    let passColor = "var(--error)";
                    if (p.passRate >= 80) passColor = "var(--success)";
                    else if (p.passRate >= 50) passColor = "var(--warning)";

                    return (
                      <tr key={p.id} style={{ borderBottom: "1px solid var(--border)", opacity: p.totalRuns > 0 ? 1 : 0.6 }}>
                        <td className="py-3">
                          <div className="font-medium" style={{ color: "var(--text-primary)" }}>{p.name}</div>
                          <div className="text-[10px]" style={{ color: "var(--text-muted)" }}>{p.websiteUrl}</div>
                        </td>
                        <td className="py-3 text-center" style={{ color: "var(--text-secondary)" }}>
                          {p.totalRuns}
                        </td>
                        <td className="py-3 text-right font-semibold" style={{ color: p.totalRuns > 0 ? passColor : "var(--text-muted)" }}>
                          {p.totalRuns > 0 ? `${p.passRate}%` : "N/A"}
                        </td>
                        <td className="py-3 text-right capitalize" style={{ color: p.status === "active" ? "var(--success)" : "var(--text-muted)" }}>
                          {p.status}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Recent Runs List */}
          <div className="glass p-6">
            <h3 className="text-base font-semibold mb-4" style={{ color: "var(--text-primary)" }}>
              Recent Workspace Runs
            </h3>
            <div className="space-y-3">
              {data.recentRuns.length === 0 ? (
                <p className="text-xs text-center py-8" style={{ color: "var(--text-muted)" }}>
                  No recent runs executed yet.
                </p>
              ) : (
                data.recentRuns.map((run) => {
                  let statusColor = "var(--text-muted)";
                  if (run.status === "completed") statusColor = "var(--success)";
                  else if (run.status === "failed") statusColor = "var(--error)";
                  else if (run.status === "executing") statusColor = "var(--accent)";

                  return (
                    <div
                      key={run.id}
                      className="p-3 rounded-lg flex items-center justify-between"
                      style={{ background: "var(--bg-secondary)", border: "1px solid var(--border)" }}
                    >
                      <div>
                        <div className="text-xs font-semibold" style={{ color: "var(--text-primary)" }}>
                          {run.projectName}
                        </div>
                        <div className="text-[10px] mt-0.5" style={{ color: "var(--text-muted)" }}>
                          Run ID: {run.id.slice(0, 8)} • {new Date(run.createdAt).toLocaleString()}
                        </div>
                      </div>
                      <div className="text-right">
                        <span className="text-[10px] capitalize font-semibold px-2 py-0.5 rounded-full" style={{ background: `rgba(255,255,255,0.05)`, color: statusColor }}>
                          {run.status}
                        </span>
                        <div className="text-[10px] mt-1" style={{ color: "var(--text-secondary)" }}>
                          <span style={{ color: "var(--success)" }}>{run.passedCases}</span> / <span style={{ color: "var(--error)" }}>{run.failedCases}</span> cases
                        </div>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
