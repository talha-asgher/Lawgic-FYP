
"use client";

import React, { useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import { FileText, FilePlus, Files, FileWarning, ChevronRight, Search, FileSignature, Gavel, ScrollText,} from "lucide-react";
import { TEMPLATE_LIST, TEMPLATE_COLORS } from "../lib/documentTemplates";

const TEMPLATE_ICONS = {
  fir:          <FileWarning className="w-8 h-8" />,
  tenancy:      <FileText className="w-8 h-8" />,
  divorce:      <Files className="w-8 h-8" />,
  affidavit:    <ScrollText className="w-8 h-8" />,
  poa:          <FileSignature className="w-8 h-8" />,
  legal_notice: <Gavel className="w-8 h-8" />,
};

export default function DocumentGenerationPage() {
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState("");

  const filteredTemplates = useMemo(() => {
    if (!searchQuery.trim()) return TEMPLATE_LIST;
    const q = searchQuery.toLowerCase();
    return TEMPLATE_LIST.filter(
      (t) =>
        t.title.toLowerCase().includes(q) ||
        t.subtitle.toLowerCase().includes(q) ||
        t.legalBasis.toLowerCase().includes(q)
    );
  }, [searchQuery]);

  // ✅ Navigate using query param — matches your folder name
  const handleTemplateClick = (templateKey) => {
    router.push(`/document-generation-template?type=${templateKey}`);
  };

  return (
    <div className="min-h-screen bg-white flex flex-col">
      <main className="flex-1 bg-[#F6F8FB]">
        <div className="max-w-7xl mx-auto px-6 lg:px-12 py-12">

          {/* Header */}
          <div className="mb-8">
            <h1 className="text-3xl font-medium text-gray-900 mb-2">Document Generation</h1>
            <p className="text-gray-600">Create legal documents using our verified templates</p>
          </div>

          {/* Search */}
          <div className="mb-10 relative max-w-lg">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search for a template (e.g. Affidavit, Lease)..."
              className="w-full pl-12 pr-4 py-3 bg-white border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#052379]/20 focus:border-[#052379] transition-all"
            />
          </div>

          {/* Templates Grid */}
          {filteredTemplates.length === 0 ? (
            <div className="text-center py-16">
              <p className="text-gray-400 text-lg">No templates found for "{searchQuery}"</p>
              <button
                onClick={() => setSearchQuery("")}
                className="mt-3 text-[#052379] text-sm hover:underline"
              >
                Clear search
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
              {filteredTemplates.map((template) => {
                const colors = TEMPLATE_COLORS[template.color] || TEMPLATE_COLORS.blue;
                const Icon = TEMPLATE_ICONS[template.key];

                return (
                  <div
                    key={template.key}
                    onClick={() => handleTemplateClick(template.key)}
                    className={`group bg-white rounded-2xl p-6 border-2 border-transparent ${colors.border} shadow-sm hover:shadow-md transition-all duration-300 cursor-pointer flex flex-col`}
                  >
                    <div className={`w-16 h-16 rounded-xl flex items-center justify-center mb-5 ${colors.bg} ${colors.icon}`}>
                      {Icon || <FileText className="w-8 h-8" />}
                    </div>

                    <div className="flex-1">
                      <h3 className="text-base font-semibold text-gray-900 mb-1 line-clamp-2">
                        {template.title}
                      </h3>
                      <p className="text-xs text-gray-500 mb-3 line-clamp-2">
                        {template.subtitle}
                      </p>
                      <span className={`inline-block text-xs px-2 py-0.5 rounded-full font-medium ${colors.badge}`}>
                        {template.legalBasis}
                      </span>
                    </div>

                    <button className="flex items-center gap-1 text-sm font-medium text-gray-900 group-hover:gap-2 transition-all mt-5">
                      Start Draft
                      <ChevronRight className="w-4 h-4" />
                    </button>
                  </div>
                );
              })}

              {/* Custom Document Card */}
              <div
                onClick={() => handleTemplateClick("custom")}
                className="group bg-white rounded-2xl p-6 border-2 border-dashed border-gray-200 hover:border-[#052379]/40 shadow-sm hover:shadow-md transition-all duration-300 cursor-pointer flex flex-col"
              >
                <div className="w-16 h-16 rounded-xl flex items-center justify-center mb-5 bg-[#052379]/5 text-[#052379]">
                  <FilePlus className="w-8 h-8" />
                </div>
                <div className="flex-1">
                  <h3 className="text-base font-semibold text-gray-900 mb-1">Custom Document</h3>
                  <p className="text-xs text-gray-500 mb-3">Create a custom legal document from scratch</p>
                  <span className="inline-block text-xs px-2 py-0.5 rounded-full font-medium bg-gray-100 text-gray-600">
                    AI-Assisted
                  </span>
                </div>
                <button className="flex items-center gap-1 text-sm font-medium text-gray-900 group-hover:gap-2 transition-all mt-5">
                  Start Draft
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}
        </div>
      </main>
    </div>
  );
}