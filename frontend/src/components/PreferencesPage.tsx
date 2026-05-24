import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { PreferencesResponse } from "../types";

const VALID_TOPICS = [
  "politics", "military", "technology", "health",
  "science", "business", "sports", "culture", "environment",
] as const;

const TOPIC_LABELS: Record<string, string> = {
  politics: "Политика",
  military: "Военное дело",
  technology: "Технологии",
  health: "Здоровье",
  science: "Наука",
  business: "Бизнес",
  sports: "Спорт",
  culture: "Культура",
  environment: "Экология",
};

export default function PreferencesPage() {
  const [prefs, setPrefs] = useState<Record<string, number>>(() =>
    Object.fromEntries(VALID_TOPICS.map((t) => [t, 0]))
  );
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  useEffect(() => {
    api
      .get<PreferencesResponse>("/v1/preferences/")
      .then((r) => {
        const map: Record<string, number> = Object.fromEntries(
          VALID_TOPICS.map((t) => [t, 0])
        );
        for (const p of r.data.preferences) {
          if (VALID_TOPICS.includes(p.topic as any)) {
            map[p.topic] = p.weight;
          }
        }
        setPrefs(map);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  async function save() {
    setSaving(true);
    setMessage(null);
    const body = {
      preferences: VALID_TOPICS.map((topic) => ({
        topic,
        weight: prefs[topic],
      })),
    };
    try {
      const r = await api.put<PreferencesResponse>("/v1/preferences/", body);
      const map: Record<string, number> = Object.fromEntries(
        VALID_TOPICS.map((t) => [t, 0])
      );
      for (const p of r.data.preferences) {
        if (VALID_TOPICS.includes(p.topic as any)) {
          map[p.topic] = p.weight;
        }
      }
      setPrefs(map);
      setMessage({ type: "success", text: "Предпочтения сохранены" });
    } catch {
      setMessage({ type: "error", text: "Не удалось сохранить" });
    } finally {
      setSaving(false);
    }
  }

  function setWeight(topic: string, value: number) {
    setPrefs((prev) => ({ ...prev, [topic]: value }));
  }

  return (
    <div style={s.page}>
      <nav style={s.nav}>
        <Link to="/feed" style={s.navLogo}>News Radar</Link>
        <div style={s.navLinks}>
          <Link to="/feed" style={s.navLink}>Лента</Link>
          <Link to="/preferences" style={s.navLinkActive}>Темы</Link>
          <Link to="/sources" style={s.navLink}>Источники</Link>
          <Link to="/profile" style={s.navLink}>Профиль</Link>
        </div>
      </nav>
      <div style={{ ...s.wrap, opacity: loading ? 0 : 1, transition: "opacity 0.2s" }}>
        <h1 style={s.heading}>Предпочтения</h1>
      <p style={s.subtitle}>
        Настройте вес каждой темы — новости с более высоким весом будут чаще попадать в вашу ленту.
      </p>

      <div style={s.list}>
        {VALID_TOPICS.map((topic) => (
          <label key={topic} style={s.row}>
            <span style={s.label}>
              {TOPIC_LABELS[topic]}
              <span style={s.value}>{(prefs[topic] * 100).toFixed(0)}%</span>
            </span>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={prefs[topic]}
              onChange={(e) => setWeight(topic, parseFloat(e.target.value))}
              style={s.slider}
            />
          </label>
        ))}
      </div>

      {message && (
        <p style={message.type === "success" ? s.successMsg : s.errorMsg}>
          {message.text}
        </p>
      )}

      <button onClick={save} disabled={saving} style={s.saveBtn}>
        {saving ? "Сохранение..." : "Сохранить"}
      </button>
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
    maxWidth: 560,
    margin: "0 auto",
    padding: "32px 16px 60px",
  },
  heading: {
    fontSize: 22,
    fontWeight: 700,
    marginBottom: 8,
  },
  subtitle: {
    color: "var(--text-muted)",
    fontSize: 14,
    marginBottom: 28,
    lineHeight: 1.6,
  },
  list: {
    display: "flex",
    flexDirection: "column",
    gap: 20,
  },
  row: {
    display: "flex",
    flexDirection: "column",
    gap: 6,
    background: "var(--bg-card)",
    border: "1px solid var(--border)",
    borderRadius: "var(--radius)",
    padding: "14px 16px",
  },
  label: {
    display: "flex",
    justifyContent: "space-between",
    fontSize: 15,
    fontWeight: 500,
  },
  value: {
    color: "var(--accent)",
    fontWeight: 600,
    fontSize: 14,
  },
  slider: {
    width: "100%",
    accentColor: "var(--accent)",
    height: 6,
  },
  saveBtn: {
    marginTop: 28,
    width: "100%",
    padding: "12px",
    background: "var(--accent)",
    border: "none",
    borderRadius: "var(--radius-sm)",
    color: "#fff",
    fontSize: 15,
    fontWeight: 600,
    cursor: "pointer",
  },
  successMsg: {
    marginTop: 16,
    textAlign: "center",
    color: "var(--success)",
    fontSize: 14,
  },
  errorMsg: {
    marginTop: 16,
    textAlign: "center",
    color: "var(--danger)",
    fontSize: 14,
  },
};
