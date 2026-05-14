"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  getToken,
  getUser,
  verifySession,
  isAccessTokenExpired,
  clearSession,
} from "@/lib/api";
import { useAuthStore } from "@/app/lib/authStore";

export function useAuthGuard(requiredRole = null) {
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;

    async function run() {
      const token = getToken();
      if (!token) {
        router.replace("/login");
        return;
      }
      if (isAccessTokenExpired(token)) {
        clearSession();
        useAuthStore.getState().logout();
        router.replace("/login");
        return;
      }

      const result = await verifySession();
      if (cancelled) return;

      if (result.sessionInvalid) {
        router.replace("/login");
        return;
      }
      if (result.ok && result.user) {
        useAuthStore.getState().login(result.user, token);
      } else if (result.networkError || !result.ok) {
        const u = getUser();
        if (u) useAuthStore.getState().login(u, token);
        else {
          router.replace("/login");
          return;
        }
      }

      const user = useAuthStore.getState().user;
      if (!user) {
        router.replace("/login");
        return;
      }
      if (requiredRole) {
        if (user?.role !== requiredRole) {
          router.replace(
            user?.role === "lawyer" ? "/dashboard/lawyer" : "/dashboard/user"
          );
          return;
        }
      }

      setReady(true);
    }

    run();
    return () => {
      cancelled = true;
    };
  }, [requiredRole, router]);

  return ready;
}
