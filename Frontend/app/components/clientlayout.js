"use client";

import { usePathname } from "next/navigation";
import Navbar from "./Navbar";
import SubNavbar from "./SubNavbar";
import Footer from "./Footer";

export default function ClientLayout({ children }) {
  const pathname = usePathname();

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
