"use client";

import { usePathname } from "next/navigation";
import Navbar from "./Navbar";
import SubNavbar from "./SubNavbar";
import Footer from "./Footer";

export default function ClientLayout({ children }) {
  const pathname = usePathname();

  const hideSubAndFooter =
    pathname.startsWith("/login") ||
    pathname.startsWith("/register");

  return (
    <>
      
      {!hideSubAndFooter && <Navbar />}
      {!hideSubAndFooter && <SubNavbar />}
      <main>{children}</main>
      {!hideSubAndFooter && <Footer />}
    </>
  );
}
