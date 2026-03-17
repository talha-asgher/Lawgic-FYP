import { create } from "zustand";

export const useAuthStore = create((set) => ({
  user: null,
  token: null,
  isLoggedIn: false,

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