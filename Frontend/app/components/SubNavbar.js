"use client";

import { Home, Brain, FileText, FileCheck, Users, MapPin, Calculator, Briefcase, MessageSquare, Calendar } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuthStore } from "../lib/authStore";
import { useLanguage } from "../lib/LanguageContext";

export default function SubNavbar() {
  const pathname = usePathname();
  const { user } = useAuthStore();
  const { t } = useLanguage();
  const role = user?.role;

  const clientItems = [
    { icon: <Home className="w-4 h-4" />, labelKey: "subNav.home", href: "/" },
    { icon: <Brain className="w-4 h-4" />, labelKey: "subNav.aiQA", href: "/ai-qa" },
    { icon: <FileText className="w-4 h-4" />, labelKey: "subNav.documentAnalysis", href: "/document-analysis" },
    { icon: <FileCheck className="w-4 h-4" />, labelKey: "subNav.documentGeneration", href: "/document-generation" },
    { icon: <Users className="w-4 h-4" />, labelKey: "subNav.findLawyers", href: "/find-lawyers" },
    { icon: <Briefcase className="w-4 h-4" />, labelKey: "subNav.myCases", href: "/cases" },
    { icon: <Calendar className="w-4 h-4" />, labelKey: "subNav.appointments", href: "/appointments" },
    { icon: <MessageSquare className="w-4 h-4" />, labelKey: "subNav.messages", href: "/chat" },
    { icon: <MapPin className="w-4 h-4" />, labelKey: "subNav.institutions", href: "/institiutions" },
    { icon: <Calculator className="w-4 h-4" />, labelKey: "subNav.inheritanceCalculator", href: "/inheritance-calculator" },
  ];

  const lawyerItems = [
    { icon: <Home className="w-4 h-4" />, labelKey: "subNav.home", href: "/" },
    { icon: <Brain className="w-4 h-4" />, labelKey: "subNav.aiQA", href: "/ai-qa" },
    { icon: <FileText className="w-4 h-4" />, labelKey: "subNav.documentAnalysis", href: "/document-analysis" },
    { icon: <FileCheck className="w-4 h-4" />, labelKey: "subNav.documentGeneration", href: "/document-generation" },
    { icon: <Briefcase className="w-4 h-4" />, labelKey: "subNav.myCases", href: "/cases" },
    { icon: <Calendar className="w-4 h-4" />, labelKey: "subNav.appointments", href: "/appointments" },
    { icon: <MessageSquare className="w-4 h-4" />, labelKey: "subNav.messages", href: "/chat" },
    { icon: <MapPin className="w-4 h-4" />, labelKey: "subNav.institutions", href: "/institiutions" },
    { icon: <Calculator className="w-4 h-4" />, labelKey: "subNav.inheritanceCalculator", href: "/inheritance-calculator" },
  ];

  const navItems = role === "lawyer" ? lawyerItems : clientItems;

  return (
    <nav className="border-b border-gray-200 bg-white sticky top-20 z-40">
      <div className="max-w-7xl mx-auto px-6 lg:px-12">
        <div className="flex flex-wrap items-center justify-between gap-1 py-2">
          {navItems.map((item, index) => {
            const isActive = pathname === item.href;
            pathname.startsWith(item.href + "/");

            return (
              <Link
                key={index}
                href={item.href}
                className={`
                  flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-medium whitespace-nowrap
                  transition-colors text-gray-700 hover:bg-gray-100
                  ${isActive ? "bg-gray-100 font-semibold text-gray-900" : ""}
                `}
              >
                {item.icon}
                <span>{t(item.labelKey)}</span>
              </Link>
            );
          })}
        </div>
      </div>
    </nav>
  );
}
