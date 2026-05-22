import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Dashboard — TestPilot AI",
};

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen flex" style={{ background: "var(--bg-primary)" }}>
      {/* Sidebar */}
      <aside
        className="w-64 flex-shrink-0 flex flex-col"
        style={{ background: "var(--bg-secondary)", borderRight: "1px solid var(--border)" }}
      >
        <div className="p-4 flex items-center gap-2" style={{ borderBottom: "1px solid var(--border)" }}>
          <div
            className="w-7 h-7 rounded-md flex items-center justify-center text-white text-xs font-bold"
            style={{ background: "var(--gradient-1)" }}
          >
            TP
          </div>
          <span className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
            TestPilot<span style={{ color: "var(--accent)" }}>AI</span>
          </span>
        </div>

        <nav className="flex-1 p-3 space-y-1">
          {[
            { label: "Projects", href: "/dashboard", icon: "📁" },
            { label: "Test Runs", href: "/dashboard/runs", icon: "🧪" },
            { label: "Analytics", href: "/dashboard/analytics", icon: "📊" },
            { label: "Settings", href: "/dashboard/settings", icon: "⚙️" },
          ].map((item) => (
            <a
              key={item.href}
              href={item.href}
              className="sidebar-nav-link flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-all duration-150"
            >
              <span>{item.icon}</span>
              {item.label}
            </a>
          ))}
        </nav>

        <div className="p-3" style={{ borderTop: "1px solid var(--border)" }}>
          <div className="flex items-center gap-3 px-3 py-2">
            <div
              className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold"
              style={{ background: "var(--bg-tertiary)", color: "var(--text-muted)" }}
            >
              U
            </div>
            <div>
              <div className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>
                User
              </div>
              <div className="text-xs" style={{ color: "var(--text-muted)" }}>
                Free Plan
              </div>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 overflow-y-auto">
        {children}
      </main>
    </div>
  );
}
