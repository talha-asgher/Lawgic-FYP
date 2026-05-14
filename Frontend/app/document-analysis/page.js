"use client";

import React, { useState, useRef, useEffect, useCallback, useMemo } from "react";
import {
  Upload,
  FileText,
  X,
  Loader2,
  AlertCircle,
  FileWarning,
  ClipboardList,
  Info,
  FilePlus,
} from "lucide-react";
import {
  createDocumentAnalysis,
  getDocumentAnalysis,
} from "@/lib/api";
import { useLanguage } from "@/app/lib/LanguageContext";

const ACCEPT_EXT = [".pdf", ".docx", ".txt", ".png", ".jpg", ".jpeg", ".webp"];
const ACCEPT_MIME = new Set([
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "text/plain",
  "image/png",
  "image/jpeg",
  "image/webp",
]);

function normalizeUiOutputLang(lang) {
  if (!lang || typeof lang !== "string") return "en";
  const s = lang.trim().toLowerCase();
  if (s === "ur_latn" || s === "roman" || s === "roman_urdu") return "ur";
  return s === "ur" ? "ur" : "en";
}

/** Two user-visible steps; backend still sends analyzing_clauses / checking_risks / generating_suggestions. */
const STAGE_ORDER = ["extracting_text", "generating_summary"];

const STAGE_LABELS = {
  pending: "Queued…",
  extracting_text: "Extracting text…",
  generating_summary: "Generating summary…",
};

const SUMMARY_SUBSTAGES = new Set([
  "analyzing_clauses",
  "checking_risks",
  "generating_suggestions",
]);

/** Map API progress_stage to index in STAGE_ORDER (-1 = pending/queued). */
function stageToActiveIndex(stage) {
  if (stage === "pending" || stage == null) return -1;
  if (stage === "extracting_text") return 0;
  if (SUMMARY_SUBSTAGES.has(stage)) return 1;
  return 0;
}

function headlineForStage(stage) {
  if (stage === "pending" || stage == null) return STAGE_LABELS.pending;
  if (stage === "extracting_text") return STAGE_LABELS.extracting_text;
  if (SUMMARY_SUBSTAGES.has(stage)) return STAGE_LABELS.generating_summary;
  return STAGE_LABELS.pending;
}

function isAllowedFile(file) {
  if (!file) return false;
  const name = (file.name || "").toLowerCase();
  if (ACCEPT_EXT.some((ext) => name.endsWith(ext))) return true;
  if (file.type && ACCEPT_MIME.has(file.type)) return true;
  return false;
}

function parseAnalysisError(keyDetailsRaw) {
  if (!keyDetailsRaw || typeof keyDetailsRaw !== "string") return null;
  try {
    const o = JSON.parse(keyDetailsRaw);
    if (o && typeof o.error === "string") return o.error;
  } catch {
    /* ignore */
  }
  return null;
}

function isPdfFile(file) {
  if (!file) return false;
  const n = (file.name || "").toLowerCase();
  return file.type === "application/pdf" || n.endsWith(".pdf");
}

function AnalysisCard({ title, icon: Icon, children, accent }) {
  const accents = {
    blue: "border-l-sky-600 bg-sky-50/40",
    slate: "border-l-slate-400 bg-slate-50/60",
  };
  return (
    <section
      className={`rounded-xl border border-gray-100 shadow-sm border-l-4 pl-4 pr-4 py-4 ${accents[accent] || accents.slate}`}
    >
      <div className="flex items-center gap-2 mb-3">
        {Icon && <Icon className="w-5 h-5 text-gray-700 shrink-0" />}
        <h3 className="font-semibold text-gray-900 text-sm">{title}</h3>
      </div>
      <div className="text-gray-800">{children}</div>
    </section>
  );
}

function ProgressPanel({ stage }) {
  const activeIdx = stageToActiveIndex(stage);

  return (
    <div className="rounded-xl border border-[#052379]/20 bg-white p-6 shadow-sm">
      <Loader2 className="w-10 h-10 text-[#052379] animate-spin mx-auto mb-5" />
      <p className="text-center text-base font-medium text-gray-900 mb-1">
        {headlineForStage(stage)}
      </p>
      <p className="text-center text-xs text-gray-500 mb-6">
        Long documents are chunked and condensed before analysis.
      </p>
      <ol className="space-y-3 max-w-sm mx-auto">
        {STAGE_ORDER.map((key, i) => {
          const done = activeIdx >= 0 && i < activeIdx;
          const cur = activeIdx >= 0 && i === activeIdx;
          return (
            <li
              key={key}
              className={`flex items-center gap-3 text-sm rounded-lg px-3 py-2 transition-colors ${
                cur
                  ? "bg-[#052379]/10 text-[#052379] font-medium"
                  : done
                    ? "text-emerald-700"
                    : "text-gray-400"
              }`}
            >
              <span
                className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${
                  done
                    ? "bg-emerald-500 text-white"
                    : cur
                      ? "bg-[#052379] text-white"
                      : "bg-gray-200 text-gray-500"
                }`}
              >
                {done ? "✓" : i + 1}
              </span>
              <span>{STAGE_LABELS[key]}</span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

export default function DocumentAnalysisPage() {
  const { t } = useLanguage();
  const [isDragging, setIsDragging] = useState(false);
  const [file, setFile] = useState(null);
  const [outputLang, setOutputLang] = useState("en");
  const [currentJob, setCurrentJob] = useState(null);
  const [fromCache, setFromCache] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  const fileInputRef = useRef(null);

  const pdfObjectUrl = useMemo(() => {
    if (!file || !isPdfFile(file)) return null;
    return URL.createObjectURL(file);
  }, [file]);

  useEffect(() => {
    const url = pdfObjectUrl;
    if (!url) return;
    return () => URL.revokeObjectURL(url);
  }, [pdfObjectUrl]);

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile && isAllowedFile(droppedFile)) {
      handleFileSelection(droppedFile);
    } else {
      alert("Please upload a PDF, DOCX, TXT, or image (PNG, JPEG, WebP).");
    }
  };

  const handleFileSelect = (e) => {
    if (e.target.files && e.target.files[0]) {
      handleFileSelection(e.target.files[0]);
    }
  };

  async function handleFileSelection(selectedFile) {
    if (!isAllowedFile(selectedFile)) {
      alert("Please upload a PDF, DOCX, TXT, or image (PNG, JPEG, WebP).");
      return;
    }
    setFile(selectedFile);
    setUploadError(null);
    setCurrentJob(null);
    setFromCache(false);
    try {
      const job = await createDocumentAnalysis(selectedFile, outputLang);
      setFromCache(!!job.from_cache);
      setCurrentJob(job);
    } catch (err) {
      setUploadError(err?.message || "Upload failed");
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  const resetSession = useCallback(() => {
    setFile(null);
    setCurrentJob(null);
    setFromCache(false);
    setUploadError(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }, []);

  const loadNewDocument = useCallback(() => {
    resetSession();
    requestAnimationFrame(() => {
      fileInputRef.current?.click();
    });
  }, [resetSession]);

  const removeFile = resetSession;

  useEffect(() => {
    if (!currentJob?.analysis_id) return;
    const s = currentJob.status;
    if (s !== "pending" && s !== "processing") return;

    let cancelled = false;

    const tick = async () => {
      try {
        const data = await getDocumentAnalysis(currentJob.analysis_id);
        if (!cancelled) setCurrentJob(data);
      } catch {
        if (!cancelled) {
          setUploadError("Could not refresh analysis status. Try again.");
        }
      }
    };

    tick();
    const id = setInterval(tick, 1200);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
 }, [currentJob?.analysis_id, currentJob?.status]);

  const analyzing =
    currentJob &&
    (currentJob.status === "pending" || currentJob.status === "processing");
  const done = currentJob && currentJob.status === "done";
  const failed = currentJob && currentJob.status === "failed";
  const failMessage =
    failed && parseAnalysisError(currentJob.key_details);
  const result = currentJob?.result;
  const scriptDir =
    normalizeUiOutputLang((currentJob && currentJob.output_language) || outputLang) ===
    "ur"
      ? "rtl"
      : "ltr";

  const fileMeta = useMemo(() => {
    if (!file) return null;
    return (
      <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
        <div className="flex items-start gap-3">
          <div className="w-11 h-11 bg-red-50 text-red-500 rounded-lg flex items-center justify-center shrink-0">
            <FileText className="w-6 h-6" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium text-gray-900 truncate">{file.name}</p>
            <p className="text-xs text-gray-500 mt-0.5">
              {(file.size / 1024 / 1024).toFixed(2)} MB
              {currentJob?.file_hash && (
                <span className="ml-2 font-mono text-[10px] text-gray-400">
                  {currentJob.file_hash.slice(0, 12)}…
                </span>
              )}
            </p>
            {fromCache && (
              <p className="mt-2 text-xs font-medium text-emerald-700 bg-emerald-50 border border-emerald-100 rounded-md px-2 py-1 inline-block">
                Loaded from saved analysis (same file)
              </p>
            )}
          </div>
          {!analyzing && (
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-end shrink-0">
              <button
                type="button"
                onClick={loadNewDocument}
                className="inline-flex items-center justify-center gap-2 rounded-lg border border-[#052379] bg-white px-3 py-2 text-sm font-medium text-[#052379] hover:bg-[#052379]/5 transition-colors"
              >
                <FilePlus className="w-4 h-4 shrink-0" />
                New document
              </button>
              <button
                type="button"
                onClick={removeFile}
                className="p-2 hover:bg-gray-100 rounded-full text-gray-400 hover:text-gray-600"
                aria-label="Clear and close"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
          )}
          {analyzing && (
            <button
              type="button"
              onClick={loadNewDocument}
              className="inline-flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 shrink-0"
            >
              <FilePlus className="w-3.5 h-3.5" />
              Different file
            </button>
          )}
        </div>
        {pdfObjectUrl ? (
          <div className="mt-4 rounded-lg border border-gray-200 overflow-hidden bg-gray-100">
            <iframe
              title="PDF preview"
              src={`${pdfObjectUrl}#toolbar=0`}
              className="w-full h-[min(70vh,560px)] bg-white"
            />
          </div>
        ) : (
          <p className="mt-4 text-xs text-gray-500">
            Preview is available for PDF files. Other formats show metadata only.
          </p>
        )}
      </div>
    );
  }, [
    file,
    pdfObjectUrl,
    analyzing,
    currentJob,
    fromCache,
    loadNewDocument,
    removeFile,
  ]);

  return (
    <div className="w-full min-h-screen bg-[#F6F8FB] px-4 sm:px-6 lg:px-10 py-10">
      <div className="max-w-7xl mx-auto mb-8">
        <h1 className="text-3xl font-medium text-gray-900 mb-2">
          {t("docAnalysis.heading")}
        </h1>
        <p className="text-gray-600 max-w-2xl">
          Upload a legal document. Text is extracted (with OCR when needed), then
          analyzed into structured sections below.
        </p>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <span className="text-sm text-gray-600">Output language</span>
          <select
            value={outputLang}
            onChange={(e) => setOutputLang(e.target.value)}
            disabled={!!file}
            className="rounded-lg border border-gray-200 bg-white px-2.5 py-1.5 text-sm text-gray-800 focus:outline-none focus:ring-2 focus:ring-[#052379]/30 disabled:opacity-60"
            aria-label="Analysis output language"
          >
            <option value="en">English</option>
            <option value="ur">اردو</option>
          </select>
          {file && (
            <span className="text-xs text-gray-500">
              Clear the current file to change language
            </span>
          )}
        </div>
      </div>

      <div className="max-w-7xl mx-auto">
        <input
          type="file"
          ref={fileInputRef}
          className="hidden"
          tabIndex={-1}
          accept=".pdf,.docx,.txt,.png,.jpg,.jpeg,.webp,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain,image/png,image/jpeg,image/webp"
          onChange={handleFileSelect}
          aria-hidden
        />

        {!file && (
          <>
            <div
              className={`
              relative bg-white rounded-2xl border-2 border-dashed p-12 text-center transition-all cursor-pointer max-w-4xl mx-auto
              ${isDragging ? "border-[#052379] bg-blue-50/50" : "border-gray-300 hover:border-gray-400"}
            `}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => fileInputRef.current?.click()}
            >
              <div className="w-16 h-16 bg-[#052379]/10 text-[#052379] rounded-xl flex items-center justify-center mx-auto mb-6">
                <Upload className="w-8 h-8" />
              </div>

              <h3 className="text-lg font-medium text-gray-900 mb-2">
                Upload Document
              </h3>
              <p className="text-gray-500 text-sm">
                Drag and drop or{" "}
                <span className="text-[#052379] font-medium underline">
                  click to upload
                </span>{" "}
                (PDF, DOCX, TXT, or image)
              </p>
            </div>
            {uploadError && (
              <div className="mt-4 max-w-4xl mx-auto p-4 rounded-xl border border-red-200 bg-red-50 text-red-800 text-sm flex gap-2 items-start">
                <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
                <span>{uploadError}</span>
              </div>
            )}
          </>
        )}

        {file && (
          <div className="grid lg:grid-cols-2 gap-8 items-start">
            <div className="space-y-4 lg:sticky lg:top-8">{fileMeta}</div>

            <div className="space-y-5 min-h-50">
              {uploadError && (
                <div className="p-4 rounded-xl border border-amber-200 bg-amber-50 text-amber-900 text-sm flex gap-2 items-start">
                  <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
                  <span>{uploadError}</span>
                </div>
              )}

              {analyzing && (
                <ProgressPanel stage={currentJob?.progress_stage || "pending"} />
              )}

              {failed && (
                <div className="space-y-4">
                  <div className="p-4 rounded-xl border border-red-200 bg-red-50 text-red-900 text-sm flex gap-2 items-start">
                    <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
                    <div>
                      <p className="font-medium mb-1">Analysis failed</p>
                      <p>
                        {failMessage ||
                          "Something went wrong. Try another file or check the AI service."}
                      </p>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={loadNewDocument}
                    className="inline-flex w-full items-center justify-center gap-2 rounded-xl border border-[#052379] bg-white px-4 py-3 text-sm font-medium text-[#052379] hover:bg-[#052379]/5 transition-colors sm:w-auto"
                  >
                    <FilePlus className="w-4 h-4 shrink-0" />
                    Try a different document
                  </button>
                </div>
              )}

              {done && result && (
                <div className="space-y-4 animate-in fade-in duration-500">
                  <AnalysisCard
                    title="Document Type"
                    icon={ClipboardList}
                    accent="slate"
                  >
                    <p className="text-sm" dir={scriptDir}>
                      {result.document_type || "—"}
                    </p>
                  </AnalysisCard>

                  <AnalysisCard title="Quick Summary" icon={Info} accent="blue">
                    <div
                      dir={scriptDir}
                      className="text-sm leading-relaxed whitespace-pre-wrap text-gray-800"
                    >
                      {result.summary || "—"}
                    </div>
                  </AnalysisCard>

                  <AnalysisCard
                    title="Disclaimer"
                    icon={FileWarning}
                    accent="slate"
                  >
                    <p
                      className="text-sm text-gray-700 leading-relaxed"
                      dir={scriptDir}
                    >
                      {result.disclaimer}
                    </p>
                  </AnalysisCard>

                  <div className="pt-1">
                    <button
                      type="button"
                      onClick={loadNewDocument}
                      className="inline-flex w-full items-center justify-center gap-2 rounded-xl border border-[#052379] bg-[#052379] px-4 py-3 text-sm font-medium text-white hover:bg-[#041d5c] transition-colors sm:w-auto"
                    >
                      <FilePlus className="w-4 h-4 shrink-0" />
                      Analyze another document
                    </button>
                  </div>
                </div>
              )}

              {done && !result && (
                <div className="space-y-3">
                  <p className="text-sm text-gray-600">
                    Analysis finished but structured results were not available.
                  </p>
                  <button
                    type="button"
                    onClick={loadNewDocument}
                    className="inline-flex items-center gap-2 rounded-lg border border-[#052379] px-3 py-2 text-sm font-medium text-[#052379] hover:bg-[#052379]/5"
                  >
                    <FilePlus className="w-4 h-4" />
                    Analyze another document
                  </button>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
