"use client";

import { useState, useEffect } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import {
  Calendar, Clock, Video, Phone, MapPin, ChevronLeft,
  CheckCircle, Loader2, AlertCircle,
} from "lucide-react";
import { getLawyerById, getCaseById, createAppointment, isLoggedIn, getUser } from "@/lib/api";
import { useLanguage } from "@/app/lib/LanguageContext";

function todayString() {
  return new Date().toISOString().split("T")[0];
}

export default function BookAppointmentPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { t } = useLanguage();
  const lawyerId = searchParams.get("lawyer");
  const caseId = searchParams.get("case");

  const [lawyer, setLawyer] = useState(null);
  const [caseData, setCaseData] = useState(null);
  const [loadingLawyer, setLoadingLawyer] = useState(true);
  const [fetchError, setFetchError] = useState("");

  const [mode, setMode] = useState("physical");
  const [date, setDate] = useState("");
  const [hour, setHour] = useState("");
  const [minute, setMinute] = useState("00");
  const [ampm, setAmpm] = useState("AM");
  const [notes, setNotes] = useState("");
  const [validationError, setValidationError] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [submitError, setSubmitError] = useState("");

  const MODES = [
    { value: "physical", labelKey: "newAppointment.modes.physical.label", descKey: "newAppointment.modes.physical.desc", icon: MapPin },
    { value: "online_meeting", labelKey: "newAppointment.modes.online_meeting.label", descKey: "newAppointment.modes.online_meeting.desc", icon: Video },
    { value: "phone", labelKey: "newAppointment.modes.phone.label", descKey: "newAppointment.modes.phone.desc", icon: Phone },
  ];

  useEffect(() => {
    if (!isLoggedIn()) { router.replace("/login"); return; }
    const user = getUser();
    if (user?.role === "lawyer") { router.replace("/dashboard/lawyer"); return; }
    if (!lawyerId || !caseId) {
      setFetchError(t("newAppointment.errInvalidLink"));
      setLoadingLawyer(false);
      return;
    }

    Promise.all([
      getLawyerById(lawyerId),
      getCaseById(caseId),
    ])
      .then(([lawyerData, caseInfo]) => {
        if (caseInfo.status !== "in_progress") {
          setFetchError(t("newAppointment.errAcceptedOnly"));
          return;
        }
        setLawyer(lawyerData);
        setCaseData(caseInfo);
      })
      .catch((e) => setFetchError(e.message || "Could not load details."))
      .finally(() => setLoadingLawyer(false));
  }, [lawyerId, caseId]);

  const get24hTime = () => {
    const h = parseInt(hour);
    const h24 = ampm === "PM" ? (h === 12 ? 12 : h + 12) : (h === 12 ? 0 : h);
    return `${String(h24).padStart(2, "0")}:${minute}`;
  };

  const validate = () => {
    if (!date) { setValidationError(t("newAppointment.errDate")); return false; }
    if (!hour) { setValidationError(t("newAppointment.errTime")); return false; }
    const scheduled = new Date(`${date}T${get24hTime()}`);
    if (scheduled <= new Date()) { setValidationError(t("newAppointment.errFuture")); return false; }
    return true;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setValidationError("");
    setSubmitError("");
    if (!validate()) return;

    const scheduledAt = new Date(`${date}T${get24hTime()}`).toISOString();
    setSubmitting(true);
    try {
      await createAppointment(parseInt(lawyerId), mode, scheduledAt, notes.trim() || null);
      setSuccess(true);
    } catch (err) {
      setSubmitError(err.message || "Failed to book appointment. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  if (loadingLawyer) {
    return (
      <div className="min-h-screen bg-[#F6F8FB] flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="w-10 h-10 text-[#052379] animate-spin" />
          <p className="text-gray-500 text-sm">{t("common.loading")}</p>
        </div>
      </div>
    );
  }

  if (fetchError) {
    return (
      <div className="min-h-screen bg-[#F6F8FB] flex items-center justify-center">
        <div className="text-center max-w-sm px-4">
          <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-3" />
          <p className="text-gray-700 mb-4">{fetchError}</p>
          <button onClick={() => router.push("/cases")}
            className="px-4 py-2 bg-[#052379] text-white text-sm font-medium rounded-xl hover:bg-[#041d5c] transition-colors">
            {t("newAppointment.backToCasesBtn")}
          </button>
        </div>
      </div>
    );
  }

  if (success) {
    const scheduledAt = new Date(`${date}T${get24hTime()}`);
    const selectedMode = MODES.find(m => m.value === mode);
    return (
      <div className="min-h-screen bg-[#F6F8FB] flex items-center justify-center px-4">
        <div className="bg-white rounded-2xl border border-gray-200 shadow-sm max-w-md w-full p-8 text-center">
          <div className="w-16 h-16 bg-emerald-100 rounded-full flex items-center justify-center mx-auto mb-4">
            <CheckCircle className="w-9 h-9 text-emerald-600" />
          </div>
          <h2 className="text-xl font-semibold text-gray-900 mb-2">{t("newAppointment.successHeading")}</h2>
          <p className="text-gray-500 text-sm mb-6">
            {t("newAppointment.successMsg", { name: lawyer?.name || "" })}
          </p>

          <div className="bg-[#F6F8FB] rounded-xl p-4 text-start mb-6 space-y-2">
            <div className="flex items-center gap-2 text-sm">
              <Calendar className="w-4 h-4 text-gray-400" />
              <span className="text-gray-600">{scheduledAt.toLocaleDateString(undefined, { weekday: "long", year: "numeric", month: "long", day: "numeric" })}</span>
            </div>
            <div className="flex items-center gap-2 text-sm">
              <Clock className="w-4 h-4 text-gray-400" />
              <span className="text-gray-600">{scheduledAt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
            </div>
            {selectedMode && (
              <div className="flex items-center gap-2 text-sm">
                <selectedMode.icon className="w-4 h-4 text-gray-400" />
                <span className="text-gray-600">{t(selectedMode.labelKey)}</span>
              </div>
            )}
          </div>

          <div className="flex flex-col sm:flex-row gap-3">
            <button onClick={() => router.push("/appointments")}
              className="flex-1 px-4 py-2.5 bg-[#052379] text-white text-sm font-medium rounded-xl hover:bg-[#041d5c] transition-colors">
              {t("newAppointment.viewAppointments")}
            </button>
            <button onClick={() => router.push("/cases")}
              className="flex-1 px-4 py-2.5 bg-white border border-gray-200 text-gray-700 text-sm font-medium rounded-xl hover:bg-gray-50 transition-colors">
              {t("newAppointment.backToCasesBtn")}
            </button>
          </div>
        </div>
      </div>
    );
  }

  const initials = lawyer?.name
    ? lawyer.name.split(" ").map((n) => n[0]).join("").substring(0, 2).toUpperCase()
    : "?";

  return (
    <div className="min-h-screen bg-[#F6F8FB] px-4 lg:px-8 py-8">
      <div className="max-w-2xl mx-auto">
        <button onClick={() => router.push("/cases")}
          className="flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-6 text-sm">
          <ChevronLeft className="w-4 h-4" />
          {t("newAppointment.backToCases")}
        </button>

        <h1 className="text-2xl font-semibold text-gray-900 mb-6">{t("newAppointment.heading")}</h1>

        {lawyer && (
          <div className="bg-white rounded-2xl border border-gray-200 p-4 mb-6 shadow-sm flex items-center gap-4">
            <div className="w-14 h-14 bg-[#052379] rounded-xl flex items-center justify-center text-white font-semibold text-lg flex-shrink-0">
              {initials}
            </div>
            <div className="flex-1 min-w-0">
              <p className="font-medium text-gray-900">{lawyer.name}</p>
              <p className="text-sm text-gray-500 truncate">
                {(lawyer.specializations || [lawyer.specialization]).filter(Boolean).join(", ")}
              </p>
              {caseData && (
                <p className="text-xs text-emerald-700 mt-0.5">{t("newAppointment.caseLabel")} {caseData.title}</p>
              )}
            </div>
            {lawyer.consultation_fee && (
              <div className="text-end flex-shrink-0">
                <p className="text-xs text-gray-400">{t("newAppointment.feeLabel")}</p>
                <p className="text-sm font-medium text-gray-900">PKR {lawyer.consultation_fee.toLocaleString()}</p>
              </div>
            )}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm">
            <h2 className="font-medium text-gray-900 mb-4">{t("newAppointment.howMeet")}</h2>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {MODES.map((m) => (
                <button
                  key={m.value}
                  type="button"
                  onClick={() => setMode(m.value)}
                  className={`flex flex-col items-center gap-2 p-4 rounded-xl border-2 transition-all text-center
                    ${mode === m.value
                      ? "border-[#052379] bg-blue-50 text-[#052379]"
                      : "border-gray-200 hover:border-gray-300 text-gray-600"
                    }`}
                >
                  <m.icon className="w-6 h-6" />
                  <span className="text-sm font-medium">{t(m.labelKey)}</span>
                  <span className="text-xs text-gray-400 leading-snug">{t(m.descKey)}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm">
            <h2 className="font-medium text-gray-900 mb-4">{t("newAppointment.selectDateTime")}</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-gray-600 mb-2">
                  <span className="flex items-center gap-1.5"><Calendar className="w-4 h-4" />{t("newAppointment.dateLabel")}</span>
                </label>
                <input
                  type="date"
                  value={date}
                  min={todayString()}
                  onChange={(e) => { setDate(e.target.value); setValidationError(""); }}
                  className="w-full px-3 py-2.5 bg-[#F6F8FB] border border-gray-200 rounded-xl text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-[#052379]/20 focus:border-[#052379]"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-600 mb-2">
                  <span className="flex items-center gap-1.5"><Clock className="w-4 h-4" />{t("newAppointment.timeLabel")}</span>
                </label>
                <div className="flex gap-2">
                  <select
                    value={hour}
                    onChange={(e) => { setHour(e.target.value); setValidationError(""); }}
                    className="flex-1 px-3 py-2.5 bg-[#F6F8FB] border border-gray-200 rounded-xl text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-[#052379]/20 focus:border-[#052379]"
                  >
                    <option value="">HH</option>
                    {[1,2,3,4,5,6,7,8,9,10,11,12].map(h => (
                      <option key={h} value={h}>{String(h).padStart(2,"0")}</option>
                    ))}
                  </select>
                  <select
                    value={minute}
                    onChange={(e) => { setMinute(e.target.value); setValidationError(""); }}
                    className="flex-1 px-3 py-2.5 bg-[#F6F8FB] border border-gray-200 rounded-xl text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-[#052379]/20 focus:border-[#052379]"
                  >
                    {["00","15","30","45"].map(m => (
                      <option key={m} value={m}>{m}</option>
                    ))}
                  </select>
                  <select
                    value={ampm}
                    onChange={(e) => { setAmpm(e.target.value); setValidationError(""); }}
                    className="px-3 py-2.5 bg-[#F6F8FB] border border-gray-200 rounded-xl text-sm text-gray-900 focus:outline-none focus:ring-2 focus:ring-[#052379]/20 focus:border-[#052379]"
                  >
                    <option value="AM">AM</option>
                    <option value="PM">PM</option>
                  </select>
                </div>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm">
            <h2 className="font-medium text-gray-900 mb-1">
              {t("newAppointment.notesHeading")} <span className="text-gray-400 font-normal text-sm">{t("newAppointment.notesOptional")}</span>
            </h2>
            <p className="text-xs text-gray-400 mb-3">{t("newAppointment.notesHint")}</p>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={4}
              placeholder={t("newAppointment.notesPlaceholder")}
              className="w-full px-3 py-2.5 bg-[#F6F8FB] border border-gray-200 rounded-xl text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-[#052379]/20 focus:border-[#052379] resize-none"
            />
          </div>

          {(validationError || submitError) && (
            <div className="flex items-start gap-2 p-4 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">
              <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
              <span>{validationError || submitError}</span>
            </div>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="w-full py-3 bg-[#052379] hover:bg-[#041d5c] disabled:opacity-60 disabled:cursor-not-allowed text-white text-sm font-medium rounded-xl transition-colors flex items-center justify-center gap-2 shadow-sm"
          >
            {submitting ? (
              <><Loader2 className="w-4 h-4 animate-spin" /> {t("newAppointment.booking")}</>
            ) : (
              <><Calendar className="w-4 h-4" /> {t("newAppointment.confirmAppointment")}</>
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
