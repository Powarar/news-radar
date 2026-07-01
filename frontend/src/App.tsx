import { useEffect, useState } from "react";
import { Routes, Route, useNavigate, Link, Navigate, useLocation } from "react-router-dom";
import { api } from "./api/client";
import { User, NewsItem } from "./types";
import NavBar from "./components/NavBar";
import PreferencesPage from "./components/PreferencesPage";
import SourcesPage from "./components/SourcesPage";
import { TOPIC_LABELS, TOPIC_COLORS } from "./constants";

// ─── Icons ────────────────────────────────────────────────────────────────────

function IconThumbUp({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M7 10v12" /><path d="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2a3.13 3.13 0 0 1 3 3.88Z" />
    </svg>
  );
}

function IconThumbDown({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M17 14V2" /><path d="M9 18.12 10 14H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H20a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2.76a2 2 0 0 0-1.79 1.11L12 22a3.13 3.13 0 0 1-3-3.88Z" />
    </svg>
  );
}

function IconBan({ size = 14 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" /><path d="m4.9 4.9 14.2 14.2" />
    </svg>
  );
}

function IconExternalLink({ size = 13 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" /><polyline points="15 3 21 3 21 9" /><line x1="10" y1="14" x2="21" y2="3" />
    </svg>
  );
}

// ─── Hooks ────────────────────────────────────────────────────────────────────

function useTelegramWebApp() {
  const navigate = useNavigate();
  useEffect(() => {
    const tg = (window as any).Telegram?.WebApp;
    if (!tg?.initData || localStorage.getItem("access_token")) return;
    tg.ready();
    api.post("/v1/auth/telegram/webapp", { init_data: tg.initData })
      .then((r: { data: { access_token: string; refresh_token: string } }) => {
        localStorage.setItem("access_token", r.data.access_token);
        localStorage.setItem("refresh_token", r.data.refresh_token);
        navigate("/feed", { replace: true });
      })
      .catch((err) => console.error("Telegram auth failed", err));
  }, [navigate]);
}

function useUser() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) { setLoading(false); return; }
    api.get<User>("/v1/users/me")
      .then((r) => setUser(r.data))
      .catch((err) => console.error("Failed to fetch user", err))
      .finally(() => setLoading(false));
  }, []);
  return { user, loading };
}

// ─── NewsCard ─────────────────────────────────────────────────────────────────

function NewsCard({ item, user, onReact, enterDelay = 0 }: {
  item: NewsItem;
  user: User | null;
  onReact: (newsId: number, reaction: string) => Promise<void>;
  enterDelay?: number;
}) {
  const [localReaction, setLocalReaction] = useState<string | null>(item.reaction ?? null);
  const [localLikes, setLocalLikes] = useState(item.likes_count);
  const [localDislikes, setLocalDislikes] = useState(item.dislikes_count);
  const [loading, setLoading] = useState(false);

  function timeAgo(iso: string) {
    const ms = new Date(iso).getTime();
    if (Number.isNaN(ms)) return "";
    const diff = Date.now() - ms;
    if (diff < 0) return "только что";
    const min = Math.floor(diff / 60_000);
    if (min < 1) return "только что";
    if (min < 60) return `${min} мин`;
    const h = Math.floor(min / 60);
    if (h < 24) return `${h} ч`;
    return `${Math.floor(h / 24)} д`;
  }

  async function handleReact(reaction: string) {
    if (!user || loading) return;
    setLoading(true);
    const prev = localReaction;
    const isToggleOff = prev === reaction;
    if (reaction === "like") {
      setLocalLikes(n => isToggleOff ? n - 1 : n + 1);
      setLocalDislikes(n => prev === "dislike" && !isToggleOff ? n - 1 : n);
    } else if (reaction === "dislike") {
      setLocalDislikes(n => isToggleOff ? n - 1 : n + 1);
      setLocalLikes(n => prev === "like" && !isToggleOff ? n - 1 : n);
    }
    if (reaction !== "blacklist") setLocalReaction(isToggleOff ? null : reaction);
    try {
      await onReact(item.id, reaction);
    } catch {
      setLocalReaction(prev);
      setLocalLikes(item.likes_count);
      setLocalDislikes(item.dislikes_count);
    } finally {
      setLoading(false);
    }
  }

  const text = item.summary ?? (item.body.length > 240 ? item.body.slice(0, 240) + "…" : item.body);
  const topTopics = Object.entries(item.topics)
    .sort(([, a], [, b]) => b - a)
    .filter(([, score]) => score > 0.15)
    .slice(0, 3);

  return (
    <article
      className="card-enter"
      style={{ ...s.card, animationDelay: `${enterDelay}ms` }}
    >
      {item.image_url && (
        <img
          src={item.image_url}
          alt=""
          style={s.cardThumb}
          onError={e => { (e.target as HTMLImageElement).style.display = "none"; }}
        />
      )}

      <div style={s.cardMeta}>
        <span style={s.source}>{item.source.name}</span>
        <span style={s.metaSep}>·</span>
        <span style={s.time}>{timeAgo(item.published_at ?? item.created_at)}</span>
      </div>

      {item.title && <h2 style={s.cardTitle}>{item.title}</h2>}
      <p style={s.cardBody}>{text}</p>

      <div style={s.cardFooter}>
        {topTopics.length > 0 ? (
          <div style={s.topicsRow}>
            {topTopics.map(([topic]) => (
              <span key={topic} style={{ ...s.topicTag, color: TOPIC_COLORS[topic] ?? "var(--text-muted)" }}>
                {TOPIC_LABELS[topic] ?? topic}
              </span>
            ))}
          </div>
        ) : <span />}

        <div style={s.cardActions}>
          {user && (
            <div style={s.reactionRow}>
              <button
                style={{ ...s.reactionBtn, ...(localReaction === "like" ? s.reactionLike : {}) }}
                onClick={() => handleReact("like")}
                disabled={loading}
                aria-label="Нравится"
                title="Нравится"
              >
                <IconThumbUp /> {localLikes > 0 && <span>{localLikes}</span>}
              </button>
              <button
                style={{ ...s.reactionBtn, ...(localReaction === "dislike" ? s.reactionDislike : {}) }}
                onClick={() => handleReact("dislike")}
                disabled={loading}
                aria-label="Не нравится"
                title="Не нравится"
              >
                <IconThumbDown /> {localDislikes > 0 && <span>{localDislikes}</span>}
              </button>
              <button
                style={s.reactionBtn}
                onClick={() => handleReact("blacklist")}
                disabled={loading}
                aria-label="Скрыть источник"
                title="Скрыть источник"
              >
                <IconBan />
              </button>
            </div>
          )}
          {item.url && (
            <a href={item.url} target="_blank" rel="noreferrer" style={s.readMore}>
              Читать <IconExternalLink />
            </a>
          )}
        </div>
      </div>
    </article>
  );
}

// ─── Skeleton ─────────────────────────────────────────────────────────────────

function CardSkeleton() {
  return (
    <div style={{ padding: "20px 0", borderBottom: "1px solid var(--border)" }}>
      <div className="skeleton" style={{ width: "100%", height: 160, borderRadius: 8, marginBottom: 14 }} />
      <div style={{ display: "flex", gap: 8, marginBottom: 8 }}>
        <div className="skeleton" style={{ width: 64, height: 10 }} />
        <div className="skeleton" style={{ width: 28, height: 10 }} />
      </div>
      <div className="skeleton" style={{ width: "88%", height: 20, marginBottom: 6 }} />
      <div className="skeleton" style={{ width: "72%", height: 20, marginBottom: 12 }} />
      <div className="skeleton" style={{ width: "100%", height: 13, marginBottom: 5 }} />
      <div className="skeleton" style={{ width: "85%", height: 13, marginBottom: 5 }} />
      <div className="skeleton" style={{ width: "60%", height: 13, marginBottom: 14 }} />
      <div style={{ display: "flex", gap: 10 }}>
        <div className="skeleton" style={{ width: 52, height: 10 }} />
        <div className="skeleton" style={{ width: 44, height: 10 }} />
      </div>
    </div>
  );
}

// ─── FeedPage ─────────────────────────────────────────────────────────────────

function GuestBanner() {
  return (
    <div style={s.guestBanner}>
      <span>Хотите персонализировать ленту? </span>
      <Link to="/login" style={{ color: "var(--accent)", fontWeight: 600 }}>Войдите</Link>
      <span> — AI подберёт новости под ваши интересы.</span>
    </div>
  );
}

type SortMode = "relevance" | "date" | "importance";

const SORT_OPTIONS: { value: SortMode; label: string }[] = [
  { value: "relevance", label: "Для вас" },
  { value: "importance", label: "Важные" },
  { value: "date", label: "Новые" },
];

const LIMIT = 20;

function FeedPage() {
  const { user, loading: userLoading } = useUser();
  const [items, setItems] = useState<NewsItem[]>([]);
  const [page, setPage] = useState(0);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [sort, setSort] = useState<SortMode>("relevance");

  async function loadPage(p: number, sortMode: SortMode = sort) {
    setLoading(true);
    try {
      const r = await api.get<{ items: NewsItem[]; total: number }>(
        `/v1/news/?limit=${LIMIT}&offset=${p * LIMIT}&sort=${sortMode}`
      );
      setItems(r.data.items);
      setTotal(r.data.total);
      setPage(p);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (err) {
      console.error("Failed to load feed", err);
    } finally {
      setLoading(false);
    }
  }

  function changeSort(mode: SortMode) {
    setSort(mode);
    loadPage(0, mode);
  }

  useEffect(() => { loadPage(0); }, []);

  // Guests can't use personalization — switch default chip to "date" after load
  useEffect(() => {
    if (!userLoading && !user && sort === "relevance") {
      setSort("date");
      loadPage(0, "date");
    }
  }, [userLoading, user, sort]);

  async function handleReact(newsId: number, reaction: string) {
    const r = await api.post<{ likes: number; dislikes: number }>(`/v1/news/${newsId}/react`, { reaction });
    if (reaction === "blacklist") {
      const sourceId = items.find(x => x.id === newsId)?.source.id;
      if (sourceId) setItems(prev => prev.filter(i => i.source.id !== sourceId));
    } else {
      setItems(prev => prev.map(i => {
        if (i.id !== newsId) return i;
        const newReaction = i.reaction === reaction ? null : (reaction as NewsItem["reaction"]);
        return { ...i, reaction: newReaction, likes_count: r.data.likes, dislikes_count: r.data.dislikes };
      }));
    }
  }

  const totalPages = Math.ceil(total / LIMIT);

  return (
    <div style={s.page}>
      <NavBar />
      <main className="page-enter" style={s.feed}>
        {!userLoading && !user && <GuestBanner />}

        <div style={s.sortBar}>
          {SORT_OPTIONS.map(opt => {
            const isPersonal = opt.value === "relevance";
            const disabled = isPersonal && !user;
            return (
              <button
                key={opt.value}
                disabled={disabled || undefined}
                style={{
                  ...s.sortChip,
                  ...(sort === opt.value ? s.sortChipActive : {}),
                  ...(disabled ? s.sortChipDisabled : {}),
                }}
                onClick={() => !disabled && changeSort(opt.value)}
                title={disabled ? "Войдите, чтобы включить персонализацию" : undefined}
              >
                {opt.label}
              </button>
            );
          })}
        </div>

        {loading ? (
          Array.from({ length: 5 }).map((_, i) => <CardSkeleton key={i} />)
        ) : items.length === 0 ? (
          <div style={s.empty}>
            <svg width="52" height="52" viewBox="0 0 52 52" fill="none" aria-hidden="true" style={{ color: "var(--text-subtle)", marginBottom: 8 }}>
              <circle cx="12" cy="40" r="3.5" fill="currentColor" opacity="0.4" />
              <path d="M12 40 Q12 26 28 26" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" opacity="0.35"/>
              <path d="M12 40 Q12 16 38 16" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" opacity="0.2"/>
              <path d="M12 40 Q12 6 48 6" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" opacity="0.1"/>
            </svg>
            <p style={{ fontWeight: 600, marginBottom: 6 }}>Новостей пока нет</p>
            <p style={{ color: "var(--text-muted)", fontSize: 13 }}>
              Добавьте источники на странице <Link to="/sources" style={{ color: "var(--accent)", textDecoration: "underline" }}>Источники</Link> — новости начнут подгружаться автоматически
            </p>
          </div>
        ) : (
          items.map((item, i) => (
            <NewsCard
              key={item.id}
              item={item}
              user={user}
              onReact={handleReact}
              enterDelay={Math.min(i * 35, 280)}
            />
          ))
        )}

        {totalPages > 1 && !loading && (
          <div style={s.pagination}>
            <button style={s.pageBtn} onClick={() => loadPage(page - 1)} disabled={page === 0}>
              ← Назад
            </button>
            <span style={s.pageInfo}>{page + 1} / {totalPages}</span>
            <button style={s.pageBtn} onClick={() => loadPage(page + 1)} disabled={page >= totalPages - 1}>
              Вперёд →
            </button>
          </div>
        )}
      </main>
    </div>
  );
}

// ─── ProfilePage ──────────────────────────────────────────────────────────────

function ProfilePage() {
  const { user, loading } = useUser();
  const navigate = useNavigate();

  function logout() {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    navigate("/login");
  }

  if (loading) return (
    <div style={s.page}>
      <NavBar />
      <div style={s.centerFull}><div className="skeleton" style={{ width: 240, height: 240, borderRadius: "var(--radius)" }} /></div>
    </div>
  );
  if (!user) { navigate("/login"); return null; }

  const hour = new Date().getHours();
  const greeting = hour < 6 ? "Доброй ночи" : hour < 12 ? "Доброе утро" : hour < 18 ? "Добрый день" : "Добрый вечер";

  return (
    <div style={s.page}>
      <NavBar />
      <div className="page-enter" style={s.profileWrap}>
        <div style={s.profileCard}>
          <div style={s.avatar}>{user.username[0].toUpperCase()}</div>
          <p style={s.greeting}>{greeting}</p>
          <h1 style={s.profileName}>{user.username}</h1>
          {user.email && <p style={s.profileEmail}>{user.email}</p>}
          <span style={{ ...s.badge, ...(user.plan === "pro" ? s.badgePro : {}) }}>
            {user.plan === "pro" ? "✦ Pro" : "Free"}
          </span>
          <div style={s.profileActions}>
            <Link to="/preferences" style={s.profileActionBtn}>Настроить темы →</Link>
            <button style={s.logoutBtn} onClick={logout}>Выйти</button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── TelegramWidget ───────────────────────────────────────────────────────────

function TelegramWidget({ onAuth }: { onAuth: (data: object) => void }) {
  useEffect(() => {
    (window as any).onTelegramAuth = onAuth;
    const script = document.createElement("script");
    script.src = "https://telegram.org/js/telegram-widget.js?22";
    script.setAttribute("data-telegram-login", import.meta.env.VITE_TG_BOT_USERNAME);
    script.setAttribute("data-size", "large");
    script.setAttribute("data-onauth", "onTelegramAuth(user)");
    script.setAttribute("data-request-access", "write");
    script.async = true;
    document.getElementById("tg-widget")?.appendChild(script);
    return () => { delete (window as any).onTelegramAuth; };
  }, []);
  return <div id="tg-widget" />;
}

// ─── LoginPage ────────────────────────────────────────────────────────────────

function LoginPage() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  function saveTokens(data: { access_token: string; refresh_token: string }) {
    localStorage.setItem("access_token", data.access_token);
    localStorage.setItem("refresh_token", data.refresh_token);
    navigate("/feed");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      if (tab === "login") {
        const r = await api.post("/v1/auth/login", { email, password });
        saveTokens(r.data);
      } else {
        const r = await api.post("/v1/auth/register", { email, username, password });
        saveTokens(r.data);
      }
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      let errorMsg = "Что-то пошло не так";
      if (typeof detail === "string") {
        errorMsg = detail;
      } else if (Array.isArray(detail) && typeof detail[0] === "object" && detail[0]?.msg) {
        errorMsg = detail[0].msg;
      }
      setError(errorMsg);
    } finally {
      setLoading(false);
    }
  }

  async function handleTelegramAuth(data: object) {
    const r = await api.post("/v1/auth/telegram", data);
    saveTokens(r.data);
  }

  return (
    <div style={s.authPage}>
      <div style={s.authCard}>
        <div style={s.authHeader}>
          <span style={s.authLogoMark}>
            <svg width="36" height="36" viewBox="0 0 20 20" fill="none" aria-hidden="true">
              <circle cx="4" cy="16" r="1.8" fill="currentColor" />
              <path d="M4 16 Q4 4 16 4" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
              <path d="M4 16 Q4 9 11 9" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
            </svg>
          </span>
          <h1 style={s.authTitle}>News Radar</h1>
          <p style={s.authSubtitle}>Новости с AI‑персонализацией</p>
        </div>

        <div style={s.tabs}>
          {(["login", "register"] as const).map(t => (
            <button
              key={t}
              style={tab === t ? s.tabActive : s.tab}
              onClick={() => { setTab(t); setError(""); }}
            >
              {t === "login" ? "Войти" : "Регистрация"}
            </button>
          ))}
        </div>

        <form onSubmit={handleSubmit} style={s.form}>
          <div style={s.inputWrap}>
            <input style={s.input} type="email" placeholder="Email" value={email}
              onChange={e => setEmail(e.target.value)} required autoComplete="email" />
          </div>
          {tab === "register" && (
            <div style={s.inputWrap}>
              <input style={s.input} type="text" placeholder="Имя пользователя" value={username}
                onChange={e => setUsername(e.target.value)} required autoComplete="username" />
            </div>
          )}
          <div style={s.inputWrap}>
            <input style={s.input} type="password" placeholder="Пароль (минимум 8 символов)" value={password}
              onChange={e => setPassword(e.target.value)} required
              autoComplete={tab === "login" ? "current-password" : "new-password"} />
          </div>

          {error && <p style={s.errorMsg}>{error}</p>}

          <button type="submit" style={s.submitBtn} disabled={loading}>
            {loading ? "…" : tab === "login" ? "Войти" : "Создать аккаунт"}
          </button>
        </form>

        <div style={s.divider}>
          <span style={s.dividerLine} />
          <span style={s.dividerText}>или</span>
          <span style={s.dividerLine} />
        </div>

        <a href="/api/v1/auth/google/login" style={s.googleBtn}>
          <svg width="18" height="18" viewBox="0 0 48 48" style={{ flexShrink: 0 }}>
            <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
            <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
            <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
            <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.18 1.48-4.97 2.31-8.16 2.31-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
          </svg>
          Войти через Google
        </a>
        <div style={{ display: "flex", justifyContent: "center", width: "100%" }}>
          <TelegramWidget onAuth={handleTelegramAuth} />
        </div>
      </div>
    </div>
  );
}

// ─── OAuthCallback ────────────────────────────────────────────────────────────

function OAuthCallback() {
  const navigate = useNavigate();
  const location = useLocation();
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const code = params.get("code");
    if (!code) { navigate("/login", { replace: true }); return; }
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    api.post<{ access_token: string; refresh_token: string }>("/v1/auth/exchange", { code })
      .then(r => {
        localStorage.setItem("access_token", r.data.access_token);
        localStorage.setItem("refresh_token", r.data.refresh_token);
        navigate("/feed", { replace: true });
      })
      .catch(() => navigate("/login", { replace: true }));
  }, [navigate, location.search]);
  return <div style={s.centerFull}><div className="skeleton" style={{ width: 160, height: 20 }} /></div>;
}

// ─── Styles ───────────────────────────────────────────────────────────────────

const s: Record<string, React.CSSProperties> = {
  // Layout
  page: { minHeight: "100dvh", background: "var(--bg)" },
  feed: {
    maxWidth: 700,
    margin: "0 auto",
    padding: "24px 20px 80px",
  },
  centerFull: {
    minHeight: "calc(100dvh - 56px)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },

  // Article row — editorial, no card chrome
  card: {
    padding: "20px 0",
    borderBottom: "1px solid var(--border)",
  },
  cardThumb: {
    display: "block",
    width: "100%",
    height: 200,
    objectFit: "cover" as const,
    borderRadius: 8,
    marginBottom: 14,
    opacity: 0.93,
  },
  cardMeta: {
    display: "flex",
    alignItems: "center",
    gap: 6,
    marginBottom: 6,
  },
  source: {
    fontSize: 11,
    fontWeight: 700,
    color: "var(--accent)",
    textTransform: "uppercase" as const,
    letterSpacing: "0.07em",
  },
  metaSep: { fontSize: 11, color: "var(--text-subtle)" },
  time: { fontSize: 11, color: "var(--text-subtle)" },
  cardTitle: {
    fontSize: 17,
    fontWeight: 700,
    lineHeight: 1.28,
    color: "var(--text)",
    letterSpacing: "-0.02em",
    marginBottom: 6,
  },
  cardBody: {
    fontSize: 14,
    color: "var(--text-muted)",
    lineHeight: 1.65,
    marginBottom: 10,
  },
  topicsRow: { display: "flex", flexWrap: "wrap" as const, gap: 10 },
  topicTag: {
    fontSize: 11,
    fontWeight: 600,
    letterSpacing: "0.04em",
    opacity: 0.85,
  },
  cardFooter: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12,
  },
  cardActions: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    flexShrink: 0,
  },
  readMore: {
    display: "inline-flex",
    alignItems: "center",
    gap: 4,
    fontSize: 12,
    fontWeight: 600,
    color: "var(--accent)",
    textDecoration: "none",
    flexShrink: 0,
    opacity: 0.9,
  },
  reactionRow: { display: "flex", gap: 1 },
  reactionBtn: {
    display: "inline-flex",
    alignItems: "center",
    gap: 4,
    padding: "4px 7px",
    background: "transparent",
    border: "none",
    borderRadius: "var(--radius-xs)",
    color: "var(--text-subtle)",
    cursor: "pointer",
    fontSize: 12,
    fontWeight: 500,
    transition: "color 120ms ease, background 120ms ease",
  },
  reactionLike: {
    color: "var(--success)",
    background: "var(--success-dim)",
  },
  reactionDislike: {
    color: "var(--danger)",
    background: "var(--danger-dim)",
  },

  // Sort bar
  sortBar: {
    display: "flex",
    gap: 6,
    marginBottom: 16,
  },
  sortChip: {
    padding: "5px 14px",
    background: "transparent",
    border: "1px solid var(--border)",
    borderRadius: 20,
    color: "var(--text-muted)",
    cursor: "pointer",
    fontSize: 12,
    fontWeight: 500,
    transition: "all 140ms ease",
    lineHeight: 1.4,
  },
  sortChipActive: {
    background: "var(--accent)",
    borderColor: "var(--accent)",
    color: "#fff",
    fontWeight: 600,
  },
  sortChipDisabled: {
    opacity: 0.35,
    cursor: "not-allowed",
  },

  // Feed meta
  guestBanner: {
    borderLeft: "2px solid var(--accent)",
    paddingLeft: 14,
    paddingTop: 10,
    paddingBottom: 10,
    marginBottom: 4,
    fontSize: 13,
    color: "var(--text-muted)",
    lineHeight: 1.6,
  },
  empty: {
    textAlign: "center" as const,
    padding: "80px 20px",
    color: "var(--text-muted)",
    display: "flex",
    flexDirection: "column" as const,
    alignItems: "center",
    gap: 8,
  },
  emptyIcon: { fontSize: 40, marginBottom: 8 },
  pagination: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: 16,
    padding: "28px 0 8px",
  },
  pageBtn: {
    padding: "7px 16px",
    background: "transparent",
    border: "1px solid var(--border)",
    borderRadius: "var(--radius-sm)",
    color: "var(--text-muted)",
    cursor: "pointer",
    fontSize: 13,
    fontWeight: 500,
    transition: "border-color 150ms ease, color 150ms ease",
  },
  pageInfo: {
    color: "var(--text-subtle)",
    fontSize: 13,
    minWidth: 52,
    textAlign: "center" as const,
  },

  // Profile
  profileWrap: {
    minHeight: "calc(100dvh - 54px)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    padding: "20px 16px",
  },
  profileCard: {
    background: "var(--bg-card)",
    border: "1px solid var(--border)",
    borderRadius: "var(--radius)",
    padding: "40px 32px",
    width: "100%",
    maxWidth: 360,
    display: "flex",
    flexDirection: "column" as const,
    alignItems: "center",
    gap: 8,
    textAlign: "center" as const,
  },
  avatar: {
    width: 68,
    height: 68,
    borderRadius: "50%",
    background: "var(--accent-dim)",
    border: "2px solid var(--accent)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: 26,
    fontWeight: 700,
    color: "var(--accent)",
    marginBottom: 4,
  },
  greeting: { fontSize: 12, color: "var(--text-subtle)", textTransform: "uppercase" as const, letterSpacing: "0.08em" },
  profileName: { fontSize: 22, fontWeight: 700, letterSpacing: "-0.02em" },
  profileEmail: { fontSize: 13, color: "var(--text-muted)" },
  badge: {
    fontSize: 11,
    fontWeight: 600,
    padding: "3px 12px",
    borderRadius: 20,
    background: "var(--bg-elevated)",
    border: "1px solid var(--border)",
    color: "var(--text-muted)",
    letterSpacing: "0.04em",
    marginTop: 4,
  },
  badgePro: { color: "var(--accent)", borderColor: "var(--accent)", background: "var(--accent-dim)" },
  profileActions: { display: "flex", flexDirection: "column" as const, gap: 8, width: "100%", marginTop: 16 },
  profileActionBtn: {
    display: "block",
    padding: "11px",
    background: "var(--accent)",
    border: "none",
    borderRadius: "var(--radius-sm)",
    color: "#fff",
    fontSize: 14,
    fontWeight: 600,
    textAlign: "center" as const,
    textDecoration: "none",
  },
  logoutBtn: {
    padding: "10px",
    background: "transparent",
    border: "1px solid var(--border)",
    borderRadius: "var(--radius-sm)",
    color: "var(--text-muted)",
    cursor: "pointer",
    fontSize: 14,
  },

  // Auth
  authPage: {
    minHeight: "100dvh",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: "var(--bg)",
    padding: "20px 16px",
  },
  authCard: {
    background: "var(--bg-card)",
    border: "1px solid var(--border)",
    borderRadius: "var(--radius)",
    padding: "40px",
    width: "100%",
    maxWidth: "380px",
    display: "flex",
    flexDirection: "column" as const,
    alignItems: "center",
    gap: "14px",
  },
  authHeader: { textAlign: "center" as const, marginBottom: 4 },
  authLogoMark: { fontSize: 28, color: "var(--accent)" },
  authTitle: { fontSize: 22, fontWeight: 700, letterSpacing: "-0.02em", marginTop: 4 },
  authSubtitle: { fontSize: 13, color: "var(--text-muted)", marginTop: 4 },
  tabs: {
    display: "flex",
    width: "100%",
    background: "var(--bg-elevated)",
    borderRadius: "var(--radius-sm)",
    padding: 3,
    gap: 3,
  },
  tab: {
    flex: 1,
    padding: "8px 0",
    background: "transparent",
    border: "none",
    borderRadius: "var(--radius-sm)",
    color: "var(--text-muted)",
    cursor: "pointer",
    fontSize: 13,
    fontWeight: 500,
    transition: "color 150ms ease",
  },
  tabActive: {
    flex: 1,
    padding: "8px 0",
    background: "var(--bg-card)",
    border: "none",
    borderRadius: "var(--radius-sm)",
    color: "var(--text)",
    cursor: "pointer",
    fontSize: 13,
    fontWeight: 600,
    boxShadow: "0 1px 3px rgba(0,0,0,0.3)",
  },
  form: { width: "100%", display: "flex", flexDirection: "column" as const, gap: 8 },
  inputWrap: { width: "100%" },
  input: {
    width: "100%",
    padding: "11px 14px",
    background: "var(--bg-elevated)",
    border: "1px solid var(--border)",
    borderRadius: "var(--radius-sm)",
    color: "var(--text)",
    fontSize: 14,
    outline: "none",
    transition: "border-color 150ms ease",
  },
  submitBtn: {
    width: "100%",
    padding: "12px",
    background: "var(--accent)",
    border: "none",
    borderRadius: "var(--radius-sm)",
    color: "#fff",
    fontSize: 14,
    fontWeight: 600,
    cursor: "pointer",
    marginTop: 2,
    transition: "opacity 150ms ease",
  },
  errorMsg: { color: "var(--danger)", fontSize: 12, textAlign: "center" as const },
  divider: { display: "flex", alignItems: "center", width: "100%", gap: 10 },
  dividerLine: { flex: 1, height: 1, background: "var(--border)" },
  dividerText: { color: "var(--text-subtle)", fontSize: 11 },
  googleBtn: {
    display: "flex",
    alignItems: "center",
    gap: 12,
    padding: "11px 20px",
    background: "var(--bg-elevated)",
    border: "1px solid var(--border)",
    borderRadius: "var(--radius-sm)",
    color: "var(--text)",
    fontSize: 14,
    fontWeight: 500,
    textDecoration: "none",
    width: "100%",
    justifyContent: "center",
    transition: "border-color 150ms ease",
  },
};

// ─── App ──────────────────────────────────────────────────────────────────────

export default function App() {
  useTelegramWebApp();
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/feed" replace />} />
      <Route path="/feed" element={<FeedPage />} />
      <Route path="/preferences" element={<PreferencesPage />} />
      <Route path="/sources" element={<SourcesPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/profile" element={<ProfilePage />} />
      <Route path="/oauth/callback" element={<OAuthCallback />} />
      <Route path="/tg-auth" element={<OAuthCallback />} />
    </Routes>
  );
}
