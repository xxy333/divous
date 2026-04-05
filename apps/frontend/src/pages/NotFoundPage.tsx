import styles from "./Page.module.css";

export default function NotFoundPage() {
  return (
    <main className={styles.container}>
      <h1 className={styles.title}>404</h1>
      <p className={styles.subtitle}>Stránka nenalezena.</p>
      <a href="/">← Zpět na dashboard</a>
    </main>
  );
}
