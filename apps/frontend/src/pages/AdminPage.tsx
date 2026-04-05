import { useState, useEffect } from "react";
import { User } from "../api";
import styles from "./Page.module.css";

interface Props {
  user: User;
}

interface AdminData {
  message: string;
  user: User;
}

export default function AdminPage(_props: Props) {
  const [data, setData] = useState<AdminData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/admin")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(setData)
      .catch((e) => setError(e.message));
  }, []);

  return (
    <main className={styles.container}>
      <h1 className={styles.title}>⚙️ Admin Panel</h1>
      <p className={styles.subtitle}>Přístupný pouze pro roli <span className={styles.badge}>admin</span></p>

      {error && <div className={styles.alert}>{error}</div>}
      {data && (
        <div className={styles.card}>
          <div className={styles.cardContent}>
            <h3>{data.message}</h3>
            <pre className={styles.pre}>{JSON.stringify(data.user, null, 2)}</pre>
          </div>
        </div>
      )}
    </main>
  );
}
