"use client";

import { Scale, ChevronDown, LogOut, LayoutDashboard, User } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState, useEffect, useRef } from "react";
import { getUser, clearSession, isLoggedIn } from "@/lib/api";

export default function Navbar() {
  const router = useRouter();

  // mounted prevents SSR/hydration mismatch and flicker
  const [mounted, setMounted] = useState(false);
  const [user, setUser] = useState(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef(null);

  useEffect(() => {
    setUser(getUser());
    setMounted(true);
  }, []);

  useEffect(() => {
    function handleClickOutside(e) {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  function handleLogout() {
    clearSession();
    setUser(null);
    setMenuOpen(false);
    router.push("/");
  }

  function goToDashboard() {
    setMenuOpen(false);
    router.push(user?.role === "lawyer" ? "/dashboard/lawyer" : "/dashboard/user");
  }

  // Initials from name for the avatar
  const initials = user?.name
    ? user.name.split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase()
    : "?";

  return (
    <header className="border-b border-gray-200 bg-white sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-6 lg:px-12">
        <div className="flex items-center justify-between h-20">
          {/* Logo */}
          <div
            className="flex items-center gap-3 cursor-pointer"
            onClick={() => router.push("/")}
          >
            <div className="w-10 h-10 bg-[#052379] rounded-xl flex items-center justify-center">
              <Scale className="w-6 h-6 text-white" />
            </div>
            <span className="text-xl font-semibold text-gray-900">Lawgic</span>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-4">
            <button className="px-4 py-2 text-sm font-medium text-gray-900 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors">
              EN ↔ اردو
            </button>

            {/* Auth area — render nothing until mounted to avoid flicker */}
            {!mounted ? (
              <div className="w-24 h-9" />
            ) : user ? (
              /* ── Logged-in: avatar + dropdown ── */
              <div className="relative" ref={menuRef}>
                <button
                  onClick={() => setMenuOpen((o) => !o)}
                  className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-gray-100 transition-colors"
                >
                  <div className="w-8 h-8 rounded-full bg-[#052379] flex items-center justify-center text-white text-xs font-semibold select-none">
                    {initials}
                  </div>
                  <span className="text-sm font-medium text-gray-900 max-w-[120px] truncate hidden sm:block">
                    {user.name}
                  </span>
                  <ChevronDown className="w-4 h-4 text-gray-500" />
                </button>

                {menuOpen && (
                  <div className="absolute right-0 mt-2 w-48 bg-white border border-gray-200 rounded-xl shadow-lg py-1 z-50">
                    <div className="px-4 py-2 border-b border-gray-100">
                      <p className="text-xs text-gray-500 capitalize">{user.role}</p>
                      <p className="text-sm font-medium text-gray-900 truncate">{user.name}</p>
                    </div>
                    <button
                      onClick={goToDashboard}
                      className="w-full flex items-center gap-2 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
                    >
                      <LayoutDashboard className="w-4 h-4" />
                      Dashboard
                    </button>
                    <div className="border-t border-gray-100 mt-1" />
                    <button
                      onClick={handleLogout}
                      className="w-full flex items-center gap-2 px-4 py-2 text-sm text-red-600 hover:bg-red-50 transition-colors"
                    >
                      <LogOut className="w-4 h-4" />
                      Logout
                    </button>
                  </div>
                )}
              </div>
            ) : (
              /* ── Logged-out: Login / Register ── */
              <div className="flex items-center gap-2">
                <button
                  onClick={() => router.push("/login")}
                  className="px-4 py-2 text-sm font-medium text-gray-900 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
                >
                  Login
                </button>
                <button
                  onClick={() => router.push("/register/user")}
                  className="px-4 py-2 text-sm font-medium text-white bg-[#052379] rounded-lg hover:bg-[#041d5c] transition-colors"
                >
                  Register
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
