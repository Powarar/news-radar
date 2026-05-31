import type { CSSProperties } from "react";
import { useEffect, useState } from "react";
import { api } from "../api/client";
import NavBar from "./NavBar";

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

const TYPE_COLORS: Record<string, string> = {
  telegram: "#2aabee",
  website: "#5b8dee",
  rss: "#e79b47",
};

// ─── Toggle ───────────────────────────────────────────────────────────────────

function Toggle({ checked, onChange }: { checked: boolean; onChange: () => void }) {
  return (
    <button
      role="switch"
      aria-checked={checked}
      onClick={onChange}
      style={{
        width: 38,
        height: 22,
        borderRadius: 11,
        background: checked ? "var(--success)" : "var(--bg-elevated)",
        border: `1px solid ${checked ? "var(--success)" : "var(--border)"}`,
        position: "relative",
        cursor: "pointer",
        transition: "background 200ms ease, border-color 200ms ease",
        padding: 0,
        flexShrink: 0,
      }}
    >
      <span
        style={{
          position: "absolute",
          top: 2,
          left: checked ? 17 : 2,
          width: 16,
          height: 16,
          borderRadius: "50%",
          background: "#fff",
          transition: "left 200ms var(--ease)",
        }}
      />
    </button>
  );
}

// ─── Skeleton ─────────────────────────────────────────────────────────────────

function SkeletonCard() {
  return (
    <div style={s.card}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div className="skeleton" style={{ width: 140, height: 15 }} />
        <div className="skeleton" style={{ width: 52, height: 20, borderRadius: 20 }} />
      </div>
      <div className="skeleton" style={{ width: "80%", height: 12, marginTop: 2 }} />
      <div style={{ display: "flex", gap: 6, marginTop: 4 }}>
        <div className="skeleton" style={{ width: 32, height: 20, borderRadius: 20 }} />
        <div className="skeleton" style={{ width: 60, height: 20, borderRadius: 20 }} />
      </div>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function SourcesPage() {
  const [sources, setSources] = useState<Source[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [form, setForm] = useState({ name: "", url: "", type: "telegram", language: "ru", country: "", topics: "" });
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
      flash("success", "Источник скрыт из ленты");
    } catch {
      flash("error", "Не удалось скрыть источник");
    }
  }

  function flash(type: "success" | "error", text: string) {
    setMessage({ type, text });
    setTimeout(() => setMessage(null), 3000);
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
        language: form.language || "ru",
        country: form.country || null,
        topics: form.topics ? form.topics.split(",").map((t) => t.trim()).filter(Boolean) : null,
      });
      setShowAdd(false);
      setForm({ name: "", url: "", type: "telegram", language: "ru", country: "", topics: "" });
      await load();
      flash("success", "Источник добавлен");
    } catch {
      flash("error", "Не удалось добавить источник");
    } finally {
      setAdding(false);
    }
  }

  return (
    <div style={s.page}>
      <NavBar />

      <div style={s.wrap}>
        <div style={s.headerRow}>
          <h1 style={s.heading}>Источники</h1>
          <button onClick={() => setShowAdd(!showAdd)} style={showAdd ? s.cancelBtn : s.addBtn}>
            {showAdd ? "Отмена" : "+ Добавить"}
          </button>
        </div>
        <p style={s.subtitle}>
          Настройте, из каких источников получать новости. Отключённые и скрытые не попадут в ленту.
        </p>

        {message && (
          <div style={message.type === "success" ? s.successMsg : s.errorMsg}>
            {message.type === "success" ? "✓ " : "✕ "}{message.text}
          </div>
        )}

        {showAdd && (
          <form onSubmit={addSource} style={s.addForm}>
            <input style={s.input} type="text" placeholder="Название (например, Медуза)"
              value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
            <input style={s.input} type="url" placeholder="URL (t.me/s/channel или сайт)"
              value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} required />
            <select style={s.input} value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>
              <option value="telegram">Telegram</option>
              <option value="website">Сайт</option>
              <option value="rss">RSS</option>
            </select>
            <div style={{ display: "flex", gap: 8 }}>
              <input style={{ ...s.input, flex: 1 }} type="text" placeholder="Язык (ru, en)"
                value={form.language} onChange={(e) => setForm({ ...form, language: e.target.value })} />
              <input style={{ ...s.input, flex: 1 }} type="text" placeholder="Страна (необязательно)"
                value={form.country} onChange={(e) => setForm({ ...form, country: e.target.value })} />
            </div>
            <input style={s.input} type="text" placeholder="Темы через запятую (politics, technology, ...)"
              value={form.topics} onChange={(e) => setForm({ ...form, topics: e.target.value })} />
            <button type="submit" disabled={adding} style={s.submitBtn}>
              {adding ? "Добавление…" : "Добавить источник"}
            </button>
          </form>
        )}

        <div style={s.list}>
          {loading
            ? Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)
            : sources.length === 0
              ? (
                <div style={s.empty}>
                  <div style={{ fontSize: 36, marginBottom: 12 }}>📡</div>
                  <p style={{ fontWeight: 600, marginBottom: 4 }}>Источников пока нет</p>
                  <p style={{ color: "var(--text-muted)", fontSize: 13 }}>Добавьте первый источник новостей</p>
                </div>
              )
              : sources.map((src) => (
                <div key={src.id} style={{ ...s.card, ...(src.blacklisted ? s.cardBlacklisted : {}) }}>
                  <div style={s.cardHeader}>
                    <span style={s.cardName}>{src.name}</span>
                    <span style={{
                      ...s.typeBadge,
                      color: TYPE_COLORS[src.type] ?? "var(--text-muted)",
                      borderColor: TYPE_COLORS[src.type] ?? "var(--border)",
                    }}>
                      {TYPE_LABELS[src.type] ?? src.type}
                    </span>
                  </div>

                  <div style={s.cardUrl}>{src.url}</div>

                  {((src.topics && src.topics.length > 0) || src.language) && (
                    <div style={s.cardMeta}>
                      {src.language && <span style={s.metaChip}>{src.language.toUpperCase()}</span>}
                      {src.topics?.map((t) => <span key={t} style={s.metaChip}>{t}</span>)}
                    </div>
                  )}

                  <div style={s.cardActions}>
                    <div style={s.toggleRow}>
                      <Toggle checked={src.enabled} onChange={() => toggle(src.id)} />
                      <span style={{ fontSize: 13, color: src.enabled ? "var(--text)" : "var(--text-subtle)" }}>
                        {src.enabled ? "Активен" : "Отключён"}
                      </span>
                    </div>
                    <button
                      onClick={() => blacklist(src.id)}
                      style={src.blacklisted ? s.unblacklistBtn : s.blacklistBtn}
                    >
                      {src.blacklisted ? "Показать" : "Скрыть"}
                    </button>
                  </div>
                </div>
              ))}
        </div>
      </div>
    </div>
  );
}

const s: Record<string, CSSProperties> = {
  page: { minHeight: "100dvh", background: "var(--bg)" },
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
    letterSpacing: "-0.02em",
  },
  addBtn: {
    padding: "8px 16px",
    background: "var(--accent)",
    border: "none",
    borderRadius: "var(--radius-sm)",
    color: "#fff",
    fontSize: 13,
    fontWeight: 600,
    cursor: "pointer",
  },
  cancelBtn: {
    padding: "8px 16px",
    background: "transparent",
    border: "1px solid var(--border)",
    borderRadius: "var(--radius-sm)",
    color: "var(--text-muted)",
    fontSize: 13,
    fontWeight: 500,
    cursor: "pointer",
  },
  subtitle: {
    color: "var(--text-muted)",
    fontSize: 14,
    marginBottom: 24,
    lineHeight: 1.6,
  },
  successMsg: {
    marginBottom: 16,
    padding: "10px 14px",
    background: "var(--success-dim)",
    border: "1px solid var(--success)",
    borderRadius: "var(--radius-sm)",
    color: "var(--success)",
    fontSize: 13,
    fontWeight: 500,
  },
  errorMsg: {
    marginBottom: 16,
    padding: "10px 14px",
    background: "var(--danger-dim)",
    border: "1px solid var(--danger)",
    borderRadius: "var(--radius-sm)",
    color: "var(--danger)",
    fontSize: 13,
    fontWeight: 500,
  },
  addForm: {
    display: "flex",
    flexDirection: "column",
    gap: 8,
    background: "var(--bg-card)",
    border: "1px solid var(--border)",
    borderRadius: "var(--radius)",
    padding: "16px",
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
    boxSizing: "border-box",
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
    gap: 10,
  },
  card: {
    background: "var(--bg-card)",
    border: "1px solid var(--border)",
    borderRadius: "var(--radius)",
    padding: "14px 16px",
    display: "flex",
    flexDirection: "column",
    gap: 8,
    transition: "border-color 150ms ease",
  },
  cardBlacklisted: {
    opacity: 0.5,
  },
  cardHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  cardName: {
    fontSize: 15,
    fontWeight: 600,
    color: "var(--text)",
  },
  typeBadge: {
    fontSize: 11,
    fontWeight: 600,
    padding: "2px 8px",
    borderRadius: 20,
    border: "1px solid",
    background: "transparent",
    letterSpacing: "0.04em",
  },
  cardUrl: {
    fontSize: 12,
    color: "var(--text-subtle)",
    wordBreak: "break-all",
  },
  cardMeta: {
    display: "flex",
    flexWrap: "wrap",
    gap: 5,
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
  toggleRow: {
    display: "flex",
    alignItems: "center",
    gap: 10,
  },
  blacklistBtn: {
    background: "transparent",
    border: "1px solid var(--border)",
    borderRadius: "var(--radius-sm)",
    padding: "4px 12px",
    color: "var(--text-muted)",
    fontSize: 12,
    cursor: "pointer",
    transition: "color 150ms ease, border-color 150ms ease",
  },
  unblacklistBtn: {
    background: "var(--danger-dim)",
    border: "1px solid var(--danger)",
    borderRadius: "var(--radius-sm)",
    padding: "4px 12px",
    color: "var(--danger)",
    fontSize: 12,
    cursor: "pointer",
  },
  empty: {
    textAlign: "center",
    padding: "60px 20px",
    color: "var(--text-muted)",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
  },
};
