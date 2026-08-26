import React, { useState, useEffect, useRef } from 'react';
import { useSalesOpsChat } from './useSalesOpsChat.js';
import type { WidgetConfig } from './types.js';

export interface SalesOpsWidgetProps extends WidgetConfig {
  className?: string;
}

export const SalesOpsWidget: React.FC<SalesOpsWidgetProps> = ({
  storeName = 'Rewilt Store',
  primaryColor = '#1e293b',
  position = 'bottom-right',
  apiBaseUrl,
  locale = 'pt-PT',
  initialOpen = false,
  className = ''
}) => {
  const {
    messages,
    status,
    sessionId,
    isOpen,
    startSession,
    sendMessage,
    toggle,
    close
  } = useSalesOpsChat({
    apiBaseUrl,
    locale,
    storeName,
    initialOpen
  });

  const [inputVal, setInputVal] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Initialize session when widget is first opened
  useEffect(() => {
    if (isOpen && !sessionId && status === 'idle' && messages.length === 0) {
      void startSession();
    }
  }, [isOpen, sessionId, status, messages.length, startSession]);

  // Auto-scroll to bottom on new message / streaming token
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, status]);

  const handleSend = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputVal.trim()) return;
    void sendMessage(inputVal);
    setInputVal('');
  };

  const posClass =
    position === 'bottom-left' ? 'left-6 bottom-6' : 'right-6 bottom-6';

  return (
    <div
      className={`salesops-widget-root fixed ${posClass} z-50 flex flex-col items-end font-sans ${className}`}
      data-testid="salesops-widget"
    >
      {isOpen && (
        <div
          role="dialog"
          aria-label={`Chat with ${storeName} AI Assistant`}
          className="salesops-modal mb-4 w-96 max-w-[calc(100vw-2rem)] h-[550px] max-h-[calc(100vh-6rem)] bg-white rounded-2xl shadow-2xl border border-gray-200 flex flex-col overflow-hidden transition-all duration-300 ease-in-out"
          style={{ boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1)' }}
        >
          {/* Header with EU AI Act Art. 50 AI Assistant Disclosure Badge */}
          <div
            className="salesops-header px-4 py-3 text-white flex items-center justify-between"
            style={{ backgroundColor: primaryColor }}
          >
            <div>
              <div className="font-semibold text-base leading-tight">{storeName}</div>
              {/* Mandatory AI Disclosure Badge */}
              <div
                className="salesops-ai-badge inline-flex items-center gap-1 mt-0.5 text-xs text-emerald-300 font-medium tracking-wide"
                data-testid="eu-ai-act-disclosure-badge"
              >
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                <span>Assistente de IA • AI Sales Assistant</span>
              </div>
            </div>
            <button
              onClick={close}
              aria-label="Close chat window"
              className="text-gray-300 hover:text-white text-xl leading-none p-1 rounded transition-colors"
            >
              &times;
            </button>
          </div>

          {/* Messages Container */}
          <div className="salesops-messages flex-1 p-4 overflow-y-auto space-y-3 bg-gray-50 text-sm">
            {status === 'loading' && messages.length === 0 && (
              <div className="flex items-center justify-center h-full text-gray-400">
                <span className="animate-pulse">A iniciar assistente...</span>
              </div>
            )}

            {messages.map((msg) => {
              const isVisitor = msg.role === 'visitor';
              return (
                <div
                  key={msg.id}
                  className={`flex ${isVisitor ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-[85%] rounded-2xl px-4 py-2.5 shadow-sm text-sm ${
                      isVisitor
                        ? 'bg-blue-600 text-white rounded-br-none'
                        : 'bg-white text-gray-800 border border-gray-200 rounded-bl-none'
                    }`}
                  >
                    <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                    {msg.isStreaming && !msg.content && (
                      <span className="inline-block animate-pulse text-gray-400">...</span>
                    )}
                  </div>
                </div>
              );
            })}
            <div ref={messagesEndRef} />
          </div>

          {/* Input Box */}
          <form
            onSubmit={handleSend}
            className="salesops-input-bar p-3 bg-white border-t border-gray-200 flex items-center gap-2"
          >
            <input
              type="text"
              value={inputVal}
              onChange={(e) => setInputVal(e.target.value)}
              placeholder="Escreva a sua mensagem..."
              disabled={status === 'loading'}
              className="flex-1 px-3.5 py-2 text-sm border border-gray-300 rounded-full focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
              data-testid="salesops-chat-input"
            />
            <button
              type="submit"
              disabled={!inputVal.trim() || status === 'streaming'}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white rounded-full text-sm font-medium transition-colors shadow-sm"
              data-testid="salesops-chat-send-btn"
            >
              Enviar
            </button>
          </form>
        </div>
      )}

      {/* Floating Trigger Button */}
      <button
        onClick={toggle}
        aria-label="Open sales chat"
        className="salesops-trigger-btn w-14 h-14 rounded-full text-white shadow-xl flex items-center justify-center hover:scale-105 active:scale-95 transition-transform"
        style={{ backgroundColor: primaryColor }}
        data-testid="salesops-trigger-button"
      >
        {isOpen ? (
          <span className="text-2xl font-bold">&times;</span>
        ) : (
          <svg
            className="w-6 h-6 fill-current"
            viewBox="0 0 24 24"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z" />
          </svg>
        )}
      </button>
    </div>
  );
};
