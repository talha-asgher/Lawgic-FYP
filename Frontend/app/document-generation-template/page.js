"use client";

import React, { useState, useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  ChevronLeft, ChevronRight, Download,
  Loader2, CheckCircle2, AlertCircle, FileText, LogIn,
} from "lucide-react";
import { DOCUMENT_TEMPLATES, TEMPLATE_COLORS } from "../lib/documentTemplates";
import { getToken } from "@/lib/api";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ─── Field Renderer ───────────────────────────────────────────────────────────
function FormField({ field, value, onChange, error }) {
  const base = "w-full px-4 py-2.5 bg-white border rounded-xl text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-[#052379]/20 focus:border-[#052379] transition-all";
  const err  = error ? "border-red-400" : "border-gray-200";
  const handle = (e) => onChange(field.name, e.target.value);

  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-sm font-medium text-gray-700">
        {field.label}
        {field.required && <span className="text-red-500 ml-1">*</span>}
      </label>
      {field.type === "textarea" ? (
        <textarea rows={3} value={value || ""} onChange={handle}
          placeholder={field.placeholder || ""}
          className={`${base} ${err} resize-none`} />
      ) : field.type === "select" ? (
        <select value={value || ""} onChange={handle} className={`${base} ${err}`}>
          <option value="">Select an option...</option>
          {field.options?.map((opt) => <option key={opt} value={opt}>{opt}</option>)}
        </select>
      ) : (
        <input type={field.type} value={value || ""} onChange={handle}
          placeholder={field.placeholder || ""}
          className={`${base} ${err}`} />
      )}
      {error && (
        <p className="text-xs text-red-500 flex items-center gap-1">
          <AlertCircle className="w-3 h-3" /> {error}
        </p>
      )}
    </div>
  );
}

// ─── Step Indicator ───────────────────────────────────────────────────────────
function StepIndicator({ sections, currentSection, completedSections }) {
  return (
    <div className="flex items-center gap-2 mb-8 overflow-x-auto pb-1">
      {sections.map((section, idx) => {
        const isActive = idx === currentSection;
        const isDone   = completedSections.has(idx);
        return (
          <React.Fragment key={idx}>
            <div className="flex items-center gap-2 shrink-0">
              <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold border-2 transition-all ${
                isActive ? "bg-[#052379] border-[#052379] text-white"
                : isDone  ? "bg-green-500 border-green-500 text-white"
                : "bg-white border-gray-200 text-gray-400"
              }`}>
                {isDone && !isActive ? <CheckCircle2 className="w-4 h-4" /> : idx + 1}
              </div>
              <span className={`text-xs font-medium hidden sm:block ${
                isActive ? "text-[#052379]" : isDone ? "text-green-600" : "text-gray-400"
              }`}>{section.heading}</span>
            </div>
            {idx < sections.length - 1 && (
              <div className={`h-0.5 flex-1 min-w-4 ${isDone ? "bg-green-400" : "bg-gray-200"}`} />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}

// ─── Not Logged In Screen ─────────────────────────────────────────────────────
function NotLoggedInScreen({ onLogin }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="w-16 h-16 rounded-full bg-amber-100 flex items-center justify-center mb-4">
        <LogIn className="w-8 h-8 text-amber-600" />
      </div>
      <h2 className="text-xl font-semibold text-gray-900 mb-2">Login Required</h2>
      <p className="text-gray-500 mb-6 max-w-sm text-sm">
        You need to be logged in to generate and save legal documents to your account.
      </p>
      <button onClick={onLogin}
        className="bg-[#052379] text-white px-6 py-3 rounded-xl text-sm font-medium hover:bg-[#052379]/90 transition-all">
        Go to Login
      </button>
    </div>
  );
}

// ─── Success Screen ───────────────────────────────────────────────────────────
function SuccessScreen({ template, docId, docTitle, onReset, onDownload, isDownloading }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="w-20 h-20 rounded-full bg-green-100 flex items-center justify-center mb-6">
        <CheckCircle2 className="w-10 h-10 text-green-600" />
      </div>
      <h2 className="text-2xl font-semibold text-gray-900 mb-2">Document Generated!</h2>
      <p className="text-gray-500 mb-2 max-w-sm">
        Your <strong>{template.title}</strong> has been saved to your account.
      </p>
      <p className="text-xs text-gray-400 mb-8">Document ID: #{docId}</p>

      <div className="bg-gray-50 border border-gray-200 rounded-2xl p-5 w-full max-w-sm mb-8">
        <div className="flex items-center gap-4">
          <div className="w-12 h-14 bg-red-100 rounded-lg flex items-center justify-center">
            <FileText className="w-6 h-6 text-red-500" />
          </div>
          <div className="text-left">
            <p className="font-medium text-gray-900 text-sm">{docTitle}</p>
            <p className="text-xs text-gray-400 mt-0.5">PDF · Saved to your account</p>
          </div>
        </div>
      </div>

      <div className="flex gap-3 flex-wrap justify-center">
        <button onClick={onDownload} disabled={isDownloading}
          className="flex items-center gap-2 bg-[#052379] text-white px-6 py-3 rounded-xl text-sm font-medium hover:bg-[#052379]/90 transition-all disabled:opacity-60">
          {isDownloading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Download className="w-4 h-4" />}
          {isDownloading ? "Downloading..." : "Download PDF"}
        </button>
        <button onClick={onReset}
          className="px-6 py-3 rounded-xl text-sm font-medium border border-gray-200 text-gray-700 hover:bg-gray-50 transition-all">
          Generate Another
        </button>
      </div>
    </div>
  );
}

// ─── Main Page ─────────────────────────────────────────────────────────────────
export default function DocumentFormPage() {
  const router       = useRouter();
  const searchParams = useSearchParams();
  const templateKey  = searchParams.get("type");
  const template     = templateKey ? DOCUMENT_TEMPLATES[templateKey] : null;
  const colors       = template ? TEMPLATE_COLORS[template.color] || TEMPLATE_COLORS.blue : null;

  const [currentSection,    setCurrentSection]    = useState(0);
  const [formData,          setFormData]          = useState({});
  const [errors,            setErrors]            = useState({});
  const [completedSections, setCompletedSections] = useState(new Set());
  const [isSubmitting,      setIsSubmitting]      = useState(false);
  const [isSuccess,         setIsSuccess]         = useState(false);
  const [isDownloading,     setIsDownloading]     = useState(false);
  const [generatedDocId,    setGeneratedDocId]    = useState(null);
  const [generatedDocTitle, setGeneratedDocTitle] = useState("");
  const [submitError,       setSubmitError]       = useState("");
  const [notLoggedIn,       setNotLoggedIn]       = useState(false);

  const handleFieldChange = useCallback((name, value) => {
    setFormData((prev) => ({ ...prev, [name]: value }));
    setErrors((prev) => { const u = { ...prev }; delete u[name]; return u; });
  }, []);

  const validateSection = (idx) => {
    const section = template.sections[idx];
    const errs = {};
    section.fields.forEach((f) => {
      if (f.required && !formData[f.name]?.toString().trim()) {
        errs[f.name] = `${f.label} is required`;
      }
    });
    return errs;
  };

  const handleNext = () => {
    const errs = validateSection(currentSection);
    if (Object.keys(errs).length > 0) { setErrors(errs); return; }
    setCompletedSections((p) => new Set([...p, currentSection]));
    setCurrentSection((p) => p + 1);
    setErrors({});
  };

  const handleBack = () => {
    if (currentSection === 0) router.push("/document-generation");
    else { setCurrentSection((p) => p - 1); setErrors({}); }
  };

  const handleSubmit = async () => {
    const errs = validateSection(currentSection);
    if (Object.keys(errs).length > 0) { setErrors(errs); return; }

    const token = getToken();
    if (!token) { setNotLoggedIn(true); return; }

    setCompletedSections((p) => new Set([...p, currentSection]));
    setIsSubmitting(true);
    setSubmitError("");

    try {
      const res = await fetch(`${API_BASE_URL}/documents/generate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`,
        },
        body: JSON.stringify({ template_type: templateKey, form_data: formData }),
      });

      if (res.status === 401) { setNotLoggedIn(true); setIsSubmitting(false); return; }

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to generate document");
      }

      const data = await res.json();
      setGeneratedDocId(data.document_id);
      setGeneratedDocTitle(data.title);
      setIsSuccess(true);
    } catch (err) {
      setSubmitError(err.message || "Something went wrong. Please try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDownload = async () => {
    if (!generatedDocId) return;
    const token = getToken();
    if (!token) { setNotLoggedIn(true); return; }
    setIsDownloading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/documents/download/${generatedDocId}`, {
        headers: { "Authorization": `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Download failed");
      const blob = await res.blob();
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement("a");
      a.href = url;
      a.download = `${templateKey}_${generatedDocId}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      alert("Download failed: " + err.message);
    } finally {
      setIsDownloading(false);
    }
  };

  const handleReset = () => {
    setFormData({}); setErrors({}); setCurrentSection(0);
    setCompletedSections(new Set()); setIsSuccess(false);
    setGeneratedDocId(null); setSubmitError(""); setNotLoggedIn(false);
  };

  if (!template) {
    return (
      <div className="min-h-screen bg-[#F6F8FB] flex items-center justify-center">
        <div className="text-center">
          <h2 className="text-2xl font-semibold text-gray-900 mb-2">Template Not Found</h2>
          <p className="text-gray-500 mb-6">Please go back and select a valid template.</p>
          <button onClick={() => router.push("/document-generation")}
            className="bg-[#052379] text-white px-6 py-3 rounded-xl text-sm font-medium">
            Back to Templates
          </button>
        </div>
      </div>
    );
  }

  const currentSectionData = template.sections[currentSection];
  const isLastSection      = currentSection === template.sections.length - 1;

  return (
    <div className="min-h-screen bg-[#F6F8FB]">
      <div className="max-w-3xl mx-auto px-4 sm:px-6 py-10">

        <button onClick={() => router.push("/document-generation")}
          className="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-900 mb-6 transition-colors">
          <ChevronLeft className="w-4 h-4" /> Back to Templates
        </button>

        {/* Header */}
        <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100 mb-6">
          <div className="flex items-start gap-4">
            <div className={`w-12 h-12 rounded-xl flex items-center justify-center shrink-0 ${colors.bg} ${colors.icon}`}>
              <FileText className="w-6 h-6" />
            </div>
            <div className="flex-1 min-w-0">
              <h1 className="text-xl font-semibold text-gray-900 mb-0.5">{template.title}</h1>
              <p className="text-sm text-gray-500">{template.subtitle}</p>
              <span className={`inline-block mt-2 text-xs px-2.5 py-1 rounded-full font-medium ${colors.badge}`}>
                {template.legalBasis}
              </span>
            </div>
          </div>
        </div>

        {/* Form Card */}
        <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
          {notLoggedIn ? (
            <NotLoggedInScreen onLogin={() => router.push("/login")} />
          ) : isSuccess ? (
            <SuccessScreen
              template={template}
              docId={generatedDocId}
              docTitle={generatedDocTitle}
              onReset={handleReset}
              onDownload={handleDownload}
              isDownloading={isDownloading}
            />
          ) : (
            <>
              <StepIndicator
                sections={template.sections}
                currentSection={currentSection}
                completedSections={completedSections}
              />

              <div className="mb-6">
                <h2 className="text-lg font-semibold text-gray-900">{currentSectionData.heading}</h2>
                <p className="text-sm text-gray-400 mt-0.5">
                  Step {currentSection + 1} of {template.sections.length}
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-5 mb-8">
                {currentSectionData.fields.map((field) => (
                  <div key={field.name} className={field.type === "textarea" ? "sm:col-span-2" : ""}>
                    <FormField field={field} value={formData[field.name]}
                      onChange={handleFieldChange} error={errors[field.name]} />
                  </div>
                ))}
              </div>

              {submitError && (
                <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-xl flex items-center gap-2 text-sm text-red-700">
                  <AlertCircle className="w-4 h-4 shrink-0" /> {submitError}
                </div>
              )}

              <div className="flex justify-between items-center pt-4 border-t border-gray-100">
                <button onClick={handleBack}
                  className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-medium border border-gray-200 text-gray-700 hover:bg-gray-50 transition-all">
                  <ChevronLeft className="w-4 h-4" />
                  {currentSection === 0 ? "Cancel" : "Back"}
                </button>

                {isLastSection ? (
                  <button onClick={handleSubmit} disabled={isSubmitting}
                    className="flex items-center gap-2 bg-[#052379] text-white px-6 py-2.5 rounded-xl text-sm font-medium hover:bg-[#052379]/90 transition-all disabled:opacity-60">
                    {isSubmitting
                      ? <><Loader2 className="w-4 h-4 animate-spin" /> Generating...</>
                      : <><Download className="w-4 h-4" /> Generate & Save PDF</>}
                  </button>
                ) : (
                  <button onClick={handleNext}
                    className="flex items-center gap-2 bg-[#052379] text-white px-6 py-2.5 rounded-xl text-sm font-medium hover:bg-[#052379]/90 transition-all">
                    Next <ChevronRight className="w-4 h-4" />
                  </button>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}