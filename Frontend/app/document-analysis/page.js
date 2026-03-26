"use client";

import React, { useState, useRef } from 'react';
import {
  Upload,
  FileText,
  X,
  CheckCircle,
  Loader2,
  AlertCircle,
  ShieldAlert,
  Info
} from 'lucide-react';
import { useLanguage } from '@/app/lib/LanguageContext';

export default function DocumentAnalysisPage() {
  const { t } = useLanguage();
  const [isDragging, setIsDragging] = useState(false);
  const [file, setFile] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState(null);
  const fileInputRef = useRef(null);

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
    if (droppedFile && droppedFile.type === 'application/pdf') {
      handleFileSelection(droppedFile);
    } else {
      alert(t("docAnalysis.pdfOnly"));
    }
  };

  const handleFileSelect = (e) => {
    if (e.target.files && e.target.files[0]) {
      handleFileSelection(e.target.files[0]);
    }
  };

  const handleFileSelection = (selectedFile) => {
    setFile(selectedFile);
    setAnalysisResult(null);
  };

  const removeFile = () => {
    setFile(null);
    setAnalysisResult(null);
    setAnalyzing(false);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  return (
    <div className="w-full min-h-screen bg-[#F6F8FB] px-6 lg:px-12 py-12">

      <div className="max-w-4xl mx-auto mb-10">
        <h1 className="text-3xl font-medium text-gray-900 mb-2">
          {t("docAnalysis.heading")}
        </h1>
        <p className="text-gray-600">
          {t("docAnalysis.subtitle")}
        </p>
      </div>

      <div className="max-w-4xl mx-auto">

        {!file && (
          <div
            className={`
              relative bg-white rounded-2xl border-2 border-dashed p-12 text-center transition-all cursor-pointer
              ${isDragging ? 'border-[#052379] bg-blue-50/50' : 'border-gray-300 hover:border-gray-400'}
            `}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
          >
            <input
              type="file"
              ref={fileInputRef}
              className="hidden"
              accept="application/pdf"
              onChange={handleFileSelect}
            />

            <div className="w-16 h-16 bg-[#052379]/10 text-[#052379] rounded-xl flex items-center justify-center mx-auto mb-6">
              <Upload className="w-8 h-8" />
            </div>

            <h3 className="text-lg font-medium text-gray-900 mb-2">
              {t("docAnalysis.uploadHeading")}
            </h3>
            <p className="text-gray-500 text-sm">
              {t("docAnalysis.uploadHint", { clickLink: <span className="text-[#052379] font-medium underline">{t("docAnalysis.clickToUpload")}</span> })}
            </p>
          </div>
        )}

        {file && (
          <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm">

            <div className="flex items-center justify-between mb-6 pb-6 border-b border-gray-100">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 bg-red-50 text-red-500 rounded-lg flex items-center justify-center">
                  <FileText className="w-6 h-6" />
                </div>
                <div>
                  <h4 className="text-sm font-medium text-gray-900">{file.name}</h4>
                  <p className="text-xs text-gray-500">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
                </div>
              </div>

              {!analyzing && (
                <button
                  onClick={removeFile}
                  className="p-2 hover:bg-gray-100 rounded-full text-gray-400 hover:text-gray-600 transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              )}
            </div>

            {analyzing && (
              <div className="py-12 text-center">
                <Loader2 className="w-10 h-10 text-[#052379] animate-spin mx-auto mb-4" />
                <h3 className="text-lg font-medium text-gray-900">{t("docAnalysis.analyzing")}</h3>
                <p className="text-gray-500 text-sm mt-1">{t("docAnalysis.analyzingHint")}</p>
              </div>
            )}

            {analysisResult && (
              <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">

                <div className="bg-blue-50 p-4 rounded-xl border border-blue-100">
                  <div className="flex gap-3">
                    <Info className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
                    <div>
                      <h4 className="font-medium text-blue-900 mb-1">{t("docAnalysis.docSummary")}</h4>
                      <p className="text-sm text-blue-800 leading-relaxed">
                        {analysisResult.summary}
                      </p>
                    </div>
                  </div>
                </div>

                <div className="grid md:grid-cols-2 gap-6">

                  <div className="border border-gray-200 rounded-xl p-5">
                    <div className="flex items-center gap-2 mb-4 text-amber-600">
                      <ShieldAlert className="w-5 h-5" />
                      <h4 className="font-medium">{t("docAnalysis.potentialRisks")}</h4>
                    </div>
                    <ul className="space-y-3">
                      {analysisResult.risks.map((risk, i) => (
                        <li key={i} className="flex gap-3 text-sm text-gray-700">
                          <span className="w-1.5 h-1.5 bg-amber-500 rounded-full mt-1.5 flex-shrink-0" />
                          {risk}
                        </li>
                      ))}
                    </ul>
                  </div>

                  <div className="border border-gray-200 rounded-xl p-5">
                    <div className="flex items-center gap-2 mb-4 text-emerald-600">
                      <CheckCircle className="w-5 h-5" />
                      <h4 className="font-medium">{t("docAnalysis.keyDetails")}</h4>
                    </div>
                    <ul className="space-y-3">
                      {analysisResult.keyPoints.map((point, i) => (
                        <li key={i} className="flex gap-3 text-sm text-gray-700">
                          <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full mt-1.5 flex-shrink-0" />
                          {point}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>

                <div className="pt-4 flex justify-end">
                  <button className="px-6 py-2.5 bg-[#052379] text-white text-sm font-medium rounded-lg hover:bg-[#041d5c] transition-colors">
                    {t("docAnalysis.downloadReport")}
                  </button>
                </div>

              </div>
            )}

          </div>
        )}

      </div>
    </div>
  );
}
