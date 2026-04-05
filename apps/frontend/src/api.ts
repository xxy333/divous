export interface User {
  sub: string;
  preferred_username: string;
  email: string | null;
  name: string | null;
  roles: string[];
}

export async function fetchMe(): Promise<User | null> {
  const res = await fetch("/me");
  if (res.status === 401) return null;
  if (!res.ok) throw new Error("Failed to fetch user");
  return res.json();
}
