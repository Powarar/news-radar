import { useEffect, useRef, useState, type CSSProperties } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { PreferencesResponse } from "../types";
import NavBar from "./NavBar";
import { VALID_TOPICS, TOPIC_LABELS, TOPIC_COLORS } from "../constants";

// 4 survey levels → weight values
const LEVELS = [
  { label: "Не читаю", value: 0 },
  { label: "Иногда",   value: 0.33 },
  { label: "Часто",    value: 0.67 },
  { label: "Всегда",   value: 1.0 },
];

function weightToLevel(w: number): number {
  if (w < 0.1)  return 0;
  if (w < 0.45) return 1;
  if (w < 0.8)  return 2;
  return 3;
}

// ─── Skeleton ─────────────────────────────────────────────────────────────────

function SkeletonRow() {
  return (
    <div style={s.card}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
        <div className="skeleton" style={{ width: 8, height: 8, borderRadius: "50%" }} />
        <div className="skeleton" style={{ width: 110, height: 15 }} />
      </div>
      <div style={{ display: "flex", gap: 6 }}>
        {[70, 56, 52, 72].map((w, i) => (
          <div key={i} className="skeleton" style={{ flex: 1, height: 34, borderRadius: "var(--radius-sm)" }} />
        ))}
      </div>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function PreferencesPage() {
  // Store selected level index (0–3) per topic
  const [levels, setLevels] = useState<Record<string, number>>(() =>
    Object.fromEntries(VALID_TOPICS.map((t) => [t, 0]))
  );
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState(false);
  const savedTimer = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => {
    api
      .get<PreferencesResponse>("/v1/preferences/")
      .then((r) => {
        const map = Object.fromEntries(VALID_TOPICS.map((t) => [t, 0]));
        for (const p of r.data.preferences) {
          if ((VALID_TOPICS as readonly string[]).includes(p.topic)) {
            map[p.topic] = weightToLevel(p.weight);
          }
        }
        setLevels(map);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
    return () => clearTimeout(savedTimer.current);
  }, []);

  async function save() {
    setSaving(true);
    setSaved(false);
    setError(false);
    try {
      await api.put("/v1/preferences/", {
        preferences: VALID_TOPICS.map((topic) => ({
          topic,
          weight: LEVELS[levels[topic]].value,
        })),
      });
      setSaved(true);
      clearTimeout(savedTimer.current);
      savedTimer.current = setTimeout(() => setSaved(false), 3000);
    } catch {
      setError(true);
    } finally {
      setSaving(false);
    }
  }

  const anySet = Object.values(levels).some((l) => l > 0);

  return (
    <div style={s.page}>
      <NavBar />
      <div className="page-enter" style={s.wrap}>
        <div style={s.header}>
          <h1 style={s.heading}>Настройте ленту</h1>
          <p style={s.subtitle}>Как часто вы хотите видеть каждую тему?</p>
        </div>

        <div style={s.list}>
          {loading
            ? VALID_TOPICS.map((t) => <SkeletonRow key={t} />)
            : VALID_TOPICS.map((topic) => {
                const color = TOPIC_COLORS[topic];
                const current = levels[topic];
                return (
                  <div key={topic} style={s.card}>
                    <div style={s.cardLabel}>
                      <span style={{ ...s.dot, background: color }} />
                      <span style={s.topicName}>{TOPIC_LABELS[topic]}</span>
                      {current > 0 && (
                        <span style={{ ...s.levelBadge, color, borderColor: color + "40", background: color + "18" }}>
                          {LEVELS[current].label}
                        </span>
                      )}
                    </div>
                    <div style={s.segmented}>
                      {LEVELS.map((level, i) => {
                        const active = current === i;
                        return (
                          <button
                            key={i}
                            onClick={() => setLevels((prev) => ({ ...prev, [topic]: i }))}
                            style={{
                              ...s.segBtn,
                              ...(active ? {
                                background: color,
                                borderColor: color,
                                color: "#fff",
                                fontWeight: 600,
                              } : {}),
                            }}
                          >
                            {level.label}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
        </div>

        <div style={s.footer}>
          {saved && <span style={s.savedMsg}>✓ Сохранено</span>}
          {error && <span style={s.errorMsg}>✕ Не удалось сохранить</span>}
          <button
            onClick={save}
            disabled={saving || loading}
            style={{
              ...s.saveBtn,
              ...(saving ? { opacity: 0.6 } : {}),
            }}
          >
            {saving ? "Сохранение…" : "Сохранить"}
          </button>
        </div>
      </div>
    </div>
  );
}

const s: Record<string, CSSProperties> = {
  page: { minHeight: "100dvh", background: "var(--bg)" },
  wrap: {
    maxWidth: 580,
    margin: "0 auto",
    padding: "32px 16px 80px",
  },
  header: {
    marginBottom: 28,
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
    gap: 12,
  },
  cardLabel: {
    display: "flex",
    alignItems: "center",
    gap: 8,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: "50%",
    flexShrink: 0,
  },
  topicName: {
    fontSize: 14,
    fontWeight: 600,
    color: "var(--text)",
    flex: 1,
  },
  levelBadge: {
    fontSize: 11,
    fontWeight: 600,
    padding: "2px 8px",
    borderRadius: 20,
    border: "1px solid",
    letterSpacing: "0.02em",
  },
  segmented: {
    display: "flex",
    gap: 5,
  },
  segBtn: {
    flex: 1,
    padding: "7px 4px",
    background: "var(--bg-elevated)",
    border: "1px solid var(--border)",
    borderRadius: "var(--radius-sm)",
    color: "var(--text-muted)",
    fontSize: 12,
    fontWeight: 500,
    cursor: "pointer",
    textAlign: "center",
    transition: "background 150ms ease, border-color 150ms ease, color 150ms ease",
    whiteSpace: "nowrap",
  },
  footer: {
    marginTop: 28,
    display: "flex",
    alignItems: "center",
    gap: 16,
  },
  saveBtn: {
    flex: 1,
    padding: "12px",
    background: "var(--accent)",
    border: "none",
    borderRadius: "var(--radius-sm)",
    color: "#fff",
    fontSize: 15,
    fontWeight: 600,
    cursor: "pointer",
    transition: "opacity 150ms ease",
  },
  savedMsg: {
    fontSize: 13,
    fontWeight: 500,
    color: "var(--success)",
    whiteSpace: "nowrap",
  },
  errorMsg: {
    fontSize: 13,
    fontWeight: 500,
    color: "var(--danger)",
    whiteSpace: "nowrap",
  },
};
