import { useEffect, useState } from "react";
import { Routes, Route, useNavigate, useLocation, Link } from "react-router-dom";
import { api } from "./api/client";
import { User } from "./types";

function useUser() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) { setLoading(false); return; }
    api.get<User>("/v1/users/me")
      .then((r) => setUser(r.data))
      .finally(() => setLoading(false));
  }, []);

  return { user, loading };
}

function ProfilePage() {
  const { user, loading } = useUser();
  const navigate = useNavigate();

  function logout() {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    navigate("/login");
  }

  if (loading) return <div style={styles.center}>Загрузка...</div>;
  if (!user) { navigate("/login"); return null; }

  const hour = new Date().getHours();
  const greeting =
    hour < 6 ? "Доброй ночи" :
    hour < 12 ? "Доброе утро" :
    hour < 18 ? "Добрый день" : "Добрый вечер";

  return (
    <div style={styles.page}>
      <div style={styles.card}>
        <div style={styles.avatar}>{user.username[0].toUpperCase()}</div>
        <h1 style={styles.greeting}>{greeting}, {user.username}!</h1>
        <p style={styles.email}>{user.email}</p>
        <div style={styles.badge}>{user.plan === "pro" ? "Pro" : "Free"}</div>
        <button style={styles.btn} onClick={logout}>Выйти</button>
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

  async function handleTelegramAuth(data: object) {
    // виджет вызвал нас с данными юзера — шлём на бэкенд
    const r = await api.post("/v1/auth/telegram", data);
    localStorage.setItem("access_token", r.data.access_token);
    localStorage.setItem("refresh_token", r.data.refresh_token);
    navigate("/profile");
  }

  return (
    <div style={styles.page}>
      <div style={styles.card}>
        <h1 style={{ fontSize: 24, marginBottom: 8 }}>News Radar</h1>
        <p style={{ color: "var(--text-muted)", marginBottom: 32 }}>
          Новости с AI-персонализацией
        </p>
        <a href="/api/v1/auth/google/login" style={styles.googleBtn}>
          <svg width="20" height="20" viewBox="0 0 48 48" style={{ flexShrink: 0 }}>
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
    const code = params.get("code"); // одноразовый code, не токен

    if (!code) { navigate("/login", { replace: true }); return; }

    // сразу меняем URL чтобы code не висел в адресной строке
    window.history.replaceState({}, "", "/oauth/callback");

    // обмениваем code на токены через POST — токены идут в теле ответа, не в URL
    api.post<{ access_token: string; refresh_token: string }>("/v1/auth/exchange", { code })
      .then((r) => {
        localStorage.setItem("access_token", r.data.access_token);
        localStorage.setItem("refresh_token", r.data.refresh_token);
        navigate("/profile", { replace: true });
      })
      .catch(() => navigate("/login", { replace: true }));
  }, []);

  return <div style={styles.center}>Входим...</div>;
}

const styles: Record<string, React.CSSProperties> = {
  page: {
    minHeight: "100dvh",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: "var(--bg)",
  },
  card: {
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
      <Route path="/" element={<LoginPage />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/profile" element={<ProfilePage />} />
      <Route path="/oauth/callback" element={<OAuthCallback />} />
    </Routes>
  );
}
