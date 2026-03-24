"use client";

import { useState, useEffect } from "react";
import { MessageSquare } from "lucide-react";
import { useRouter } from "next/navigation";
import { getMyConversations, getUser, isLoggedIn } from "@/lib/api";
import ChatSidebar from "@/app/components/ChatSidebar";

export default function ChatListPage() {
  const router = useRouter();
  const [conversations, setConversations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const currentUser = getUser();

  useEffect(() => {
    if (!isLoggedIn()) { router.replace("/login"); return; }
    getMyConversations()
      .then(setConversations)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="flex h-[calc(100vh-128px)] bg-[#F6F8FB] overflow-hidden">
      <ChatSidebar
        conversations={conversations}
        loading={loading}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        activeConvId={null}
        currentUser={currentUser}
      />

      {/* Right pane*/}
      <div className="hidden md:flex flex-1 flex-col items-center justify-center gap-4 text-center bg-[#F6F8FB]">
        <div className="w-20 h-20 bg-white rounded-full border border-gray-200 flex items-center justify-center shadow-sm">
          <MessageSquare className="w-9 h-9 text-gray-300" />
        </div>
        <div>
          <h2 className="text-lg font-medium text-gray-700 mb-1">Your Messages</h2>
          <p className="text-sm text-gray-400">Select a conversation to start chatting.</p>
        </div>
      </div>
    </div>
  );
}
