"use client";

import React from "react";
import { useRouter } from "next/navigation";
import { MessageSquare, FileText, FileCheck, Users, Calculator, MapPin, ChevronRight } from "lucide-react";
import { isLoggedIn } from "@/lib/api";

export default function HomePage() {
  const router = useRouter();

  const goToModule = (path) => {
    if (!isLoggedIn()) {
      router.push(`/login?next=${encodeURIComponent(path)}`);
      return;
    }
    router.push(path);
  };

  const services = [
    {
      icon: <MessageSquare className="w-6 h-6" />,
      title: "Ask AI",
      description: "Get instant answers to legal questions",
      color: "bg-sky-500/10 text-sky-500",
      route: "/ai-qa"
    },
    {
      icon: <FileText className="w-6 h-6" />,
      title: "Document Analysis",
      description: "Analyze contracts and legal documents",
      color: "bg-blue-600/10 text-blue-600",
      route: "/document-analysis"
    },
    {
      icon: <FileCheck className="w-6 h-6" />,
      title: "Document Generation",
      description: "Create legal documents with templates",
      color: "bg-emerald-500/10 text-emerald-500",
      route: "/document-generation"
    },
    {
      icon: <Users className="w-6 h-6" />,
      title: "Search Lawyers",
      description: "Find verified legal professionals",
      color: "bg-amber-500/10 text-amber-500",
      route: "/find-lawyers"
    },
    {
      icon: <Calculator className="w-6 h-6" />, 
      title: "Inheritance Calculator",
      description: "Calculate Islamic inheritance shares",
      color: "bg-red-500/10 text-red-500",
      route: "/inheritance-calculator"
    },
    {
      icon: <MapPin className="w-6 h-6" />,
      title: "Nearby Legal Institutions",
      description: "Find courts, police stations & more",
      color: "bg-sky-500/10 text-sky-500",
      route: "/institutions"
    }
  ];

  return (
    <div className="min-h-screen bg-white">
      {/* main Section */}
      <section className="relative bg-gradient-to-br from-[#023a54]/70 via-[#023a54]/40 to-white overflow-hidden">
        <div className="max-w-7xl mx-auto px-6 lg:px-12 py-24">
          <div className="grid lg:grid-cols-2 gap-12 items-center">
            {/* Content */}
            <div className="space-y-8">
              <h1 className="text-5xl lg:text-6xl font-normal text-gray-900 leading-tight">
                Simplifying Law for Everyone in Pakistan
              </h1>
              <p className="text-xl text-gray-700 leading-relaxed">
                Get instant legal guidance, analyze documents, and connect with verified lawyers — all powered by AI
              </p>
              <div className="flex flex-wrap items-center gap-4">
                <button 
                  onClick={() => goToModule("/ai-qa")}
                  className="flex items-center gap-2 px-6 py-3 bg-[#052379] text-white rounded-lg font-medium hover:bg-[#041d5c] transition-colors"
                >
                  Ask a Legal Question
                  <ChevronRight className="w-4 h-4" />
                </button>
                <button className="px-6 py-3 bg-white text-gray-900 border border-gray-200 rounded-lg font-medium hover:bg-gray-50 transition-colors">
                  Try in Urdu
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

      {/* Services Section */}
      <section className="py-24 bg-white">
        <div className="max-w-7xl mx-auto px-6 lg:px-12">
          <h2 className="text-5xl font-normal text-gray-900 text-center mb-16">Our Services</h2>
          
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {services.map((service, index) => (
              <div 
                key={index}
            
                onClick={() => goToModule(service.route)}
                className="group cursor-pointer p-6 bg-white border-2 border-gray-100 rounded-2xl hover:border-gray-200 hover:shadow-lg transition-all duration-300"
              >
                <div className={`w-12 h-12 ${service.color.split(" ")[0]} rounded-xl flex items-center justify-center mb-6`}>
                  <div className={service.color.split(" ")[1]}>
                    {service.icon}
                  </div>
                </div>
                
                <h3 className="text-lg font-normal text-gray-900 mb-2">{service.title}</h3>
                <p className="text-gray-600 mb-6">{service.description}</p>
                
                <button className="flex items-center gap-2 text-sm font-medium text-gray-900 group-hover:gap-3 transition-all">
                  View
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