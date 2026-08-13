import { create } from "zustand";
import { persist } from "zustand/middleware";

export type AppRole =
  | "VIEWER"
  | "TEST_ENGINEER"
  | "PROCESS_ENGINEER"
  | "AI_ENGINEER"
  | "MAINTENANCE_ENGINEER"
  | "ADMIN";

interface AuthState {
  accessToken: string | null;
  username: string | null;
  role: AppRole | null;
  permissions: string[];
  setSession: (s: {
    accessToken: string;
    username: string;
    role: AppRole;
    permissions?: string[];
  }) => void;
  clearSession: () => void;
  hasPermission: (p: string) => boolean;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      accessToken: null,
      username: null,
      role: null,
      permissions: [],
      setSession: ({ accessToken, username, role, permissions }) =>
        set({
          accessToken,
          username,
          role,
          permissions: permissions ?? [],
        }),
      clearSession: () =>
        set({ accessToken: null, username: null, role: null, permissions: [] }),
      hasPermission: (p) => {
        const role = get().role;
        if (role === "ADMIN") return true;
        return get().permissions.includes(p);
      },
    }),
    { name: "wyi-auth" },
  ),
);
