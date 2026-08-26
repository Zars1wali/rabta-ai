import { useState, useCallback, useRef } from 'react';
import type { ChatMessage, WidgetConfig, ChatStatus } from './types.js';
import type { FunnelStage, AgentEvent } from '@salesops/types';

export interface UseSalesOpsChatReturn {
  messages: ChatMessage[];
  status: ChatStatus;
  sessionId: string | null;
  stage: FunnelStage;
  isOpen: boolean;
  error: string | null;
  startSession: (locale?: string) => Promise<void>;
  sendMessage: (content: string) => Promise<void>;
  toggle: () => void;
  open: () => void;
  close: () => void;
}

export function useSalesOpsChat(config: WidgetConfig = {}): UseSalesOpsChatReturn {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [status, setStatus] = useState<ChatStatus>('idle');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [stage, setStage] = useState<FunnelStage>('greet');
  const [isOpen, setIsOpen] = useState<boolean>(config.initialOpen ?? false);
  const [error, setError] = useState<string | null>(null);

  const apiBase = config.apiBaseUrl || '/api/salesops';
  const abortControllerRef = useRef<AbortController | null>(null);

  const startSession = useCallback(
    async (localeOverride?: string) => {
      setStatus('loading');
      setError(null);

      try {
        const res = await fetch(`${apiBase}/session`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ locale: localeOverride || config.locale || 'pt-PT' })
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.error || `Failed to start session (${res.status})`);
        }

        const data = await res.json();
        setSessionId(data.sessionId);
        setStage(data.stage || 'greet');

        const initialGreeting: ChatMessage = {
          id: `greet_${data.sessionId}`,
          role: 'agent',
          content: data.greeting,
          createdAt: new Date().toISOString()
        };

        setMessages([initialGreeting]);
        setStatus('idle');
      } catch (err: unknown) {
        const errorMsg = (err as Error).message;
        setError(errorMsg);
        setStatus('error');
      }
    },
    [apiBase, config.locale]
  );

  const sendMessage = useCallback(
    async (content: string) => {
      const trimmed = content.trim();
      if (!trimmed || status === 'streaming' || status === 'loading') return;

      // Ensure session exists
      const currentSessionId = sessionId;
      if (!currentSessionId) {
        await startSession();
      }

      const userMsgId = `user_${crypto.randomUUID().slice(0, 8)}`;
      const userMsg: ChatMessage = {
        id: userMsgId,
        role: 'visitor',
        content: trimmed,
        createdAt: new Date().toISOString()
      };

      const agentMsgId = `agent_${crypto.randomUUID().slice(0, 8)}`;
      const placeholderAgentMsg: ChatMessage = {
        id: agentMsgId,
        role: 'agent',
        content: '',
        createdAt: new Date().toISOString(),
        isStreaming: true
      };

      setMessages((prev) => [...prev, userMsg, placeholderAgentMsg]);
      setStatus('streaming');
      setError(null);

      try {
        abortControllerRef.current = new AbortController();

        const res = await fetch(`${apiBase}/chat`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            sessionId: currentSessionId || sessionId,
            message: { content: trimmed }
          }),
          signal: abortControllerRef.current.signal
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.error || `Chat error (${res.status})`);
        }

        if (!res.body) {
          throw new Error('ReadableStream not supported in response');
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n\n');
          buffer = lines.pop() || '';

          for (const block of lines) {
            if (!block.trim()) continue;

            const blockLines = block.split('\n');
            let eventType = 'message';
            let dataStr = '';

            for (const line of blockLines) {
              if (line.startsWith('event: ')) {
                eventType = line.slice(7).trim();
              } else if (line.startsWith('data: ')) {
                dataStr = line.slice(6).trim();
              }
            }

            if (!dataStr) continue;

            try {
              const parsed = JSON.parse(dataStr);

              if (eventType === 'token' && parsed.text) {
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === agentMsgId
                      ? { ...msg, content: msg.content + parsed.text }
                      : msg
                  )
                );
              } else if (eventType === 'event') {
                config.onEvent?.(parsed as AgentEvent);
              } else if (eventType === 'done') {
                if (parsed.stage) {
                  setStage(parsed.stage);
                  config.onStageChange?.(parsed.stage);
                }
              }
            } catch {
              // Ignore unparseable data chunk
            }
          }
        }

        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === agentMsgId ? { ...msg, isStreaming: false } : msg
          )
        );
        setStatus('idle');
      } catch (err: unknown) {
        const errorMsg = (err as Error).message;
        setError(errorMsg);
        setStatus('error');
        setMessages((prev) =>
          prev.map((msg) =>
            msg.id === agentMsgId
              ? {
                  ...msg,
                  content:
                    msg.content ||
                    'Desculpe, ocorreu uma interrupção na ligação. Por favor tente novamente.',
                  isStreaming: false
                }
              : msg
          )
        );
      }
    },
    [apiBase, sessionId, startSession, status, config]
  );

  const toggle = useCallback(() => setIsOpen((prev) => !prev), []);
  const open = useCallback(() => setIsOpen(true), []);
  const close = useCallback(() => setIsOpen(false), []);

  return {
    messages,
    status,
    sessionId,
    stage,
    isOpen,
    error,
    startSession,
    sendMessage,
    toggle,
    open,
    close
  };
}
