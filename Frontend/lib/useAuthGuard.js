"use client";
/**
 * useAuthGuard — client-side route protection hook.
 *
 * Usage:
 *   const ready = useAuthGuard();          // any logged-in user
 *   const ready = useAuthGuard("lawyer");  // specific role
 *
 * Returns `true` only after confirming the user is authenticated (and has
 * the right role). While checking, returns `false` so the page can render
 * nothing and avoid showing private content before redirect.
 */
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { isLoggedIn, getUser } from "@/lib/api";

export function useAuthGuard(requiredRole = null) {
  const router = useRouter();
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!isLoggedIn()) {
      router.replace("/login");
      return;
    }
    if (requiredRole) {
      const user = getUser();
      if (user?.role !== requiredRole) {
        // Wrong role — send to their own dashboard
        const u = getUser();
        router.replace(u?.role === "lawyer" ? "/dashboard/lawyer" : "/dashboard/user");
        return;
      }
    }
    setReady(true);
  }, []);

  return ready;
}
