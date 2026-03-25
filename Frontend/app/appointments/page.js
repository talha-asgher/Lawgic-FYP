"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import {
  Calendar, Clock, Video, Phone, MapPin, MessageSquare,
  Loader2, AlertCircle, CheckCircle, XCircle, Ban
} from "lucide-react";
import { getMyAppointments, updateAppointmentStatus, isLoggedIn, getUser } from "@/lib/api";

const MODE_LABELS = {
  online_meeting: { label: "Video Call", icon: Video },
  phone: { label: "Phone Call", icon: Phone },
  physical: { label: "In Person", icon: MapPin },
  chat: { label: "Chat", icon: MessageSquare },
};

const STATUS_CONFIG = {
  pending: { label: "Pending", bg: "bg-amber-50", text: "text-amber-700" },
  accepted: { label: "Confirmed", bg: "bg-emerald-50", text: "text-emerald-700" },
  rejected: { label: "Declined", bg: "bg-red-50", text: "text-red-700" },
  cancelled: { label: "Cancelled", bg: "bg-gray-100", text: "text-gray-500" },
};

export default function AppointmentsPage() {
  const router = useRouter();
  const currentUser = getUser();
  const isLawyer = currentUser?.role === "lawyer";

  const [appointments, setAppointments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeFilter, setActiveFilter] = useState("all");
  const [actionLoading, setActionLoading] = useState({});

  useEffect(() => {
    if (!isLoggedIn()) { router.replace("/login"); return; }
    loadAppointments();
  }, []);

  const loadAppointments = async () => {
    setLoading(true);
    try {
      const data = await getMyAppointments();
      setAppointments(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleStatusUpdate = async (apptId, newStatus) => {
    setActionLoading(prev => ({ ...prev, [apptId]: newStatus }));
    try {
      await updateAppointmentStatus(apptId, newStatus);
      loadAppointments();
    } catch (err) {
      alert(err.message || "Failed to update appointment");
    } finally {
      setActionLoading(prev => { const n = { ...prev }; delete n[apptId]; return n; });
    }
  };

  const filters = isLawyer
    ? ["all", "pending", "accepted", "rejected"]
    : ["all", "pending", "accepted", "cancelled"];

  const filtered = appointments.filter(a =>
    activeFilter === "all" || a.status === activeFilter
  );

  return (
    <div className="min-h-screen bg-[#F6F8FB] px-4 lg:px-8 py-8">
      <div className="max-w-4xl mx-auto">
        <div className="mb-6">
          <h1 className="text-2xl font-semibold text-gray-900">Appointments</h1>
          <p className="text-gray-500 text-sm mt-1">
            {isLawyer ? "Manage appointment requests from clients" : "Track your scheduled appointments"}
          </p>
        </div>

        <div className="flex gap-1 mb-6 bg-white rounded-xl border border-gray-200 p-1 overflow-x-auto">
          {filters.map(f => (
            <button key={f} onClick={() => setActiveFilter(f)}
              className={`flex-1 py-2 text-sm font-medium rounded-lg transition-colors capitalize whitespace-nowrap min-w-[80px]
                ${activeFilter === f ? "bg-[#052379] text-white" : "text-gray-600 hover:text-gray-900"}`}>
              {f === "all" ? `All (${appointments.length})` : STATUS_CONFIG[f]?.label || f}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="flex justify-center py-12">
            <Loader2 className="w-8 h-8 text-[#052379] animate-spin" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="bg-white rounded-2xl border border-gray-200 p-12 text-center">
            <Calendar className="w-12 h-12 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500">
              {activeFilter === "all"
                ? isLawyer ? "No appointments yet." : "No appointments yet. Book one from your active cases."
                : `No ${activeFilter} appointments.`}
            </p>
            {!isLawyer && activeFilter === "all" && (
              <button onClick={() => router.push("/cases")}
                className="mt-4 text-[#052379] hover:underline text-sm">
                Go to Cases
              </button>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            {filtered.map(appt => {
              const st = STATUS_CONFIG[appt.status] || STATUS_CONFIG.pending;
              const modeInfo = MODE_LABELS[appt.mode_of_comm];
              const ModeIcon = modeInfo?.icon || Calendar;
              const scheduledDate = new Date(appt.scheduled_at);
              const isPast = scheduledDate < new Date();
              const isLoading = actionLoading[appt.appt_id];

              return (
                <div key={appt.appt_id} className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm">
                  <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
                    <div className="flex-1">
                      <div className="flex items-center gap-3 mb-2">
                        <div className="w-10 h-10 bg-[#052379]/10 rounded-xl flex items-center justify-center">
                          <ModeIcon className="w-5 h-5 text-[#052379]" />
                        </div>
                        <div>
                          <p className="font-semibold text-gray-900 text-sm">
                            {isLawyer ? (appt.client_name || "Client") : (appt.lawyer_name || "Lawyer")}
                          </p>
                          <p className="text-xs text-gray-500">{modeInfo?.label || appt.mode_of_comm}</p>
                        </div>
                        <span className={`ml-auto sm:hidden px-2.5 py-1 rounded-full text-xs font-medium ${st.bg} ${st.text}`}>
                          {st.label}
                        </span>
                      </div>

                      <div className="flex flex-wrap gap-4 text-sm text-gray-600 mt-3">
                        <span className="flex items-center gap-1.5">
                          <Calendar className="w-4 h-4 text-gray-400" />
                          {scheduledDate.toLocaleDateString(undefined, { weekday: "short", year: "numeric", month: "short", day: "numeric" })}
                        </span>
                        <span className="flex items-center gap-1.5">
                          <Clock className="w-4 h-4 text-gray-400" />
                          {scheduledDate.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                        </span>
                        {isPast && appt.status === "accepted" && (
                          <span className="text-xs text-gray-400 italic">Past</span>
                        )}
                      </div>

                      {appt.notes && (
                        <p className="text-sm text-gray-500 mt-2 bg-gray-50 rounded-lg px-3 py-2">
                          {appt.notes}
                        </p>
                      )}
                    </div>

                    <div className="flex flex-col items-end gap-3">
                      <span className={`hidden sm:inline-flex px-2.5 py-1 rounded-full text-xs font-medium ${st.bg} ${st.text}`}>
                        {st.label}
                      </span>

                      {isLawyer && appt.status === "pending" && (
                        <div className="flex gap-2">
                          <button
                            onClick={() => handleStatusUpdate(appt.appt_id, "accepted")}
                            disabled={!!isLoading}
                            className="flex items-center gap-1 px-3 py-1.5 bg-emerald-600 text-white text-xs font-medium rounded-lg hover:bg-emerald-700 transition-colors disabled:opacity-50">
                            {isLoading === "accepted" ? <Loader2 className="w-3 h-3 animate-spin" /> : <CheckCircle className="w-3 h-3" />}
                            Accept
                          </button>
                          <button
                            onClick={() => handleStatusUpdate(appt.appt_id, "rejected")}
                            disabled={!!isLoading}
                            className="flex items-center gap-1 px-3 py-1.5 bg-white border border-gray-200 text-gray-700 text-xs font-medium rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-50">
                            {isLoading === "rejected" ? <Loader2 className="w-3 h-3 animate-spin" /> : <XCircle className="w-3 h-3" />}
                            Decline
                          </button>
                        </div>
                      )}

                      {!isLawyer && (appt.status === "pending" || appt.status === "accepted") && (
                        <button
                          onClick={() => handleStatusUpdate(appt.appt_id, "cancelled")}
                          disabled={!!isLoading}
                          className="flex items-center gap-1 px-3 py-1.5 bg-white border border-red-200 text-red-600 text-xs font-medium rounded-lg hover:bg-red-50 transition-colors disabled:opacity-50">
                          {isLoading === "cancelled" ? <Loader2 className="w-3 h-3 animate-spin" /> : <Ban className="w-3 h-3" />}
                          Cancel
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
