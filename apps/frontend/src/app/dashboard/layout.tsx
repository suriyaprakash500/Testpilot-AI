"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { 
  LayoutDashboard, 
  BarChart3, 
  Settings, 
  Search, 
  Bell, 
  ChevronDown
} from "lucide-react";

interface NavItem {
  label: string;
  href: string;
  icon: typeof LayoutDashboard;
}

const NAV_ITEMS: NavItem[] = [
  { label: "Dashboard", href: "/dashboard", icon: LayoutDashboard },
  { label: "Reports", href: "/dashboard/analytics", icon: BarChart3 },
  { label: "Settings", href: "/dashboard/settings", icon: Settings },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="min-h-screen flex relative overflow-hidden" style={{ background: "var(--bg-primary)" }}>
      {/* Cinematic Top-Right Backdrop Glow */}
      <div 
        className="absolute top-[-30%] right-[-10%] w-[60%] h-[60%] rounded-full opacity-[0.05] blur-[150px] pointer-events-none"
        style={{ background: "var(--gradient-1)" }}
      />
      
      {/* Left Sidebar */}
      <aside
        className="w-64 flex-shrink-0 flex flex-col z-20 border-r"
        style={{ background: "rgba(11, 15, 25, 0.8)", backdropFilter: "blur(20px)", borderColor: "var(--border)" }}
      >
        {/* Logo and Workspace Selector */}
        <div className="p-4 flex items-center justify-between border-b" style={{ borderColor: "var(--border)" }}>
          <div className="flex items-center gap-2">
            <div
              className="w-8 h-8 rounded-lg flex items-center justify-center text-white text-xs font-bold shadow-[0_0_12px_rgba(139,92,246,0.3)] border"
              style={{ background: "var(--gradient-1)", borderColor: "rgba(255,255,255,0.15)" }}
            >
              TP
            </div>
            <div className="flex flex-col">
              <span className="text-sm font-semibold tracking-tight" style={{ color: "var(--text-primary)" }}>
                TestPilot<span style={{ color: "var(--accent)" }}>AI</span>
              </span>
              <span className="text-[10px]" style={{ color: "var(--text-muted)" }}>Workspace IDE</span>
            </div>
          </div>
          <ChevronDown size={14} style={{ color: "var(--text-muted)" }} />
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-3 space-y-1">
          <div className="text-[10px] uppercase font-bold tracking-wider px-3 mb-2" style={{ color: "var(--text-muted)" }}>
            IDE Navigation
          </div>
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-all duration-200 ${
                  isActive ? "sidebar-nav-link-active" : "sidebar-nav-link"
                }`}
              >
                <Icon size={16} />
                {item.label}
              </Link>
            );
          })}
        </nav>

        {/* User Profile Footer */}
        <div className="p-3 border-t" style={{ borderColor: "var(--border)" }}>
          <div className="flex items-center gap-3 px-3 py-2">
            <div
              className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold border"
              style={{ background: "var(--bg-tertiary)", borderColor: "var(--border)", color: "var(--text-secondary)" }}
            >
              U
            </div>
            <div>
              <div className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                User Profile
              </div>
              <div className="text-[10px] font-mono text-violet-400">
                PRO DEV MODE
              </div>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top Navbar */}
        <header
          className="h-14 flex-shrink-0 flex items-center justify-between px-6 border-b z-10"
          style={{ background: "rgba(7, 11, 20, 0.7)", backdropFilter: "blur(12px)", borderColor: "var(--border)" }}
        >
          {/* Global Search Command Palette Bar */}
          <div className="flex items-center gap-3 w-80 relative">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: "var(--text-muted)" }} />
            <input
              type="text"
              readOnly
              placeholder="Search or ask AI... (Cmd + K)"
              className="w-full pl-9 pr-4 py-1.5 rounded-lg text-xs outline-none border cursor-pointer transition-all duration-200"
              style={{
                background: "var(--bg-secondary)",
                borderColor: "var(--border)",
                color: "var(--text-secondary)",
              }}
              onClick={() => alert("AI Command Palette activated.")}
            />
          </div>

          {/* Header Action Buttons */}
          <div className="flex items-center gap-4">
            <button 
              className="p-1.5 rounded-md border transition-all hover:bg-zinc-950 relative cursor-pointer" 
              style={{ borderColor: "var(--border)", color: "var(--text-secondary)" }}
              title="Notifications"
            >
              <Bell size={14} />
              <span className="absolute top-1 right-1 w-1.5 h-1.5 rounded-full bg-rose-500 pulse-dot" />
            </button>
          </div>
        </header>

        {/* Child Pages */}
        <main className="flex-1 overflow-y-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
