"use client";

import React from "react";
import { Scale, MessageSquare, FileText, FileCheck, Users, Calculator, MapPin, ChevronRight } from "lucide-react";
import { useLanguage } from "./lib/LanguageContext";

export default function HomePage() {
  const { t, lang, toggleLanguage } = useLanguage();

  const router = {
    push: (path) => {
      window.location.href = path;
    }
  };

  const serviceKeys = [
    {
      icon: <MessageSquare className="w-6 h-6" />,
      key: "askAI",
      color: "bg-sky-500/10 text-sky-500",
      route: "/ai-qa"
    },
    {
      icon: <FileText className="w-6 h-6" />,
      key: "docAnalysis",
      color: "bg-blue-600/10 text-blue-600",
      route: "/document-analysis"
    },
    {
      icon: <FileCheck className="w-6 h-6" />,
      key: "docGen",
      color: "bg-emerald-500/10 text-emerald-500",
      route: "/document-generation"
    },
    {
      icon: <Users className="w-6 h-6" />,
      key: "searchLawyers",
      color: "bg-amber-500/10 text-amber-500",
      route: "/find-lawyers"
    },
    {
      icon: <Calculator className="w-6 h-6" />,
      key: "inheritance",
      color: "bg-red-500/10 text-red-500",
      route: "/inheritance-calculator"
    },
    {
      icon: <MapPin className="w-6 h-6" />,
      key: "institutions",
      color: "bg-sky-500/10 text-sky-500",
      route: "/institutions"
    }
  ];

  return (
    <div className="min-h-screen bg-white">
      <section className="relative bg-gradient-to-br from-[#023a54]/70 via-[#023a54]/40 to-white overflow-hidden">
        <div className="max-w-7xl mx-auto px-6 lg:px-12 py-24">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            <div className="space-y-8">
              <h1 className="text-5xl lg:text-6xl font-normal text-gray-900 leading-tight">
                {t("home.heading")}
              </h1>
              <p className="text-xl text-gray-700 leading-relaxed">
                {t("home.subheading")}
              </p>
              <div className="flex flex-wrap items-center gap-4">
                <button
                  onClick={() => router.push('/ai-qa')}
                  className="flex items-center gap-2 px-6 py-3 bg-[#052379] text-white rounded-lg font-medium hover:bg-[#041d5c] transition-colors"
                >
                  {t("home.askLegal")}
                  <ChevronRight className="w-4 h-4" />
                </button>
                <button
                  onClick={toggleLanguage}
                  className="px-6 py-3 bg-white text-gray-900 border border-gray-200 rounded-lg font-medium hover:bg-gray-50 transition-colors"
                >
                  {lang === "en" ? t("home.tryUrdu") : t("home.tryEnglish")}
                </button>
              </div>
            </div>

            <div className="relative">
              <div className="relative rounded-2xl overflow-hidden shadow-2xl aspect-[4/3]">
                <img
                  src="/homepage.png"
                  alt="Legal consultation"
                  className="w-full h-full object-cover"
                />
                <div className="absolute inset-0 bg-gradient-to-t from-blue-600/20 to-transparent" />
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="py-24 bg-white">
        <div className="max-w-7xl mx-auto px-6 lg:px-12">
          <h2 className="text-5xl font-normal text-gray-900 text-center mb-16">{t("home.ourServices")}</h2>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {serviceKeys.map((service, index) => (
              <div
                key={index}
                onClick={() => router.push(service.route)}
                className="group cursor-pointer p-6 bg-white border-2 border-gray-100 rounded-2xl hover:border-gray-200 hover:shadow-lg transition-all duration-300"
              >
                <div className={`w-12 h-12 ${service.color.split(" ")[0]} rounded-xl flex items-center justify-center mb-6`}>
                  <div className={service.color.split(" ")[1]}>
                    {service.icon}
                  </div>
                </div>

                <h3 className="text-lg font-normal text-gray-900 mb-2">{t(`home.services.${service.key}.title`)}</h3>
                <p className="text-gray-600 mb-6">{t(`home.services.${service.key}.desc`)}</p>

                <button className="flex items-center gap-2 text-sm font-medium text-gray-900 group-hover:gap-3 transition-all">
                  {t("home.view")}
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
