"use client";

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
        const u = getUser();
        router.replace(u?.role === "lawyer" ? "/dashboard/lawyer" : "/dashboard/user");
        return;
      }
    }
    setReady(true);
  }, []);

  return ready;
}
