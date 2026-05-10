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
      const token = getToken();
      if (!token) {
        if (!cancelled) setAuthInitialized(true);
        return;
      }
      if (isAccessTokenExpired(token)) {
        clearSession();
        logout();
        if (!cancelled) setAuthInitialized(true);
        return;
      }
      const result = await verifySession();
      if (cancelled) return;
      if (result.ok && result.user) {
        login(result.user, token);
      }
      setAuthInitialized(true);
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
    <>
      {!hideAll && <Navbar />}
      {!hideSubAndFooter && <SubNavbar />}
      <main>{children}</main>
      {!hideSubAndFooter && <Footer />}
    </>
  );
}
