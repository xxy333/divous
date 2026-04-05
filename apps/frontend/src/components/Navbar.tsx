import { User } from "../api";
import styles from "./Navbar.module.css";

interface Props {
  user: User;
}

export default function Navbar({ user }: Props) {
  const isAdmin = user.roles.includes("admin");
  const isDev = user.roles.includes("developer") || isAdmin;

  return (
    <nav className={styles.navbar}>
      <div className={styles.brand}>🚀 DevOps Portal</div>
      <div className={styles.links}>
        <a href="/">Dashboard</a>
        {isDev && <a href="/dashboard/dev">Developer</a>}
        {isAdmin && <a href="/dashboard/admin">Admin</a>}
      </div>
      <div className={styles.user}>
        <span className={styles.username}>👤 {user.preferred_username}</span>
        <span className={styles.role}>{user.roles.join(", ")}</span>
        <form method="post" action="/logout">
          <button type="submit" className={styles.logoutBtn}>Odhlásit</button>
        </form>
      </div>
    </nav>
  );
}
