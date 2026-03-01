"use client";

import React, { useState } from 'react';
import { 
  Scale, 
  FileText, 
  FilePlus, 
  Files, 
  FileWarning, 
  ChevronRight, 
  Search 
} from 'lucide-react';

export default function DocumentGenerationPage() {
  const router = {
    push: (path) => {
      console.log(`Navigating to: ${path}`);
      window.location.href = path;
    }
  };

  const [activeTab, setActiveTab] = useState('doc-gen');

  const templates = [
    {
      title: "FIR (First Information Report)",
      icon: <FileWarning className="w-8 h-8 text-red-500" />,
      color: "bg-red-500/10",
      border: "hover:border-red-200",
      description: "Draft a police complaint for cognizable offenses"
    },
    {
      title: "Tenancy Agreement",
      icon: <FileText className="w-8 h-8 text-blue-600" />,
      color: "bg-blue-600/10",
      border: "hover:border-blue-200",
      description: "Standard rental agreement for landlords and tenants"
    },
    {
      title: "Divorce Notice",
      icon: <Files className="w-8 h-8 text-amber-500" />,
      color: "bg-amber-500/10",
      border: "hover:border-amber-200",
      description: "Legal notice for dissolution of marriage"
    },
    {
      title: "Custom Document",
      icon: <FilePlus className="w-8 h-8 text-sky-500" />,
      color: "bg-sky-500/10",
      border: "hover:border-sky-200",
      description: "Create a custom legal document from scratch"
    }
  ];

  const navItems = [
    { name: 'Home', route: '/' },
    { name: 'AI Q&A', route: '/ai-qa' },
    { name: 'Document Analysis', route: '/document-analysis' },
    { name: 'Document Generation', route: '/document-generation', active: true },
    { name: 'Find Lawyers', route: '/find-lawyers' },
    { name: 'Institutions', route: '/institutions' },
    { name: 'Inheritance Calculator', route: '/inheritance-calculator' }
  ];

  return (
    <div className="min-h-screen bg-white flex flex-col">
     
      {/* Main Content */}
      <main className="flex-1 bg-[#F6F8FB]">
        <div className="max-w-7xl mx-auto px-6 lg:px-12 py-12">
          
          <div className="mb-8">
            <h1 className="text-3xl font-medium text-gray-900 mb-2">Document Generation</h1>
            <p className="text-gray-600">Create legal documents using our verified templates</p>
          </div>

          <div className="mb-10 relative max-w-lg">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input 
              type="text" 
              placeholder="Search for a template (e.g. Affidavit, Lease)..." 
              className="w-full pl-12 pr-4 py-3 bg-white border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#052379]/20 focus:border-[#052379] transition-all"
            />
          </div>

          {/* Templates */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {templates.map((template, index) => (
              <div 
                key={index}
                className={`group bg-white rounded-2xl p-6 border-2 border-transparent ${template.border} shadow-sm hover:shadow-md transition-all duration-300 cursor-pointer flex flex-col`}
              >
                <div className={`w-16 h-16 rounded-xl flex items-center justify-center mb-6 ${template.color}`}>
                  {template.icon}
                </div> 
                <div className="flex-1">
                  <h3 className="text-lg font-medium text-gray-900 mb-2 line-clamp-1">
                    {template.title}
                  </h3>
                  <p className="text-sm text-gray-500 mb-6 line-clamp-2">
                    {template.description}
                  </p>
                </div>

                <button className="flex items-center gap-2 text-sm font-medium text-gray-900 group-hover:gap-3 transition-all mt-auto">
                  Start Draft
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>

        </div>
      </main>

     
    </div>
  );
}