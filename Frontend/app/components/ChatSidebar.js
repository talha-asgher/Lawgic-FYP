"use client";

import { MessageSquare, Search, Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useLanguage } from "../lib/LanguageContext";

function formatTime(dateStr) {
  if (!dateStr) return "";
  const d = new Date(dateStr);
  const now = new Date();
  const diffDays = Math.floor((now - d) / 86400000);

  if (diffDays === 0) {
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } else if (diffDays < 7) {
    return d.toLocaleDateString([], { weekday: "short" });
  } else {
    return d.toLocaleDateString([], { day: "2-digit", month: "2-digit", year: "2-digit" });
  }
}

export default function ChatSidebar({
  conversations,
  loading,
  searchQuery,
  onSearchChange,
  activeConvId,
  currentUser,
}) {
  const router = useRouter();
  const { t } = useLanguage();

  const filtered = conversations.filter((c) => {
    const other = c.participants?.find((p) => p.user_id !== currentUser?.user_id);
    return !searchQuery || other?.name?.toLowerCase().includes(searchQuery.toLowerCase());
  });

  return (
    <aside className="w-full md:w-80 lg:w-96 flex-shrink-0 flex flex-col border-e border-gray-200 bg-white h-full">
      <div className="px-4 pt-5 pb-3 border-b border-gray-100">
        <div className="flex items-center justify-between mb-3">
          <h1 className="text-lg font-semibold text-gray-900">{t("chat.sidebarHeading")}</h1>
        </div>
        <div className="relative">
          <Search className="absolute start-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            placeholder={t("chat.searchPlaceholder")}
            className="w-full ps-9 pe-3 py-2 bg-[#F6F8FB] border border-gray-200 rounded-xl text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-[#052379]/20"
          />
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="flex justify-center py-12">
            <Loader2 className="w-6 h-6 text-[#052379] animate-spin" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 px-6 text-center">
            <MessageSquare className="w-10 h-10 text-gray-200 mb-3" />
            <p className="text-sm text-gray-400">
              {searchQuery ? t("chat.noMatch") : t("chat.noConversations")}
            </p>
          </div>
        ) : (
          filtered.map((conv) => {
            const other = conv.participants?.find((p) => p.user_id !== currentUser?.user_id);
            const initials = other?.name
              ? other.name.split(" ").map((n) => n[0]).join("").substring(0, 2).toUpperCase()
              : "?";
            const isActive = activeConvId && conv.conv_id === parseInt(activeConvId);

            return (
              <button
                key={conv.conv_id}
                onClick={() => router.push("/chat/" + conv.conv_id)}
                className={`w-full flex items-center gap-3 px-4 py-3 transition-colors text-start border-b border-gray-50
                  ${isActive ? "bg-blue-50" : "hover:bg-gray-50"}`}
              >
                <div className="relative flex-shrink-0">
                  <div className="w-11 h-11 bg-[#052379] rounded-full flex items-center justify-center text-white text-sm font-medium">
                    {initials}
                  </div>
                  {conv.unread_count > 0 && (
                    <span className="absolute -top-0.5 -end-0.5 w-4 h-4 bg-[#052379] text-white text-[9px] font-bold rounded-full flex items-center justify-center">
                      {conv.unread_count > 9 ? "9+" : conv.unread_count}
                    </span>
                  )}
                </div>

                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between mb-0.5">
                    <span className={`text-sm truncate ${conv.unread_count > 0 ? "font-semibold text-gray-900" : "font-medium text-gray-800"}`}>
                      {other?.name || "Unknown"}
                    </span>
                    <span className="text-[11px] text-gray-400 flex-shrink-0 ms-2">
                      {formatTime(conv.last_message_at)}
                    </span>
                  </div>
                  <p className={`text-xs truncate ${conv.unread_count > 0 ? "text-gray-700 font-medium" : "text-gray-400"}`}>
                    {conv.last_message || t("chat.noMessagesYet")}
                  </p>
                </div>
              </button>
            );
          })
        )}
      </div>
    </aside>
  );
}
