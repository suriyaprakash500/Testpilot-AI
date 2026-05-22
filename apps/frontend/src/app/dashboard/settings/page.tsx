"use client";

import { useRouter } from "next/navigation";
import { LogOut, User, Globe, GitBranch } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../../../lib/api";

export default function SettingsPage() {
  const router = useRouter();
  const [user, setUser] = useState<{ name: string; email: string; avatarUrl: string } | null>(null);

  useEffect(() => {
    api.getCurrentUser()
      .then(setUser)
      .catch(() => {});
  }, []);

  const handleLogout = () => {
    localStorage.removeItem("token");
    router.push("/");
  };

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold" style={{ color: "var(--text-primary)" }}>Settings</h1>
        <p className="text-sm mt-1" style={{ color: "var(--text-secondary)" }}>
          Manage your account configurations, integrations, and connection credentials.
        </p>
      </div>

      <div className="space-y-6 max-w-2xl">
        {/* Profile Card */}
        <div className="glass p-6">
          <h2 className="text-base font-semibold mb-4" style={{ color: "var(--text-primary)" }}>Account Profile</h2>
          <div className="flex items-center gap-4">
            {user?.avatarUrl ? (
              <img src={user.avatarUrl} alt="Avatar" className="w-12 h-12 rounded-full" />
            ) : (
              <div className="w-12 h-12 rounded-full flex items-center justify-center" style={{ background: "var(--bg-tertiary)" }}>
                <User size={24} style={{ color: "var(--text-muted)" }} />
              </div>
            )}
            <div>
              <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{user?.name || "Loading..."}</h3>
              <p className="text-xs" style={{ color: "var(--text-muted)" }}>{user?.email || "GitHub Integrated"}</p>
            </div>
          </div>
        </div>

        {/* Integration Credentials */}
        <div className="glass p-6">
          <h2 className="text-base font-semibold mb-4" style={{ color: "var(--text-primary)" }}>Integrations</h2>
          <div className="space-y-4">
            <div className="flex items-center justify-between p-3 rounded-lg border" style={{ borderColor: "var(--border)", background: "var(--bg-primary)" }}>
              <div className="flex items-center gap-3">
                <GitBranch size={18} style={{ color: "var(--accent)" }} />
                <div>
                  <div className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>GitHub Connection</div>
                  <div className="text-xs" style={{ color: "var(--text-muted)" }}>Access granted to verify webhooks & post PR reviews</div>
                </div>
              </div>
              <span className="text-xs font-semibold px-2.5 py-1 rounded" style={{ background: "rgba(34,197,94,0.1)", color: "var(--success)" }}>Connected</span>
            </div>

            <div className="flex items-center justify-between p-3 rounded-lg border" style={{ borderColor: "var(--border)", background: "var(--bg-primary)" }}>
              <div className="flex items-center gap-3">
                <Globe size={18} style={{ color: "var(--accent)" }} />
                <div>
                  <div className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>Backend URL</div>
                  <div className="text-xs" style={{ color: "var(--text-muted)" }}>{process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:3001"}</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Sign Out */}
        <div className="glass p-6 flex justify-between items-center" style={{ borderLeft: "4px solid var(--error)" }}>
          <div>
            <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Sign Out</h3>
            <p className="text-xs" style={{ color: "var(--text-muted)" }}>Sign out of your active browser session on this device.</p>
          </div>
          <button
            onClick={handleLogout}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold cursor-pointer transition-all duration-150"
            style={{ background: "rgba(239,68,68,0.1)", border: "1px solid var(--error)", color: "var(--error)" }}
          >
            <LogOut size={16} />
            Sign Out
          </button>
        </div>
      </div>
    </div>
  );
}
