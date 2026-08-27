'use client';

import { useSalesOpsChat } from '@salesops/web/ui';
import { Bot, Send, User, ShieldCheck, Sparkles, RefreshCw } from 'lucide-react';
import { useState } from 'react';

export default function AgentPage() {
  const [inputValue, setInputValue] = useState('');

  const {
    messages,
    sendMessage,
    status,
    startSession
  } = useSalesOpsChat({
    storeName: 'ZeroPoint Security Copilot',
    primaryColor: '#10b981',
    apiBaseUrl: '/api',
    locale: 'en',
    initialOpen: true
  });

  const isLoading = status === 'loading';

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputValue.trim() || isLoading) return;
    const text = inputValue;
    setInputValue('');
    await sendMessage(text);
  };

  return (
    <div className="mx-auto max-w-4xl px-6 py-10 flex flex-col h-[calc(100vh-140px)]">
      {/* Header Info */}
      <div className="flex items-center justify-between border-b border-slate-800 pb-4 mb-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <Bot className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-base font-semibold text-white">ZeroPoint Security Copilot</h1>
            <p className="text-xs text-slate-400">Autonomous AI Ops & Compliance Specialist · EU-Resident</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => startSession('en')}
            title="Reset Session"
            className="rounded-lg border border-slate-800 bg-slate-900/60 p-2 text-slate-400 hover:text-white transition-colors text-xs flex items-center gap-1.5"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">Reset Session</span>
          </button>
        </div>
      </div>

      {/* EU AI Act Article 50 Disclosure */}
      <div className="mb-4 rounded-lg border border-emerald-500/20 bg-emerald-500/5 px-3 py-2 text-[11px] font-mono text-emerald-400 flex items-center gap-2">
        <ShieldCheck className="h-4 w-4 shrink-0" />
        <span>EU AI Act Art. 50: You are interacting with an autonomous AI security assistant.</span>
      </div>

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto space-y-4 pr-2 font-sans">
        {messages.map((m) => (
          <div
            key={m.id}
            className={`flex items-start gap-3 ${m.role === 'visitor' ? 'flex-row-reverse' : ''}`}
          >
            <div
              className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${
                m.role === 'visitor'
                  ? 'bg-slate-700 text-white'
                  : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
              }`}
            >
              {m.role === 'visitor' ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
            </div>

            <div
              className={`max-w-[80%] rounded-2xl px-4 py-3 text-xs leading-relaxed ${
                m.role === 'visitor'
                  ? 'bg-emerald-600 text-slate-950 font-medium'
                  : 'bg-slate-900/90 border border-slate-800 text-slate-200'
              }`}
            >
              {m.content}
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
              <Bot className="h-4 w-4" />
            </div>
            <div className="rounded-2xl border border-slate-800 bg-slate-900/90 px-4 py-3 text-xs text-slate-400 flex items-center gap-2">
              <Sparkles className="h-3.5 w-3.5 animate-spin text-emerald-400" />
              Evaluating security catalog & policies...
            </div>
          </div>
        )}
      </div>

      {/* Input Area */}
      <form onSubmit={handleSend} className="mt-4 flex items-center gap-2">
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          placeholder="Ask about AI Act compliance, red-teaming, or audit pricing..."
          className="flex-1 rounded-xl border border-slate-800 bg-slate-900/90 px-4 py-3 text-xs text-white placeholder:text-slate-500 focus:border-emerald-500 focus:outline-none"
        />
        <button
          type="submit"
          disabled={isLoading || !inputValue.trim()}
          className="rounded-xl bg-emerald-500 px-5 py-3 text-xs font-semibold text-slate-950 hover:bg-emerald-400 transition-colors disabled:opacity-50 flex items-center gap-1.5 shadow-md shadow-emerald-500/10"
        >
          <span>Send</span>
          <Send className="h-3.5 w-3.5" />
        </button>
      </form>
    </div>
  );
}
