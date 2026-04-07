import { Routes, Route } from "react-router-dom";

// Pages — to be implemented
const FeedPage = () => <div>Feed</div>;
const TopPage = () => <div>Top News</div>;
const SourcesPage = () => <div>Sources</div>;
const PreferencesPage = () => <div>Preferences</div>;
const ProfilePage = () => <div>Profile</div>;
const LoginPage = () => <div>Login</div>;

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<FeedPage />} />
      <Route path="/top" element={<TopPage />} />
      <Route path="/sources" element={<SourcesPage />} />
      <Route path="/preferences" element={<PreferencesPage />} />
      <Route path="/profile" element={<ProfilePage />} />
      <Route path="/login" element={<LoginPage />} />
    </Routes>
  );
}
