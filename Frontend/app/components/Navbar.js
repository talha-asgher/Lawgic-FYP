// "use client";

// import { Scale } from "lucide-react";
// import { useRouter } from "next/navigation";
// import { useAuthStore } from "../lib/authStore";
// import { useEffect } from "react";

// export default function Navbar() {
//   const router = useRouter();

//   const { user, isLoggedIn, logout, login } = useAuthStore();

//   // restore login on refresh
//   useEffect(() => {
//     const savedUser = localStorage.getItem("user");
//     const savedToken = localStorage.getItem("access_token");

//     if (savedUser && savedToken) {
//       login(JSON.parse(savedUser), savedToken);
//     }
//   }, [login]);

//   return (
//     <header className="border-b border-gray-200 bg-white sticky top-0 z-50">
//       <div className="max-w-7xl mx-auto px-6 lg:px-12">
//         <div className="flex items-center justify-between h-20">
          
//           {/* Logo */}
//           <div className="flex items-center gap-3">
//             <div className="w-10 h-10 bg-[#052379] rounded-xl flex items-center justify-center">
//               <Scale className="w-6 h-6 text-white" />
//             </div>
//             <span className="text-xl font-semibold text-gray-900">
//               Lawgic
//             </span>
//           </div>

//           {/* Actions */}
//           <div className="flex items-center gap-4">
//             <button className="px-4 py-2 text-sm font-medium text-gray-900 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors">
//               EN ↔ اردو
//             </button>

//             {/* LOGIN STATE CHECK */}
//             {!isLoggedIn ? (
//               <div className="flex items-center gap-2">
//                 <button
//                   onClick={() => router.push("/login")}
//                   className="px-4 py-2 text-sm font-medium text-gray-900 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
//                 >
//                   Login
//                 </button>

//                 <button
//                   onClick={() => router.push("/register/user")}
//                   className="px-4 py-2 text-sm font-medium text-white bg-[#052379] rounded-lg hover:bg-[#041d5c] transition-colors"
//                 >
//                   Register
//                 </button>
//               </div>
//             ) : (
//               <div className="flex items-center gap-2">

//                 <span className="text-sm text-gray-700">
//                   {user?.email}
//                 </span>

//                 <button
//                   onClick={() =>
//                     router.push(
//                       user?.role === "lawyer"
//                         ? "/dashboard/lawyer"
//                         : "/dashboard/user"
//                     )
//                   }
//                   className="px-4 py-2 text-sm font-medium text-white bg-[#052379] rounded-lg hover:bg-[#041d5c] transition-colors"
//                 >
//                   Dashboard
//                 </button>

//                 <button
//                   onClick={() => {
//                     logout();
//                     localStorage.removeItem("access_token");
//                     localStorage.removeItem("user");
//                     router.push("/");
//                   }}
//                   className="px-4 py-2 text-sm font-medium text-gray-900 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
//                 >
//                   Logout
//                 </button>

//               </div>
//             )}
//           </div>

//         </div>
//       </div>
//     </header>
//   );
// }

"use client";

import { Scale, User, LogOut, LayoutDashboard } from "lucide-react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "../lib/authStore";
import { useEffect, useState } from "react";

export default function Navbar() {
  const router = useRouter();
  const { user, isLoggedIn, logout, login } = useAuthStore();

  const [open, setOpen] = useState(false);

  useEffect(() => {
    const savedUser = localStorage.getItem("user");
    const savedToken = localStorage.getItem("access_token");

    if (savedUser && savedToken) {
      login(JSON.parse(savedUser), savedToken);
    }
  }, [login]);

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
            <span className="text-xl font-semibold text-gray-900">
              Lawgic
            </span>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-4">

            <button className="px-4 py-2 text-sm font-medium text-gray-900 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors">
              EN ↔ اردو
            </button>

            {!isLoggedIn ? (
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
            ) : (
              <div className="relative">

                <button
                  onClick={() => setOpen(!open)}
                  className="flex items-center gap-2 px-3 py-2 bg-gray-100 rounded-lg hover:bg-gray-200"
                >
                  <User className="w-4 h-4" />
                  <span className="text-sm">{user?.email}</span>
                </button>

                {open && (
                  <div className="absolute right-0 mt-2 w-48 bg-white border border-gray-200 rounded-lg shadow-lg">

                    <button
                      onClick={() =>
                        router.push(
                          user?.role === "lawyer"
                            ? "/dashboard/lawyer"
                            : "/dashboard/user"
                        )
                      }
                      className="flex items-center gap-2 w-full px-4 py-2 text-sm hover:bg-gray-50"
                    >
                      <LayoutDashboard className="w-4 h-4" />
                      Dashboard
                    </button>

                    <button
                      onClick={() => {
                        logout();
                        localStorage.removeItem("access_token");
                        localStorage.removeItem("user");
                        router.push("/");
                      }}
                      className="flex items-center gap-2 w-full px-4 py-2 text-sm hover:bg-gray-50"
                    >
                      <LogOut className="w-4 h-4" />
                      Logout
                    </button>

                  </div>
                )}
              </div>
            )}

          </div>
        </div>
      </div>
    </header>
  );
}