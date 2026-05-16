import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";

interface Source {
  id: number;
  name: string;
  url: string;
  type: "telegram" | "website" | "rss";
  language: string;
  country: string | null;
  topics: string[] | null;
  enabled: boolean;
  blacklisted: boolean;
}

const TYPE_LABELS: Record<string, string> = {
  telegram: "Telegram",
  website: "Сайт",
  rss: "RSS",
};

export default function SourcesPage() {
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({ name: "", url: "", type: "telegram", language: "en", country: "", topics: "" });
  const [adding, setAdding] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  async function load() {
    setLoading(true);
    try {
      const r = await api.get<{ items: Source[] }>("/v1/sources/");
      setSources(r.data.items);
    } catch {
      setMessage({ type: "error", text: "Не удалось загрузить источники" });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  async function toggle(sourceId: number) {
    try {
      const r = await api.patch<Source>(`/v1/sources/${sourceId}/toggle`);
      setSources((prev) => prev.map((s) => (s.id === sourceId ? { ...s, ...r.data } : s)));
    } catch {
      setMessage({ type: "error", text: "Не удалось переключить источник" });
    }
  }

  async function blacklist(sourceId: number) {
    try {
      const r = await api.patch<Source>(`/v1/sources/${sourceId}/blacklist`);
      setSources((prev) => prev.map((s) => (s.id === sourceId ? { ...s, ...r.data } : s)));
      setMessage({ type: "success", text: "Источник скрыт из ленты" });
    } catch {
      setMessage({ type: "error", text: "Не удалось скрыть источник" });
    }
  }

  async function addSource(e: React.FormEvent) {
    e.preventDefault();
    setAdding(true);
    setMessage(null);
    try {
      await api.post("/v1/sources/", {
        name: form.name,
        url: form.url,
        type: form.type,
        language: form.language || "en",
        country: form.country || null,
        topics: form.topics ? form.topics.split(",").map((t) => t.trim()).filter(Boolean) : null,
      });
      setShowAdd(false);
      setForm({ name: "", url: "", type: "telegram", language: "en", country: "", topics: "" });
      await load();
      setMessage({ type: "success", text: "Источник добавлен" });
    } catch {
      setMessage({ type: "error", text: "Не удалось добавить источник" });
    } finally {
      setAdding(false);
    }
  }

  if (loading) {
    return (
      <div style={s.page}>
        <nav style={s.nav}>
          <Link to="/feed" style={s.navLogo}>News Radar</Link>
        </nav>
        <div style={s.center}>Загрузка...</div>
      </div>
    );
  }

  return (
    <div style={s.page}>
      <nav style={s.nav}>
        <Link to="/feed" style={s.navLogo}>News Radar</Link>
        <div style={s.navLinks}>
          <Link to="/feed" style={s.navLink}>Лента</Link>
          <Link to="/preferences" style={s.navLink}>Темы</Link>
          <Link to="/sources" style={s.navLinkActive}>Источники</Link>
          <Link to="/profile" style={s.navLink}>Профиль</Link>
        </div>
      </nav>

      <div style={s.wrap}>
        <div style={s.headerRow}>
          <h1 style={s.heading}>Источники</h1>
          <button onClick={() => setShowAdd(!showAdd)} style={s.addBtn}>
            {showAdd ? "Отмена" : "+ Добавить"}
          </button>
        </div>
        <p style={s.subtitle}>
          Настройте, из каких источников вы хотите получать новости. Отключённые и скрытые источники не попадут в вашу ленту.
        </p>

        {message && (
          <p style={message.type === "success" ? s.successMsg : s.errorMsg}>
            {message.text}
          </p>
        )}

        {showAdd && (
          <form onSubmit={addSource} style={s.addForm}>
            <input
              style={s.input}
              type="text"
              placeholder="Название (например, Медуза)"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              required
            />
            <input
              style={s.input}
              type="url"
              placeholder="URL (t.me/s/channel или сайт)"
              value={form.url}
              onChange={(e) => setForm({ ...form, url: e.target.value })}
              required
            />
            <select
              style={s.input}
              value={form.type}
              onChange={(e) => setForm({ ...form, type: e.target.value })}
            >
              <option value="telegram">Telegram</option>
              <option value="website">Сайт</option>
              <option value="rss">RSS</option>
            </select>
            <input
              style={s.input}
              type="text"
              placeholder="Язык (en, ru)"
              value={form.language}
              onChange={(e) => setForm({ ...form, language: e.target.value })}
            />
            <input
              style={s.input}
              type="text"
              placeholder="Страна (необязательно)"
              value={form.country}
              onChange={(e) => setForm({ ...form, country: e.target.value })}
            />
            <input
              style={s.input}
              type="text"
              placeholder="Темы через запятую (politics, tech, ...)"
              value={form.topics}
              onChange={(e) => setForm({ ...form, topics: e.target.value })}
            />
            <button type="submit" disabled={adding} style={s.submitBtn}>
              {adding ? "Добавление..." : "Добавить источник"}
            </button>
          </form>
        )}

        <div style={s.list}>
          {sources.map((src) => (
            <div key={src.id} style={s.card}>
              <div style={s.cardHeader}>
                <span style={s.cardName}>{src.name}</span>
                <span style={s.cardType}>{TYPE_LABELS[src.type] ?? src.type}</span>
              </div>
              <div style={s.cardUrl}>{src.url}</div>
              <div style={s.cardMeta}>
                {src.language && <span style={s.metaChip}>{src.language.toUpperCase()}</span>}
                {src.topics && src.topics.map((t) => (
                  <span key={t} style={s.metaChip}>{t}</span>
                ))}
              </div>
              <div style={s.cardActions}>
                <label style={s.toggleLabel}>
                  <input
                    type="checkbox"
                    checked={src.enabled}
                    onChange={() => toggle(src.id)}
                    style={s.toggleInput}
                  />
                  <span style={s.toggleTrack} />
                  <span style={s.toggleText}>{src.enabled ? "Вкл" : "Выкл"}</span>
                </label>
                {!src.blacklisted && (
                  <button onClick={() => blacklist(src.id)} style={s.blacklistBtn}>
                    Скрыть
                  </button>
                )}
                {src.blacklisted && (
                  <span style={s.blacklistedBadge}>Скрыт</span>
                )}
              </div>
            </div>
          ))}
          {sources.length === 0 && (
            <p style={s.empty}>Источников пока нет. Добавьте первый!</p>
          )}
        </div>
      </div>
    </div>
  );
}

const s: Record<string, React.CSSProperties> = {
  page: {
    minHeight: "100dvh",
    background: "var(--bg)",
  },
  nav: {
    position: "sticky",
    top: 0,
    zIndex: 100,
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "0 20px",
    height: 56,
    background: "var(--bg-card)",
    borderBottom: "1px solid var(--border)",
  },
  navLogo: {
    fontSize: 18,
    fontWeight: 700,
    color: "var(--text)",
    textDecoration: "none",
  },
  navLinks: {
    display: "flex",
    gap: 24,
  },
  navLink: {
    color: "var(--text-muted)",
    textDecoration: "none",
    fontSize: 14,
    fontWeight: 500,
  },
  navLinkActive: {
    color: "var(--accent)",
    textDecoration: "none",
    fontSize: 14,
    fontWeight: 600,
  },
  center: {
    minHeight: "100dvh",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    color: "var(--text-muted)",
  },
  wrap: {
    maxWidth: 640,
    margin: "0 auto",
    padding: "32px 16px 60px",
  },
  headerRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 8,
  },
  heading: {
    fontSize: 22,
    fontWeight: 700,
  },
  addBtn: {
    padding: "8px 16px",
    background: "var(--accent)",
    border: "none",
    borderRadius: "var(--radius-sm)",
    color: "#fff",
    fontSize: 14,
    fontWeight: 600,
    cursor: "pointer",
  },
  subtitle: {
    color: "var(--text-muted)",
    fontSize: 14,
    marginBottom: 24,
    lineHeight: 1.6,
  },

  addForm: {
    display: "flex",
    flexDirection: "column",
    gap: 10,
    background: "var(--bg-card)",
    border: "1px solid var(--border)",
    borderRadius: "var(--radius)",
    padding: 16,
    marginBottom: 20,
  },
  input: {
    width: "100%",
    padding: "10px 12px",
    background: "var(--bg-elevated)",
    border: "1px solid var(--border)",
    borderRadius: "var(--radius-sm)",
    color: "var(--text)",
    fontSize: 14,
    outline: "none",
    boxSizing: "border-box" as const,
  },
  submitBtn: {
    width: "100%",
    padding: "10px",
    background: "var(--accent)",
    border: "none",
    borderRadius: "var(--radius-sm)",
    color: "#fff",
    fontSize: 14,
    fontWeight: 600,
    cursor: "pointer",
  },

  list: {
    display: "flex",
    flexDirection: "column",
    gap: 12,
  },
  card: {
    background: "var(--bg-card)",
    border: "1px solid var(--border)",
    borderRadius: "var(--radius)",
    padding: "14px 16px",
    display: "flex",
    flexDirection: "column",
    gap: 6,
  },
  cardHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  cardName: {
    fontSize: 15,
    fontWeight: 600,
  },
  cardType: {
    fontSize: 12,
    color: "var(--text-muted)",
    textTransform: "uppercase",
  },
  cardUrl: {
    fontSize: 13,
    color: "var(--text-muted)",
    wordBreak: "break-all",
  },
  cardMeta: {
    display: "flex",
    flexWrap: "wrap",
    gap: 6,
  },
  metaChip: {
    fontSize: 11,
    fontWeight: 500,
    padding: "2px 8px",
    borderRadius: 20,
    background: "var(--bg-elevated)",
    border: "1px solid var(--border)",
    color: "var(--text-muted)",
  },
  cardActions: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    marginTop: 4,
  },
  toggleLabel: {
    display: "flex",
    alignItems: "center",
    gap: 10,
    cursor: "pointer",
  },
  toggleInput: {
    display: "none",
  },
  toggleTrack: {
    display: "inline-block",
    width: 40,
    height: 22,
    borderRadius: 11,
    background: "var(--border)",
    position: "relative",
    transition: "background 0.2s",
  },
  toggleText: {
    fontSize: 13,
    color: "var(--text-muted)",
  },
  blacklistBtn: {
    background: "transparent",
    border: "1px solid var(--border)",
    borderRadius: "var(--radius-sm)",
    padding: "4px 12px",
    color: "var(--text-muted)",
    fontSize: 13,
    cursor: "pointer",
  },
  blacklistedBadge: {
    fontSize: 12,
    color: "var(--danger)",
    fontWeight: 500,
  },
  empty: {
    textAlign: "center",
    color: "var(--text-muted)",
    fontSize: 14,
    padding: 40,
  },
  successMsg: {
    marginBottom: 12,
    textAlign: "center",
    color: "var(--success)",
    fontSize: 14,
  },
  errorMsg: {
    marginBottom: 12,
    textAlign: "center",
    color: "var(--danger)",
    fontSize: 14,
  },
};
