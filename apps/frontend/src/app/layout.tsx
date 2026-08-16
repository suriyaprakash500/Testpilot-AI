import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700", "800"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "TestPilot AI — Automated Testing Platform",
  description: "AI-powered automated testing platform. Analyze repos, generate Playwright tests, and get debugging insights.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`dark ${inter.className}`}>
      <body className="antialiased">
        {children}
      </body>
    </html>
  );
}
