"use client";

import { usePathname } from "next/navigation";
import Navbar from "./Navbar";
import SubNavbar from "./SubNavbar";
import Footer from "./Footer";
import { LanguageProvider } from "../lib/LanguageContext";

export default function ClientLayout({ children }) {
  const pathname = usePathname();

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
