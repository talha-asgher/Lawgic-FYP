"use client";

import { Scale } from "lucide-react";
import { useRouter } from "next/navigation";

export default function Navbar() {
  const router = useRouter();

  return (
    <header className="border-b border-gray-200 bg-white sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-6 lg:px-12">
        <div className="flex items-center justify-between h-20">
          {/* Logo */}
          <div className="flex items-center gap-3">
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
          </div>
        </div>
      </div>
    </header>
  );
}
