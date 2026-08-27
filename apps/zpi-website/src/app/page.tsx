import { ShieldCheck, Terminal, Cpu, FileCheck, ArrowRight, CheckCircle2 } from 'lucide-react';

export default function HomePage() {
  return (
    <div className="flex flex-col gap-24 pb-24">
      {/* Hero Section */}
      <section className="relative overflow-hidden pt-20 pb-16 md:pt-28 md:pb-24 border-b border-slate-800/60">
        <div className="absolute inset-0 -z-10 bg-[radial-gradient(ellipse_80%_80%_at_50%_-20%,rgba(16,185,129,0.15),rgba(255,255,255,0))]" />
        
        <div className="mx-auto max-w-7xl px-6 flex flex-col items-center text-center">
          <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs font-mono text-emerald-400 mb-6">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
            Zero-Trust Agent Security & EU AI Act Conformity
          </div>

          <h1 className="max-w-4xl text-4xl font-bold tracking-tight sm:text-6xl text-white">
            High-Assurance Security for <span className="text-emerald-400">Autonomous AI Agents</span>
          </h1>

          <p className="mt-6 max-w-2xl text-base sm:text-lg text-slate-400">
            Prevent prompt injection attacks, enforce runtime token budgets, and guarantee Article 50 & 52 EU AI Act compliance with certified technical documentation.
          </p>

          <div className="mt-10 flex flex-wrap items-center justify-center gap-4">
            <a
              href="/audit"
              className="inline-flex items-center gap-2 rounded-lg bg-emerald-500 px-6 py-3 text-sm font-semibold text-slate-950 hover:bg-emerald-400 transition-colors shadow-lg shadow-emerald-500/20"
            >
              Book EU AI Act Audit (€1,500)
              <ArrowRight className="h-4 w-4" />
            </a>
            <a
              href="/agent"
              className="inline-flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-900/80 px-6 py-3 text-sm font-semibold text-slate-200 hover:bg-slate-800 transition-colors"
            >
              Talk with Agent Copilot
            </a>
          </div>

          {/* Real-time Status Card */}
          <div className="mt-16 w-full max-w-4xl rounded-xl border border-slate-800 bg-[#0c1017] p-4 sm:p-6 shadow-2xl text-left font-mono text-xs text-slate-300">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-4 text-slate-400">
              <div className="flex items-center gap-2">
                <Terminal className="h-4 w-4 text-emerald-400" />
                <span>ZeroPoint Guardrails Engine · Status: ACTIVE</span>
              </div>
              <span className="rounded bg-emerald-500/20 px-2 py-0.5 text-emerald-400 text-[11px]">15ms Overhead</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-slate-400">
              <div className="rounded-lg bg-slate-900/60 p-3 border border-slate-800/80">
                <span className="block text-[10px] uppercase tracking-wider text-slate-500">Inbound Injection Firewall</span>
                <span className="text-sm font-semibold text-emerald-400 mt-1 block">100% Mitigated</span>
              </div>
              <div className="rounded-lg bg-slate-900/60 p-3 border border-slate-800/80">
                <span className="block text-[10px] uppercase tracking-wider text-slate-500">EU Data Residency</span>
                <span className="text-sm font-semibold text-white mt-1 block">Paris / Frankfurt (EU)</span>
              </div>
              <div className="rounded-lg bg-slate-900/60 p-3 border border-slate-800/80">
                <span className="block text-[10px] uppercase tracking-wider text-slate-500">Article 50 Watermarking</span>
                <span className="text-sm font-semibold text-emerald-400 mt-1 block">Enforced & Signed</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Solutions Grid */}
      <section id="solutions" className="mx-auto max-w-7xl px-6">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <h2 className="text-xs uppercase font-mono tracking-widest text-emerald-400 mb-2">Capabilities & Protection</h2>
          <h3 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
            Built for Mission-Critical AI Systems
          </h3>
          <p className="mt-4 text-slate-400 text-sm sm:text-base">
            Autonomous systems require continuous runtime verification, deterministic tools, and rigorous compliance boundaries.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          <div className="rounded-2xl border border-slate-800 bg-[#0d121c] p-8 flex flex-col justify-between hover:border-emerald-500/40 transition-colors">
            <div>
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 mb-6">
                <ShieldCheck className="h-6 w-6" />
              </div>
              <h4 className="text-lg font-semibold text-white">Runtime Injection Firewall</h4>
              <p className="mt-3 text-sm text-slate-400 leading-relaxed">
                Zero-latency heuristic & embedding-based filters preventing indirect prompt injections, jailbreaks, and sensitive data leakage.
              </p>
            </div>
            <ul className="mt-6 flex flex-col gap-2.5 text-xs text-slate-300 border-t border-slate-800/80 pt-6">
              <li className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-400" /> 15ms inline evaluation</li>
              <li className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-400" /> Out-of-catalog assertion blocking</li>
              <li className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-400" /> Multi-tenant boundary isolation</li>
            </ul>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-[#0d121c] p-8 flex flex-col justify-between hover:border-emerald-500/40 transition-colors">
            <div>
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 mb-6">
                <FileCheck className="h-6 w-6" />
              </div>
              <h4 className="text-lg font-semibold text-white">EU AI Act Conformity (Art. 50 & 52)</h4>
              <p className="mt-3 text-sm text-slate-400 leading-relaxed">
                Comprehensive conformity audits, synthetic content watermarking verification, and certified risk classification documents.
              </p>
            </div>
            <ul className="mt-6 flex flex-col gap-2.5 text-xs text-slate-300 border-t border-slate-800/80 pt-6">
              <li className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-400" /> 48-hour turn-around assessment</li>
              <li className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-400" /> Certified audit deliverable PDF</li>
              <li className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-400" /> Regulatory remediation checklist</li>
            </ul>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-[#0d121c] p-8 flex flex-col justify-between hover:border-emerald-500/40 transition-colors">
            <div>
              <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 mb-6">
                <Cpu className="h-6 w-6" />
              </div>
              <h4 className="text-lg font-semibold text-white">24/7 Autonomous Agent SOC</h4>
              <p className="mt-3 text-sm text-slate-400 leading-relaxed">
                Managed security operations center dedicated to autonomous agent telemetry, adversarial drift detection, and budget enforcement.
              </p>
            </div>
            <ul className="mt-6 flex flex-col gap-2.5 text-xs text-slate-300 border-t border-slate-800/80 pt-6">
              <li className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-400" /> Real-time spend & loop circuit breaker</li>
              <li className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-400" /> Continuous red-teaming probe suite</li>
              <li className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-400" /> Dedicated security engineer response</li>
            </ul>
          </div>
        </div>
      </section>

      {/* Pricing Section */}
      <section id="pricing" className="mx-auto max-w-7xl px-6">
        <div className="text-center max-w-3xl mx-auto mb-16">
          <h2 className="text-xs uppercase font-mono tracking-widest text-emerald-400 mb-2">Clear & Transparent Investment</h2>
          <h3 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
            Certified Security & Compliance Packages
          </h3>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-4xl mx-auto">
          {/* Audit Package */}
          <div className="rounded-2xl border border-emerald-500/40 bg-[#0e1420] p-8 flex flex-col justify-between relative shadow-xl shadow-emerald-500/5">
            <div className="absolute -top-3 right-6 rounded-full bg-emerald-500 px-3 py-1 text-[10px] font-bold uppercase tracking-wider text-slate-950">
              One-Time Audit
            </div>
            <div>
              <h4 className="text-xl font-bold text-white">EU AI Act Comprehensive Audit</h4>
              <p className="text-xs text-slate-400 mt-2">Article 50 & 52 Technical Assessment</p>
              
              <div className="mt-6 flex items-baseline gap-1">
                <span className="text-4xl font-extrabold text-white">€1,500</span>
                <span className="text-xs text-slate-400 font-mono">/ engagement</span>
              </div>

              <ul className="mt-8 flex flex-col gap-3 text-xs text-slate-300">
                <li className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-400" /> Full technical documentation review</li>
                <li className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-400" /> Transparency disclosure & watermarking tests</li>
                <li className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-400" /> Prompt injection adversarial stress test</li>
                <li className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-400" /> 48-Hour delivery with certified PDF report</li>
              </ul>
            </div>

            <a
              href="/audit"
              className="mt-8 block w-full rounded-lg bg-emerald-500 py-3 text-center text-xs font-semibold text-slate-950 hover:bg-emerald-400 transition-colors shadow-md"
            >
              Order EU AI Act Audit
            </a>
          </div>

          {/* SOC Monthly */}
          <div className="rounded-2xl border border-slate-800 bg-[#0d121c] p-8 flex flex-col justify-between">
            <div>
              <h4 className="text-xl font-bold text-white">ZeroPoint Agent SOC & Guardrails</h4>
              <p className="text-xs text-slate-400 mt-2">Continuous Runtime Protection & Monitoring</p>
              
              <div className="mt-6 flex items-baseline gap-1">
                <span className="text-4xl font-extrabold text-white">€490</span>
                <span className="text-xs text-slate-400 font-mono">/ month</span>
              </div>

              <ul className="mt-8 flex flex-col gap-3 text-xs text-slate-300">
                <li className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-400" /> 24/7 telemetry and runtime guardrail firewall</li>
                <li className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-400" /> Dynamic token budget & spend caps</li>
                <li className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-400" /> Weekly automated red-teaming simulations</li>
                <li className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-emerald-400" /> Dedicated principal security engineer SLA</li>
              </ul>
            </div>

            <a
              href="/agent"
              className="mt-8 block w-full rounded-lg border border-slate-700 bg-slate-800/80 py-3 text-center text-xs font-semibold text-slate-200 hover:bg-slate-700 transition-colors"
            >
              Consult with Security Copilot
            </a>
          </div>
        </div>
      </section>
    </div>
  );
}
