"use client";

import { usePathname } from "next/navigation";
import { useEffect } from "react";
import Navbar from "./Navbar";
import SubNavbar from "./SubNavbar";
import Footer from "./Footer";
import {
  verifySession,
  isAccessTokenExpired,
  clearSession,
  getToken,
} from "@/lib/api";
import { useAuthStore } from "../lib/authStore";

export default function ClientLayout({ children }) {
  const pathname = usePathname();
  const login = useAuthStore((s) => s.login);
  const logout = useAuthStore((s) => s.logout);
  const setAuthInitialized = useAuthStore((s) => s.setAuthInitialized);

  useEffect(() => {
    let cancelled = false;

    async function hydrateAuth() {
      try {
        const token = getToken();
        if (!token) return;
        if (isAccessTokenExpired(token)) {
          clearSession();
          logout();
          return;
        }
        const result = await verifySession();
        if (cancelled) return;
        if (result.ok && result.user) {
          login(result.user, token);
        }
      } finally {
        if (!cancelled) setAuthInitialized(true);
      }
    }

    hydrateAuth();
    return () => {
      cancelled = true;
    };
  }, [login, logout, setAuthInitialized]);

  // Login / register pages render their own full-page header
  const hideAll =
    pathname.startsWith("/login") ||
    pathname.startsWith("/register");

  const hideSubAndFooter = hideAll;

  return (
    <LanguageProvider>
      {!hideAll && <Navbar />}
      {!hideSubAndFooter && <SubNavbar />}
      <main>{children}</main>
      {!hideSubAndFooter && <Footer />}
    </LanguageProvider>
  );
}
