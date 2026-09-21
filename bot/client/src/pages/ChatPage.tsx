import { useEffect, useRef, useState, type FormEvent } from 'react';

interface ChatMessage {
  id: number;
  role: 'user' | 'assistant';
  content: string;
  created_at: number;
}

const POLL_INTERVAL_MS = 8000;

export const ChatPage = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const fetchMessages = async () => {
    try {
      const res = await fetch('/api/chat/messages');
      if (!res.ok) throw new Error(String(res.status));
      setMessages(await res.json());
      setError(null);
    } catch {
      setError('Could not load chat.');
    }
  };

  // Poll while the tab is actually visible -- no point hammering the backend
  // (and burning tokens re-checking Hermes task status) for a hidden tab.
  useEffect(() => {
    fetchMessages();

    let interval: ReturnType<typeof setInterval> | undefined;
    const startPolling = () => {
      if (interval) return;
      interval = setInterval(fetchMessages, POLL_INTERVAL_MS);
    };
    const stopPolling = () => {
      clearInterval(interval);
      interval = undefined;
    };
    const handleVisibility = () => {
      if (document.visibilityState === 'visible') {
        fetchMessages();
        startPolling();
      } else {
        stopPolling();
      }
    };

    startPolling();
    document.addEventListener('visibilitychange', handleVisibility);
    return () => {
      stopPolling();
      document.removeEventListener('visibilitychange', handleVisibility);
    };
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async (e: FormEvent) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || sending) return;
    setInput('');
    setSending(true);
    try {
      const res = await fetch('/api/chat/messages', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
      });
      if (!res.ok) throw new Error(String(res.status));
      setMessages(await res.json());
      setError(null);
    } catch {
      setError('Message failed to send.');
    } finally {
      setSending(false);
    }
  };

  const handleClear = async () => {
    if (!window.confirm('Clear the whole conversation?')) return;
    try {
      const res = await fetch('/api/chat/clear', { method: 'POST' });
      if (!res.ok) throw new Error(String(res.status));
      setMessages([]);
      setError(null);
    } catch {
      setError('Could not clear chat.');
    }
  };

  return (
    <div className="w-full max-w-2xl mx-auto flex flex-col h-full px-3 sm:px-6 py-4 sm:py-6">
      <div className="flex items-center justify-between mb-4 shrink-0">
        <h1 className="text-lg sm:text-xl font-semibold text-foreground">Chat</h1>
        <button
          onClick={handleClear}
          className="text-xs font-medium px-2.5 py-1.5 rounded-md border border-border text-muted-foreground hover:text-foreground hover:border-foreground/40 transition-colors"
        >
          Clear conversation
        </button>
      </div>

      {error && <p className="text-destructive text-sm mb-3 shrink-0">{error}</p>}

      <div className="flex-1 min-h-0 overflow-y-auto flex flex-col gap-2 pb-4">
        {messages.length === 0 && (
          <p className="text-sm text-muted-foreground">No messages yet — say something.</p>
        )}
        {messages.map((m) => (
          <div
            key={m.id}
            className={`max-w-[85%] rounded-md px-3 py-2 text-sm whitespace-pre-wrap ${
              m.role === 'user'
                ? 'self-end bg-primary text-primary-foreground'
                : 'self-start bg-card border border-border text-foreground'
            }`}
          >
            {m.content}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      <form onSubmit={handleSend} className="flex gap-2 border-t border-border pt-4 shrink-0">
        <input
          type="text"
          placeholder="Message the agent…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          className="flex-1 bg-card border border-border rounded-md px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground"
        />
        <button
          type="submit"
          disabled={sending || !input.trim()}
          className="bg-primary text-primary-foreground rounded-md px-4 py-2 text-sm font-medium disabled:opacity-50"
        >
          Send
        </button>
      </form>
    </div>
  );
};
