import { create } from "zustand";

export const useAuthStore = create((set) => ({
  user: null,
  token: null,
  isLoggedIn: false,
  /** True after first client-side session check (local JWT + optional /auth/me). */
  authInitialized: false,
  setAuthInitialized: (value) => set({ authInitialized: !!value }),

  login: (user, token) =>
    set({
      user,
      token,
      isLoggedIn: true,
    }),

  logout: () =>
    set({
      user: null,
      token: null,
      isLoggedIn: false,
    }),
}));