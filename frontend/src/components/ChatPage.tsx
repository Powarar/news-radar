import { useEffect, useRef, useState, type CSSProperties } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import NavBar from "./NavBar";

interface Message {
  sender: "user" | "ai";
  text: string;
  sources_count?: number;
  status?: string;
}

const DAYS_OPTIONS = [
  { label: "1 день", value: 1 },
  { label: "3 дня", value: 3 },
  { label: "7 дней", value: 7 },
];

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      sender: "ai",
      text: "Привет! Я твой AI-новостной аналитик. Задай мне любой вопрос по свежим новостям (например, 'Что там про новые гаджеты от Apple?'), и я сделаю краткую выжимку по материалам из твоей ленты.",
    },
  ]);
  const [input, setInput] = useState("");
  const [days, setDays] = useState(3);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const chatEndRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  // Redirect guest user to login page on mount
  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      navigate("/login");
    }
  }, [navigate]);

  // Scroll to bottom on new messages
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    const query = input.trim();
    if (!query || loading) return;

    setInput("");
    setError("");
    setMessages((prev) => [...prev, { sender: "user", text: query }]);
    setLoading(true);

    try {
      const { data } = await api.post("/v1/news/chat", {
        query,
        days,
      });

      setMessages((prev) => [
        ...prev,
        {
          sender: "ai",
          text: data.answer,
          sources_count: data.sources_count,
          status: data.status,
        },
      ]);
    } catch (err: any) {
      console.error(err);
      if (err.response?.status === 401 || err.response?.status === 403) {
        navigate("/login");
        return;
      }
      if (err.response?.status === 429) {
        setError("Дневной лимит — 3 запроса. Попробуйте снова завтра.");
        return;
      }
      setError("Не удалось получить ответ. Попробуйте еще раз.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={s.page}>
      <NavBar />
      <div className="page-enter" style={s.wrap}>
        <div style={s.header}>
          <h1 style={s.heading}>AI Аналитик</h1>
          <p style={s.subtitle}>Задавайте вопросы по новостям за указанный период</p>
        </div>

        {/* Days selector */}
        <div style={s.daysSelector}>
          <span style={s.daysLabel}>Искать за последние:</span>
          <div style={s.segmented}>
            {DAYS_OPTIONS.map((opt) => {
              const active = days === opt.value;
              return (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => setDays(opt.value)}
                  style={{
                    ...s.segBtn,
                    ...(active ? s.segBtnActive : {}),
                  }}
                >
                  {opt.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Chat area */}
        <div className="glass-panel" style={s.chatBox}>
          <div style={s.messageList}>
            {messages.map((msg, i) => {
              const isAi = msg.sender === "ai";
              return (
                <div
                  key={i}
                  style={{
                    ...s.messageRow,
                    justifyContent: isAi ? "flex-start" : "flex-end",
                  }}
                >
                  <div
                    style={{
                      ...s.bubble,
                      ...(isAi ? s.aiBubble : s.userBubble),
                    }}
                  >
                    <div style={s.bubbleText}>{msg.text}</div>
                    {isAi && msg.sources_count !== undefined && msg.sources_count > 0 && (
                      <div style={s.sourcesCount}>
                        Использовано источников: {msg.sources_count}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}

            {loading && (
              <div style={s.messageRow}>
                <div style={{ ...s.bubble, ...s.aiBubble, ...s.loadingBubble }}>
                  <span className="skeleton" style={s.dotLoader} />
                  <span className="skeleton" style={{ ...s.dotLoader, animationDelay: "0.2s" }} />
                  <span className="skeleton" style={{ ...s.dotLoader, animationDelay: "0.4s" }} />
                </div>
              </div>
            )}

            {error && <div style={s.errorAlert}>{error}</div>}

            <div ref={chatEndRef} />
          </div>

          {/* Form */}
          <form onSubmit={handleSend} style={s.inputForm}>
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Спросите о чем-нибудь..."
              disabled={loading}
              style={s.inputField}
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              style={{
                ...s.sendBtn,
                ...(!input.trim() || loading ? { opacity: 0.5, cursor: "default" } : {}),
              }}
            >
              {loading ? "…" : "Отправить"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

const s: Record<string, CSSProperties> = {
  page: { minHeight: "100dvh", background: "var(--bg)" },
  wrap: {
    maxWidth: 680,
    margin: "0 auto",
    padding: "32px 16px 80px",
    display: "flex",
    flexDirection: "column",
    height: "calc(100dvh - 54px)",
  },
  header: {
    marginBottom: 20,
    flexShrink: 0,
  },
  heading: {
    fontSize: 22,
    fontWeight: 700,
    letterSpacing: "-0.02em",
    marginBottom: 6,
  },
  subtitle: {
    color: "var(--text-muted)",
    fontSize: 14,
    lineHeight: 1.5,
  },
  daysSelector: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 16,
    flexShrink: 0,
    gap: 12,
  },
  daysLabel: {
    fontSize: 13,
    color: "var(--text-muted)",
    fontWeight: 500,
  },
  segmented: {
    display: "flex",
    gap: 5,
    background: "rgba(255,255,255,0.03)",
    padding: 3,
    borderRadius: "var(--radius-sm)",
    border: "1px solid var(--border)",
  },
  segBtn: {
    padding: "5px 12px",
    background: "transparent",
    border: "none",
    borderRadius: "calc(var(--radius-sm) - 3px)",
    color: "var(--text-muted)",
    fontSize: 12,
    fontWeight: 600,
    cursor: "pointer",
    transition: "background 150ms ease, color 150ms ease",
  },
  segBtnActive: {
    background: "var(--bg-elevated)",
    color: "var(--text)",
  },
  chatBox: {
    flex: 1,
    display: "flex",
    flexDirection: "column",
    minHeight: 0, // critical for nested flex scroll
    background: "linear-gradient(135deg, rgba(255,255,255,0.04), rgba(255,255,255,0.01))",
  },
  messageList: {
    flex: 1,
    overflowY: "auto",
    padding: "16px 20px",
    display: "flex",
    flexDirection: "column",
    gap: 14,
  },
  messageRow: {
    display: "flex",
    width: "100%",
  },
  bubble: {
    maxWidth: "80%",
    padding: "12px 16px",
    borderRadius: "var(--radius-sm)",
    fontSize: 14,
    lineHeight: 1.5,
    whiteSpace: "pre-line",
  },
  aiBubble: {
    background: "var(--bg-card)",
    border: "1px solid var(--border)",
    color: "var(--text)",
    borderTopLeftRadius: 4,
  },
  userBubble: {
    background: "var(--accent-dim)",
    border: "1px solid rgba(185,220,255,0.25)",
    color: "var(--text)",
    borderTopRightRadius: 4,
  },
  bubbleText: {
    wordBreak: "break-word",
  },
  sourcesCount: {
    marginTop: 8,
    fontSize: 11,
    color: "var(--text-subtle)",
    fontWeight: 500,
    borderTop: "1px solid var(--border)",
    paddingTop: 6,
  },
  loadingBubble: {
    display: "flex",
    gap: 4,
    alignItems: "center",
    padding: "14px 18px",
  },
  dotLoader: {
    width: 6,
    height: 6,
    borderRadius: "50%",
    background: "var(--text-muted)",
    display: "inline-block",
  },
  errorAlert: {
    padding: "10px 14px",
    background: "var(--danger-dim)",
    border: "1px solid var(--danger)",
    borderRadius: "var(--radius-sm)",
    color: "var(--danger)",
    fontSize: 13,
    textAlign: "center",
    margin: "10px 0",
  },
  inputForm: {
    display: "flex",
    gap: 8,
    padding: "12px 16px",
    borderTop: "1px solid var(--border)",
    background: "rgba(10,13,18,0.3)",
    flexShrink: 0,
  },
  inputField: {
    flex: 1,
    background: "var(--bg-card)",
    border: "1px solid var(--border)",
    borderRadius: "var(--radius-sm)",
    padding: "10px 16px",
    color: "var(--text)",
    fontSize: 14,
    outline: "none",
    transition: "border-color 150ms ease",
  },
  sendBtn: {
    background: "var(--accent)",
    color: "#080b10",
    border: "none",
    borderRadius: "var(--radius-sm)",
    padding: "0 18px",
    fontSize: 14,
    fontWeight: 600,
    cursor: "pointer",
    transition: "opacity 150ms ease",
  },
};
