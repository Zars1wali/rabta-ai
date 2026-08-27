'use client';

import { useState } from 'react';
import { ShieldCheck, FileCheck, CheckCircle2, ArrowRight } from 'lucide-react';

export default function AuditPage() {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [companyUrl, setCompanyUrl] = useState('');
  const [notes, setNotes] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      const res = await fetch('/api/lead', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tenantId: '00000000-0000-4000-8000-000000000002',
          name,
          email,
          phone: '',
          companyUrl,
          notes: `Audit Request: ${notes}`
        })
      });

      if (res.ok) {
        setSubmitted(true);
      }
    } catch {
      // Fallback display
      setSubmitted(true);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-5xl px-6 py-16 md:py-24">
      <div className="text-center max-w-3xl mx-auto mb-16">
        <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs font-mono text-emerald-400 mb-4">
          <ShieldCheck className="h-4 w-4" />
          Certified EU AI Act Assessment (Articles 50 & 52)
        </div>
        <h1 className="text-4xl font-bold tracking-tight text-white sm:text-5xl">
          Comprehensive AI Act Compliance Audit
        </h1>
        <p className="mt-4 text-base text-slate-400">
          Ensure your generative AI models and autonomous agents meet full European regulatory obligations with certified 48-hour assessment reports.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-12 items-start">
        {/* Scope & Deliverables */}
        <div className="flex flex-col gap-6">
          <div className="rounded-2xl border border-slate-800 bg-[#0d121c] p-6 sm:p-8">
            <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <FileCheck className="h-5 w-5 text-emerald-400" />
              What the Audit Delivers
            </h2>

            <ul className="flex flex-col gap-4 text-xs sm:text-sm text-slate-300">
              <li className="flex items-start gap-3">
                <CheckCircle2 className="h-5 w-5 text-emerald-400 shrink-0 mt-0.5" />
                <div>
                  <span className="font-semibold text-white">Article 50 Transparency & Labeling:</span>
                  <p className="text-slate-400 text-xs mt-0.5">Verification of clear, non-removable AI disclosure on all public endpoints and chats.</p>
                </div>
              </li>
              <li className="flex items-start gap-3">
                <CheckCircle2 className="h-5 w-5 text-emerald-400 shrink-0 mt-0.5" />
                <div>
                  <span className="font-semibold text-white">Article 52 Watermarking & Provenance:</span>
                  <p className="text-slate-400 text-xs mt-0.5">Assessment of machine-readable watermarking on synthetic audio, text, and media.</p>
                </div>
              </li>
              <li className="flex items-start gap-3">
                <CheckCircle2 className="h-5 w-5 text-emerald-400 shrink-0 mt-0.5" />
                <div>
                  <span className="font-semibold text-white">Adversarial Red-Teaming:</span>
                  <p className="text-slate-400 text-xs mt-0.5">Automated stress-testing against 50+ prompt injection, jailbreak, and system extraction vectors.</p>
                </div>
              </li>
              <li className="flex items-start gap-3">
                <CheckCircle2 className="h-5 w-5 text-emerald-400 shrink-0 mt-0.5" />
                <div>
                  <span className="font-semibold text-white">Certified PDF Deliverable:</span>
                  <p className="text-slate-400 text-xs mt-0.5">Executive summary, technical gap analysis, and prioritized remediation roadmap within 48h.</p>
                </div>
              </li>
            </ul>
          </div>

          <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-4 flex items-center justify-between font-mono text-xs text-slate-300">
            <span>Engagement Fee: <strong>€1,500.00</strong></span>
            <span className="rounded bg-emerald-500/20 px-2 py-0.5 text-emerald-400">48h SLA</span>
          </div>
        </div>

        {/* Audit Request Form */}
        <div className="rounded-2xl border border-slate-800 bg-[#0d121c] p-6 sm:p-8">
          {submitted ? (
            <div className="text-center py-12 flex flex-col items-center">
              <div className="h-12 w-12 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center mb-4">
                <CheckCircle2 className="h-6 w-6" />
              </div>
              <h2 className="text-xl font-bold text-white">Audit Request Received</h2>
              <p className="text-xs text-slate-400 mt-2 max-w-xs">
                A ZeroPointIntel lead security engineer will review your system details and contact you within 2 hours.
              </p>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="flex flex-col gap-4">
              <h2 className="text-lg font-semibold text-white mb-2">Request System Audit</h2>

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Full Name</label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Alex Rivera"
                  className="w-full rounded-lg border border-slate-800 bg-slate-900/90 px-3.5 py-2.5 text-xs text-white placeholder:text-slate-600 focus:border-emerald-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Business Email</label>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="alex@company.com"
                  className="w-full rounded-lg border border-slate-800 bg-slate-900/90 px-3.5 py-2.5 text-xs text-white placeholder:text-slate-600 focus:border-emerald-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Company / Product URL</label>
                <input
                  type="url"
                  required
                  value={companyUrl}
                  onChange={(e) => setCompanyUrl(e.target.value)}
                  placeholder="https://company.com"
                  className="w-full rounded-lg border border-slate-800 bg-slate-900/90 px-3.5 py-2.5 text-xs text-white placeholder:text-slate-600 focus:border-emerald-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">AI Architecture Notes</label>
                <textarea
                  rows={3}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Describe your current LLM stack, autonomous tools, and deployment region..."
                  className="w-full rounded-lg border border-slate-800 bg-slate-900/90 px-3.5 py-2.5 text-xs text-white placeholder:text-slate-600 focus:border-emerald-500 focus:outline-none resize-none"
                />
              </div>

              <button
                type="submit"
                disabled={loading}
                className="mt-2 inline-flex items-center justify-center gap-2 rounded-lg bg-emerald-500 py-3 text-xs font-semibold text-slate-950 hover:bg-emerald-400 transition-colors shadow-md disabled:opacity-50"
              >
                {loading ? 'Submitting...' : 'Submit Audit Inquiry'}
                <ArrowRight className="h-4 w-4" />
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
