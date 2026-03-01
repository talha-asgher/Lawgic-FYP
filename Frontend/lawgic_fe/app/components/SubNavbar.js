"use client";

import { Home, Brain, FileText, FileCheck, Users, MapPin, Calculator } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

export default function SubNavbar() {
  const pathname = usePathname();

  const navItems = [
    { icon: <Home className="w-4 h-4" />, label: "Home", href: "/" },
    { icon: <Brain className="w-4 h-4" />, label: "AI Q&A", href: "/ai-qa" },
    { icon: <FileText className="w-4 h-4" />, label: "Document Analysis", href: "/document-analysis" },
    { icon: <FileCheck className="w-4 h-4" />, label: "Document Generation", href: "/document-generation" },
    { icon: <Users className="w-4 h-4" />, label: "Find Lawyers", href: "/find-lawyers" },
    { icon: <MapPin className="w-4 h-4" />, label: "Institutions", href: "/institiutions" },
    { icon: <Calculator className="w-4 h-4" />, label: "Inheritance Calculator", href: "/inheritance-calculator" },
  ];

  return (
    <nav className="border-b border-gray-200 bg-white sticky top-20 z-40">
      <div className="max-w-7xl mx-auto px-6 lg:px-12">
        <div className="flex items-center gap-2 py-3 overflow-x-auto">
          {navItems.map((item, index) => {
            const isActive = pathname === item.href;

            return (
              <Link
                key={index}
                href={item.href}
                className={`
                  flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium whitespace-nowrap 
                  transition-colors
                  text-gray-700 hover:bg-gray-100
                  ${isActive ? "bg-gray-100 font-semibold text-gray-900" : ""}
                `}
              >
                {item.icon}
                <span>{item.label}</span>
              </Link>
            );
          })}
        </div>
      </div>
    </nav>
  );
}
