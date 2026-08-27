import type { Metadata } from 'next';
import './globals.css';
import { ClientWidget } from '../components/ClientWidget';

export const metadata: Metadata = {
  title: 'ZeroPointIntel | Autonomous Agent Security & EU AI Act Conformity',
  description:
    'High-assurance cybersecurity, runtime prompt injection guardrails, and EU AI Act Article 50 & 52 compliance for autonomous AI systems.',
  icons: {
    icon: '/favicon.ico'
  }
};

export default function RootLayout({
  children
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-[#07090e] text-slate-100 antialiased selection:bg-emerald-500 selection:text-black">
        <header className="sticky top-0 z-40 border-b border-slate-800/80 bg-[#07090e]/80 backdrop-blur-md">
          <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
            <a href="/" className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 font-mono font-bold text-lg">
                ZPI
              </div>
              <div className="flex flex-col">
                <span className="font-semibold tracking-tight text-white text-base">ZeroPointIntel</span>
                <span className="text-[10px] uppercase font-mono tracking-widest text-emerald-400">Cybersecurity & AI Ops</span>
              </div>
            </a>

            <nav className="hidden md:flex items-center gap-8 text-sm font-medium text-slate-300">
              <a href="/#solutions" className="hover:text-emerald-400 transition-colors">Solutions</a>
              <a href="/audit" className="hover:text-emerald-400 transition-colors">EU AI Act Audit</a>
              <a href="/#pricing" className="hover:text-emerald-400 transition-colors">Pricing</a>
              <a href="/agent" className="flex items-center gap-1.5 text-emerald-400 hover:text-emerald-300 transition-colors">
                <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
                Live Copilot
              </a>
            </nav>

            <div className="flex items-center gap-4">
              <a
                href="/audit"
                className="rounded-lg bg-emerald-500 px-4 py-2 text-xs font-semibold text-slate-950 hover:bg-emerald-400 transition-colors shadow-sm shadow-emerald-500/20"
              >
                Request Audit
              </a>
            </div>
          </div>
        </header>

        <main className="relative">{children}</main>

        <footer className="border-t border-slate-800/80 bg-[#040609] py-12 text-slate-400 text-xs">
          <div className="mx-auto max-w-7xl px-6 flex flex-col md:flex-row items-center justify-between gap-6">
            <div className="flex flex-col gap-2">
              <div className="flex items-center gap-2 font-mono text-slate-300 text-sm font-bold">
                <span>ZeroPointIntel</span>
                <span className="rounded bg-emerald-500/10 px-2 py-0.5 text-[10px] text-emerald-400 border border-emerald-500/20">EU AI Act Article 50 Compliant</span>
              </div>
              <p className="text-slate-500 text-[11px] max-w-md">
                Certified cybersecurity, runtime prompt injection firewalls, and AI Act compliance audits for European autonomous AI systems.
              </p>
            </div>
            <div className="text-slate-500 text-right text-[11px]">
              <p>&copy; {new Date().getFullYear()} ZeroPointIntel. All rights reserved.</p>
              <p className="mt-1">Europe-Tier Data Residency · Hosted exclusively in EU datacenters.</p>
            </div>
          </div>
        </footer>

        {/* Embedded SalesOps Autonomous Copilot */}
        <ClientWidget />
      </body>
    </html>
  );
}
