import { useEffect, useState } from "react";
import { Routes, Route, useNavigate, useLocation, Link, Navigate } from "react-router-dom";
import { api } from "./api/client";
import { User, NewsItem } from "./types";

function useUser() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) { setLoading(false); return; }
    api.get<User>("/v1/users/me")
      .then((r) => setUser(r.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return { user, loading };
}

function NavBar() {
  return (
    <nav style={s.nav}>
      <Link to="/feed" style={s.navLogo}>News Radar</Link>
      <div style={s.navLinks}>
        <Link to="/feed" style={s.navLink}>Лента</Link>
        <Link to="/profile" style={s.navLink}>Профиль</Link>
      </div>
    </nav>
  );
}

function NewsCard({ item }: { item: NewsItem }) {
  function timeAgo(iso: string) {
    const diff = Date.now() - new Date(iso).getTime();
    const min = Math.floor(diff / 60_000);
    if (min < 1) return "только что";
    if (min < 60) return `${min} мин назад`;
    const h = Math.floor(min / 60);
    if (h < 24) return `${h} ч назад`;
    return `${Math.floor(h / 24)} д назад`;
  }

  const preview = item.body.length > 280
    ? item.body.slice(0, 280) + "…"
    : item.body;

  return (
    <article style={s.card}>
      {item.image_url && (
        <img
          src={item.image_url}
          alt=""
          style={s.cardImage}
          onError={e => { (e.target as HTMLImageElement).style.display = "none"; }}
        />
      )}

      <div style={s.cardMeta}>
        <span style={s.source}>{item.source.name}</span>
        <span style={s.time}>{timeAgo(item.published_at ?? item.created_at)}</span>
      </div>

      {item.title && <h2 style={s.cardTitle}>{item.title}</h2>}

      <p style={s.cardBody}>{preview}</p>

      {item.url && (
        <a href={item.url} target="_blank" rel="noreferrer" style={s.readMore}>
          Читать оригинал →
        </a>
      )}
    </article>
  );
}

const LIMIT = 20;

function FeedPage() {
  const [items, setItems] = useState<NewsItem[]>([]);
  const [page, setPage] = useState(0);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);

  async function loadPage(p: number) {
    setLoading(true);
    try {
      const r = await api.get<{ items: NewsItem[]; total: number }>(
        `/v1/news/?limit=${LIMIT}&offset=${p * LIMIT}`
      );
      setItems(r.data.items);
      setTotal(r.data.total);
      setPage(p);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadPage(0); }, []);

  const totalPages = Math.ceil(total / LIMIT);

  return (
    <div style={s.page}>
      <NavBar />
      <main style={s.feed}>
        {items.length === 0 && !loading && (
          <div style={s.empty}>
            <p>Новостей пока нет.</p>
            <p style={{ color: "var(--text-muted)", fontSize: 13, marginTop: 8 }}>
              Запустите парсинг через Celery worker.
            </p>
          </div>
        )}

        {loading && <div style={s.endMsg}>Загрузка…</div>}

        {!loading && items.map(item => <NewsCard key={item.id} item={item} />)}

        {totalPages > 1 && (
          <div style={s.pagination}>
            <button
              style={s.pageBtn}
              onClick={() => loadPage(page - 1)}
              disabled={page === 0}
            >
              ← Назад
            </button>

            <span style={s.pageInfo}>
              {page + 1} / {totalPages}
            </span>

            <button
              style={s.pageBtn}
              onClick={() => loadPage(page + 1)}
              disabled={page >= totalPages - 1}
            >
              Вперёд →
            </button>
          </div>
        )}
      </main>
    </div>
  );
}

function ProfilePage() {
  const { user, loading } = useUser();
  const navigate = useNavigate();

  function logout() {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    navigate("/login");
  }

  if (loading) return <div style={s.center}>Загрузка...</div>;
  if (!user) { navigate("/login"); return null; }

  const hour = new Date().getHours();
  const greeting =
    hour < 6 ? "Доброй ночи" :
    hour < 12 ? "Доброе утро" :
    hour < 18 ? "Добрый день" : "Добрый вечер";

  return (
    <div style={s.page}>
      <NavBar />
      <div style={s.profileWrap}>
        <div style={s.card}>
          <div style={s.avatar}>{user.username[0].toUpperCase()}</div>
          <h1 style={s.greeting}>{greeting}, {user.username}!</h1>
          <p style={s.email}>{user.email}</p>
          <div style={s.badge}>{user.plan === "pro" ? "Pro" : "Free"}</div>
          <button style={s.btn} onClick={logout}>Выйти</button>
        </div>
      </div>
    </div>
  );
}

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
      const msg = err.response?.data?.detail;
      if (Array.isArray(msg)) {
        setError(msg[0]?.msg ?? "Ошибка");
      } else {
        setError(msg ?? "Что-то пошло не так");
      }
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
        <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>News Radar</h1>
        <p style={{ color: "var(--text-muted)", fontSize: 13, marginBottom: 20 }}>
          Новости с AI-персонализацией
        </p>

        <div style={s.tabs}>
          <button style={tab === "login" ? s.tabActive : s.tab} onClick={() => { setTab("login"); setError(""); }}>
            Войти
          </button>
          <button style={tab === "register" ? s.tabActive : s.tab} onClick={() => { setTab("register"); setError(""); }}>
            Регистрация
          </button>
        </div>

        <form onSubmit={handleSubmit} style={{ width: "100%", display: "flex", flexDirection: "column", gap: 10 }}>
          <input
            style={s.input}
            type="email"
            placeholder="Email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            required
            autoComplete="email"
          />
          {tab === "register" && (
            <input
              style={s.input}
              type="text"
              placeholder="Имя пользователя"
              value={username}
              onChange={e => setUsername(e.target.value)}
              required
              autoComplete="username"
            />
          )}
          <input
            style={s.input}
            type="password"
            placeholder="Пароль (минимум 8 символов)"
            value={password}
            onChange={e => setPassword(e.target.value)}
            required
            autoComplete={tab === "login" ? "current-password" : "new-password"}
          />

          {error && <p style={s.errorMsg}>{error}</p>}

          <button type="submit" style={s.submitBtn} disabled={loading}>
            {loading ? "..." : tab === "login" ? "Войти" : "Создать аккаунт"}
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
        <div style={{ display: "flex", justifyContent: "center" }}>
          <TelegramWidget onAuth={handleTelegramAuth} />
        </div>
      </div>
    </div>
  );
}

function OAuthCallback() {
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const code = params.get("code");
    if (!code) { navigate("/login", { replace: true }); return; }
    window.history.replaceState({}, "", "/oauth/callback");
    // clear any existing tokens before exchanging the new code
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    api.post<{ access_token: string; refresh_token: string }>("/v1/auth/exchange", { code })
      .then((r) => {
        localStorage.setItem("access_token", r.data.access_token);
        localStorage.setItem("refresh_token", r.data.refresh_token);
        navigate("/feed", { replace: true });
      })
      .catch(() => navigate("/login", { replace: true }));
  }, []);

  return <div style={s.center}>Входим...</div>;
}

const s: Record<string, React.CSSProperties> = {
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

  page: {
    minHeight: "100dvh",
    background: "var(--bg)",
  },
  feed: {
    maxWidth: 680,
    margin: "0 auto",
    padding: "16px 16px 40px",
    display: "flex",
    flexDirection: "column",
    gap: 12,
  },
  empty: {
    textAlign: "center",
    padding: "60px 20px",
    color: "var(--text-muted)",
  },

  pagination: {
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    gap: 16,
    padding: "16px 0",
  },
  pageBtn: {
    padding: "8px 20px",
    background: "var(--bg-card)",
    border: "1px solid var(--border)",
    borderRadius: "var(--radius-sm)",
    color: "var(--text)",
    cursor: "pointer",
    fontSize: 14,
    fontWeight: 500,
  },
  pageInfo: {
    color: "var(--text-muted)",
    fontSize: 14,
    minWidth: 60,
    textAlign: "center" as const,
  },

  card: {
    background: "var(--bg-card)",
    border: "1px solid var(--border)",
    borderRadius: "var(--radius)",
    padding: "16px 20px",
    display: "flex",
    flexDirection: "column",
    gap: 8,
  },
  cardImage: {
    width: "100%",
    height: 200,
    objectFit: "cover" as const,
    borderRadius: "var(--radius-sm)",
    marginBottom: 4,
  },
  cardMeta: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  source: {
    fontSize: 12,
    fontWeight: 600,
    color: "var(--accent)",
    textTransform: "uppercase",
    letterSpacing: "0.05em",
  },
  time: {
    fontSize: 12,
    color: "var(--text-muted)",
  },
  cardTitle: {
    fontSize: 16,
    fontWeight: 600,
    lineHeight: 1.4,
    color: "var(--text)",
  },
  cardBody: {
    fontSize: 14,
    color: "var(--text-muted)",
    lineHeight: 1.6,
  },
  readMore: {
    fontSize: 13,
    color: "var(--accent)",
    textDecoration: "none",
    marginTop: 4,
    alignSelf: "flex-start",
  },

  endMsg: {
    textAlign: "center",
    color: "var(--text-muted)",
    fontSize: 13,
    padding: "16px",
  },

  profileWrap: {
    minHeight: "calc(100dvh - 56px)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
  },
  avatar: {
    width: 72,
    height: 72,
    borderRadius: "50%",
    background: "var(--accent)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: 28,
    fontWeight: 700,
    marginBottom: 8,
  },
  greeting: {
    fontSize: 22,
    fontWeight: 600,
    textAlign: "center",
  },
  email: {
    color: "var(--text-muted)",
    fontSize: 14,
  },
  badge: {
    background: "var(--bg-elevated)",
    border: "1px solid var(--border)",
    borderRadius: 20,
    padding: "2px 14px",
    fontSize: 13,
    color: "var(--text-muted)",
  },
  btn: {
    marginTop: 16,
    padding: "10px 24px",
    background: "transparent",
    border: "1px solid var(--border)",
    borderRadius: "var(--radius-sm)",
    color: "var(--text-muted)",
    cursor: "pointer",
    fontSize: 14,
  },

  tabs: {
    display: "flex",
    width: "100%",
    background: "var(--bg-elevated)",
    borderRadius: "var(--radius-sm)",
    padding: 3,
    gap: 3,
    marginBottom: 4,
  },
  tab: {
    flex: 1,
    padding: "7px 0",
    background: "transparent",
    border: "none",
    borderRadius: "var(--radius-sm)",
    color: "var(--text-muted)",
    cursor: "pointer",
    fontSize: 14,
    fontWeight: 500,
  },
  tabActive: {
    flex: 1,
    padding: "7px 0",
    background: "var(--bg-card)",
    border: "none",
    borderRadius: "var(--radius-sm)",
    color: "var(--text)",
    cursor: "pointer",
    fontSize: 14,
    fontWeight: 600,
  },
  input: {
    width: "100%",
    padding: "11px 14px",
    background: "var(--bg-elevated)",
    border: "1px solid var(--border)",
    borderRadius: "var(--radius-sm)",
    color: "var(--text)",
    fontSize: 14,
    outline: "none",
  },
  submitBtn: {
    width: "100%",
    padding: "11px",
    background: "var(--accent)",
    border: "none",
    borderRadius: "var(--radius-sm)",
    color: "#fff",
    fontSize: 14,
    fontWeight: 600,
    cursor: "pointer",
    marginTop: 2,
  },
  errorMsg: {
    color: "var(--danger)",
    fontSize: 13,
    textAlign: "center" as const,
  },
  divider: {
    display: "flex",
    alignItems: "center",
    width: "100%",
    gap: 10,
    margin: "4px 0",
  },
  dividerLine: {
    flex: 1,
    height: 1,
    background: "var(--border)",
  },
  dividerText: {
    color: "var(--text-muted)",
    fontSize: 12,
  },

  authPage: {
    minHeight: "100dvh",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: "var(--bg)",
  },
  authCard: {
    background: "var(--bg-card)",
    border: "1px solid var(--border)",
    borderRadius: "var(--radius)",
    padding: "40px",
    width: "100%",
    maxWidth: "380px",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: "12px",
  },
  googleBtn: {
    display: "flex",
    alignItems: "center",
    gap: 12,
    padding: "12px 24px",
    background: "var(--bg-elevated)",
    border: "1px solid var(--border)",
    borderRadius: "var(--radius-sm)",
    color: "var(--text)",
    fontSize: 15,
    fontWeight: 500,
    textDecoration: "none",
    width: "100%",
    justifyContent: "center",
  },

  center: {
    minHeight: "100dvh",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    color: "var(--text-muted)",
  },
};

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/feed" replace />} />
      <Route path="/feed" element={<FeedPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/profile" element={<ProfilePage />} />
      <Route path="/oauth/callback" element={<OAuthCallback />} />
    </Routes>
  );
}
