import { useState, useEffect } from "react";
import { User } from "../api";
import TiltCard from "../components/TiltCard";
import styles from "./Page.module.css";

interface Props {
  user: User;
}

function useTyping(text: string, speed = 60) {
  const [displayed, setDisplayed] = useState("");
  useEffect(() => {
    setDisplayed("");
    let i = 0;
    const interval = setInterval(() => {
      i++;
      setDisplayed(text.slice(0, i));
      if (i >= text.length) clearInterval(interval);
    }, speed);
    return () => clearInterval(interval);
  }, [text, speed]);
  return displayed;
}

export default function HomePage({ user }: Props) {
  const isAdmin = user.roles.includes("admin");
  const isDev = user.roles.includes("developer") || isAdmin;
  const greeting = useTyping(`Vítej zpět, ${user.preferred_username}!`, 55);

  return (
    <main className={styles.container}>
      <h1 className={styles.title}>Dashboard</h1>
      <p className={styles.subtitle}>
        <strong>{greeting}</strong>
        <span className={styles.cursor}>|</span>
      </p>

      <div className={styles.cards}>
        <TiltCard className={styles.card}>
          <div className={styles.cardIcon}>👤</div>
          <div className={styles.cardContent}>
            <h3>Uživatel</h3>
            <p>{user.name || user.preferred_username}</p>
            {user.email && <p className={styles.muted}>{user.email}</p>}
          </div>
        </TiltCard>

        <TiltCard className={styles.card}>
          <div className={styles.cardIcon}>🔐</div>
          <div className={styles.cardContent}>
            <h3>Role</h3>
            <div className={styles.roles}>
              {user.roles.map((r) => (
                <span key={r} className={styles.badge}>{r}</span>
              ))}
            </div>
          </div>
        </TiltCard>

        {isDev && (
          <TiltCard href="/dashboard/dev" className={`${styles.card} ${styles.cardLink}`}>
            <div className={styles.cardIcon}>🛠️</div>
            <div className={styles.cardContent}>
              <h3>Developer Panel</h3>
              <p className={styles.muted}>Přístup ke dev endpointu</p>
            </div>
          </TiltCard>
        )}

        {isAdmin && (
          <TiltCard href="/dashboard/admin" className={`${styles.card} ${styles.cardLink}`}>
            <div className={styles.cardIcon}>⚙️</div>
            <div className={styles.cardContent}>
              <h3>Admin Panel</h3>
              <p className={styles.muted}>Správa systému</p>
            </div>
          </TiltCard>
        )}
      </div>
    </main>
  );
}
