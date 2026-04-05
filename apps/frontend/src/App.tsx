import { useState, useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { fetchMe, User } from "./api";
import Navbar from "./components/Navbar";
import HomePage from "./pages/HomePage";
import DevPage from "./pages/DevPage";
import AdminPage from "./pages/AdminPage";
import NotFoundPage from "./pages/NotFoundPage";

function App() {
  const [user, setUser] = useState<User | null | undefined>(undefined);

  useEffect(() => {
    fetchMe()
      .then(setUser)
      .catch(() => setUser(null));
  }, []);

  if (user === undefined) {
    return <LoadingScreen />;
  }

  if (user === null) {
    window.location.href = "/login";
    return <LoadingScreen message="Přesměrování na přihlášení..." />;
  }

  return (
    <BrowserRouter>
      <Navbar user={user} />
      <Routes>
        <Route path="/" element={<HomePage user={user} />} />
        <Route
          path="/dashboard/dev"
          element={
            user.roles.includes("developer") || user.roles.includes("admin") ? (
              <DevPage user={user} />
            ) : (
              <Navigate to="/" replace />
            )
          }
        />
        <Route
          path="/dashboard/admin"
          element={
            user.roles.includes("admin") ? (
              <AdminPage user={user} />
            ) : (
              <Navigate to="/" replace />
            )
          }
        />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </BrowserRouter>
  );
}

function LoadingScreen({ message = "Načítání..." }: { message?: string }) {
  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      justifyContent: "center",
      alignItems: "center",
      height: "100vh",
      gap: "1.5rem",
      background: "#0f0f1a",
      animation: "fadeIn 0.3s ease",
    }}>
      <div style={{
        width: 48,
        height: 48,
        border: "3px solid rgba(67,97,238,0.2)",
        borderTop: "3px solid #4361ee",
        borderRadius: "50%",
        animation: "spin 0.8s linear infinite",
      }} />
      <p style={{ color: "#a8b2d8", fontSize: "1rem" }}>{message}</p>
    </div>
  );
}

export default App;
