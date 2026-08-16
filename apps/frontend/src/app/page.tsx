"use client";

import { useState } from "react";
import { Zap, GitBranch, Globe, ArrowRight, Shield, BarChart3, Bot } from "lucide-react";
import { api, getErrorMessage } from "../lib/api";

const FEATURE_CARDS = [
  {
    icon: Bot,
    title: "AI-Powered Analysis",
    description: "Understands your app structure, routes, components, and auth flows automatically.",
  },
  {
    icon: Shield,
    title: "Smart Test Generation",
    description: "Generates robust Playwright tests with resilient locators and proper assertions.",
  },
  {
    icon: BarChart3,
    title: "Debugging Insights",
    description: "Analyzes failures with AI, finds root causes, and suggests fixes with screenshots.",
  },
] as const;

export default function HomePage() {
  const [repoUrl, setRepoUrl] = useState("");
  const [websiteUrl, setWebsiteUrl] = useState("");
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleStartTesting = async () => {
    if (!repoUrl || !websiteUrl || testing) {
      return;
    }

    setTesting(true);
    setError(null);

    try {
      if (!localStorage.getItem("token")) {
        localStorage.setItem("token", "dev-mock-jwt-token");
      }
      const project = await api.createProject({ repoUrl, websiteUrl });
      window.location.href = `/dashboard/${project.id}`;
    } catch (err: unknown) {
      setError(getErrorMessage(err, "Failed to initialize workspace."));
      setTesting(false);
    }
  };

  const isFormValid = Boolean(repoUrl.trim() && websiteUrl.trim() && !testing);

  return (
    <div className="min-h-screen" style={{ background: "var(--bg-primary)" }}>
      {/* Navigation */}
      <nav
        className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-6 py-4"
        style={{
          background: "rgba(9,9,11,0.8)",
          backdropFilter: "blur(12px)",
          borderBottom: "1px solid var(--border)",
        }}
      >
        <div className="flex items-center gap-2">
          <div
            className="w-8 h-8 rounded-lg flex items-center justify-center"
            style={{ background: "var(--gradient-1)" }}
          >
            <Zap size={18} color="white" />
          </div>
          <span className="text-lg font-semibold" style={{ color: "var(--text-primary)" }}>
            TestPilot<span style={{ color: "var(--accent)" }}>AI</span>
          </span>
        </div>
        <a
          href={`${process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:3001"}/api/auth/github`}
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200"
          style={{
            background: "var(--bg-secondary)",
            border: "1px solid var(--border)",
            color: "var(--text-primary)",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.borderColor = "var(--accent)";
            e.currentTarget.style.background = "var(--accent-glow)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.borderColor = "var(--border)";
            e.currentTarget.style.background = "var(--bg-secondary)";
          }}
        >
          <GitBranch size={16} />
          Sign in with GitHub
        </a>
      </nav>

      {/* Hero Section */}
      <main className="pt-32 px-6 max-w-5xl mx-auto">
        <div className="text-center animate-fade-in">
          <div
            className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-medium mb-6"
            style={{
              background: "var(--accent-glow)",
              color: "var(--accent-hover)",
              border: "1px solid rgba(99,102,241,0.3)",
            }}
          >
            <span className="w-1.5 h-1.5 rounded-full pulse-dot" style={{ background: "var(--accent)" }} />
            AI-Powered Testing Platform
          </div>

          <h1
            className="text-5xl md:text-7xl font-bold tracking-tight leading-tight mb-6"
            style={{ color: "var(--text-primary)" }}
          >
            Ship with
            <span className="gradient-text"> confidence.</span>
            <br />
            Test with <span className="gradient-text">AI.</span>
          </h1>

          <p className="text-lg md:text-xl max-w-2xl mx-auto mb-12" style={{ color: "var(--text-secondary)" }}>
            Connect your GitHub repo and website. TestPilot AI analyzes your app,
            generates Playwright tests, runs them, and delivers debugging insights — automatically.
          </p>

          {/* Onboarding Form */}
          <div className="glass max-w-xl mx-auto p-6 animate-slide-up" style={{ animationDelay: "0.2s" }}>
            <div className="space-y-4">
              <div className="text-left">
                <label className="text-sm font-medium mb-1.5 block" style={{ color: "var(--text-secondary)" }}>
                  GitHub Repository URL
                </label>
                <div className="relative">
                  <GitBranch
                    size={16}
                    className="absolute left-3 top-1/2 -translate-y-1/2"
                    style={{ color: "var(--text-muted)" }}
                  />
                  <input
                    id="repo-url-input"
                    type="url"
                    placeholder="https://github.com/username/repo"
                    value={repoUrl}
                    onChange={(e) => setRepoUrl(e.target.value)}
                    className="w-full pl-10 pr-4 py-2.5 rounded-lg text-sm transition-all duration-200 outline-none"
                    style={{
                      background: "var(--bg-primary)",
                      border: "1px solid var(--border)",
                      color: "var(--text-primary)",
                    }}
                    onFocus={(e) => {
                      e.target.style.borderColor = "var(--accent)";
                    }}
                    onBlur={(e) => {
                      e.target.style.borderColor = "var(--border)";
                    }}
                  />
                </div>
              </div>

              <div className="text-left">
                <label className="text-sm font-medium mb-1.5 block" style={{ color: "var(--text-secondary)" }}>
                  Website URL
                </label>
                <div className="relative">
                  <Globe
                    size={16}
                    className="absolute left-3 top-1/2 -translate-y-1/2"
                    style={{ color: "var(--text-muted)" }}
                  />
                  <input
                    id="website-url-input"
                    type="url"
                    placeholder="https://your-app.vercel.app"
                    value={websiteUrl}
                    onChange={(e) => setWebsiteUrl(e.target.value)}
                    className="w-full pl-10 pr-4 py-2.5 rounded-lg text-sm transition-all duration-200 outline-none"
                    style={{
                      background: "var(--bg-primary)",
                      border: "1px solid var(--border)",
                      color: "var(--text-primary)",
                    }}
                    onFocus={(e) => {
                      e.target.style.borderColor = "var(--accent)";
                    }}
                    onBlur={(e) => {
                      e.target.style.borderColor = "var(--border)";
                    }}
                  />
                </div>
              </div>

              {error && (
                <p className="text-xs text-left" style={{ color: "var(--error)" }}>
                  {error}
                </p>
              )}

              <button
                id="start-testing-btn"
                className="w-full flex items-center justify-center gap-2 px-4 py-3 rounded-lg text-sm font-semibold transition-all duration-200 cursor-pointer"
                style={{
                  background: "var(--gradient-1)",
                  color: "white",
                  opacity: isFormValid ? 1 : 0.5,
                }}
                disabled={!isFormValid}
                onClick={handleStartTesting}
              >
                {testing ? "Initializing Workspace..." : "Start Testing"}
                <ArrowRight size={16} />
              </button>
            </div>
          </div>
        </div>

        {/* Feature Highlights */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-24 mb-20">
          {FEATURE_CARDS.map((feature, index) => (
            <div
              key={feature.title}
              className="glass p-6 animate-slide-up transition-all duration-300"
              style={{ animationDelay: `${0.3 + index * 0.1}s` }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = "var(--border-hover)";
                e.currentTarget.style.transform = "translateY(-2px)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = "var(--border)";
                e.currentTarget.style.transform = "translateY(0)";
              }}
            >
              <div
                className="w-10 h-10 rounded-lg flex items-center justify-center mb-4"
                style={{ background: "var(--accent-glow)" }}
              >
                <feature.icon size={20} style={{ color: "var(--accent)" }} />
              </div>
              <h3 className="text-base font-semibold mb-2" style={{ color: "var(--text-primary)" }}>
                {feature.title}
              </h3>
              <p className="text-sm leading-relaxed" style={{ color: "var(--text-secondary)" }}>
                {feature.description}
              </p>
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
