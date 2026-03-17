"use client";

import { useState, useEffect, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import { Send, Loader2, ChevronLeft, MessageSquare } from "lucide-react";
import {
  getConversationMessages,
  sendConversationMessage,
  getMyConversations,
  markConversationRead,
  getUser,
  isLoggedIn,
} from "@/lib/api";
import ChatSidebar from "@/app/components/ChatSidebar";

function dayLabel(dateStr) {
  const d = new Date(dateStr);
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);

  if (d.toDateString() === today.toDateString()) return "Today";
  if (d.toDateString() === yesterday.toDateString()) return "Yesterday";
  return d.toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" });
}

function isSameDay(a, b) {
  return new Date(a).toDateString() === new Date(b).toDateString();
}

export default function ChatThreadPage() {
  const { id } = useParams();
  const router = useRouter();
  const currentUser = getUser();

  const [conversations, setConversations] = useState([]);
  const [convsLoading, setConvsLoading] = useState(true);
  const [messages, setMessages] = useState([]);
  const [msgsLoading, setMsgsLoading] = useState(true);
  const [convTitle, setConvTitle] = useState("");
  const [newMessage, setNewMessage] = useState("");
  const [sending, setSending] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  const bottomRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (!isLoggedIn()) { window.location.replace("/login"); return; }
    if (!id) return;

    getMyConversations()
      .then((data) => {
        setConversations(data);
        if (currentUser) {
          const conv = data.find((c) => c.conv_id === parseInt(id));
          if (conv) {
            const other = conv.participants?.find((p) => p.user_id !== currentUser.user_id);
            setConvTitle(other?.name || "Conversation");
          }
        }
      })
      .catch(console.error)
      .finally(() => setConvsLoading(false));

    getConversationMessages(id)
      .then(setMessages)
      .catch(console.error)
      .finally(() => setMsgsLoading(false));

    markConversationRead(id).catch(() => {});

    const interval = setInterval(() => {
      getConversationMessages(id).then(setMessages).catch(() => {});
    }, 5000);
    return () => clearInterval(interval);
  }, [id]);

  const handleSend = async (e) => {
    e.preventDefault();
    if (!newMessage.trim() || sending) return;
    const text = newMessage.trim();
    setNewMessage("");
    setSending(true);
    try {
      const msg = await sendConversationMessage(id, text);
      setMessages((prev) => [...prev, msg]);
    } catch (err) {
      setNewMessage(text);
      alert(err.message || "Failed to send message");
    } finally {
      setSending(false);
      inputRef.current?.focus();
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend(e);
    }
  };

  const titleInitials = convTitle
    ? convTitle.split(" ").map((n) => n[0]).join("").substring(0, 2).toUpperCase()
    : "?";

  return (
    <div className="flex h-[calc(100vh-128px)] bg-[#F6F8FB] overflow-hidden">

      <div className="hidden md:flex h-full">
        <ChatSidebar
          conversations={conversations}
          loading={convsLoading}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          activeConvId={id}
          currentUser={currentUser}
        />
      </div>

      {/* Right panel*/}
      <div className="flex-1 flex flex-col min-w-0 bg-white">

        {/* Thread header */}
        <div className="flex items-center gap-3 px-4 py-3 bg-white border-b border-gray-200 shadow-sm flex-shrink-0">
          {/* Back button*/}
          <button
            onClick={() => router.push("/chat")}
            className="md:hidden text-gray-600 hover:text-gray-900 flex-shrink-0"
          >
            <ChevronLeft className="w-5 h-5" />
          </button>

          {/* Avatar */}
          <div className="relative flex-shrink-0">
            <div className="w-10 h-10 bg-[#052379] rounded-full flex items-center justify-center text-white text-sm font-medium">
              {msgsLoading ? "…" : titleInitials}
            </div>
            {/* Online indicator */}
            <span className="absolute bottom-0 right-0 w-2.5 h-2.5 bg-emerald-400 rounded-full border-2 border-white" />
          </div>

          {/* Name */}
          <div className="flex-1 min-w-0">
            <h2 className="font-medium text-gray-900 text-sm truncate">
              {convTitle || (msgsLoading ? "Loading…" : "Conversation")}
            </h2>
            <p className="text-xs text-emerald-500">Online</p>
          </div>
        </div>

        {/* Messages area */}
        <div className="flex-1 overflow-y-auto px-4 py-4 bg-[#F6F8FB]">
          {msgsLoading ? (
            <div className="flex justify-center items-center h-full">
              <Loader2 className="w-7 h-7 text-[#052379] animate-spin" />
            </div>
          ) : messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full gap-3 text-center">
              <MessageSquare className="w-10 h-10 text-gray-200" />
              <p className="text-sm text-gray-400">No messages yet. Say hello!</p>
            </div>
          ) : (
            <div className="space-y-1 max-w-3xl mx-auto">
              {messages.map((msg, i) => {
                const isMe = msg.sender_id === currentUser?.user_id;
                const prevMsg = messages[i - 1];
                const showDateSep = !prevMsg || !isSameDay(prevMsg.created_at, msg.created_at);
                const showSenderName = !isMe && (!prevMsg || prevMsg.sender_id !== msg.sender_id || showDateSep);
                const isLastInGroup = !messages[i + 1] || messages[i + 1].sender_id !== msg.sender_id;

                return (
                  <div key={msg.message_id}>
                    {/* Date separator */}
                    {showDateSep && (
                      <div className="flex items-center gap-3 my-4">
                        <div className="flex-1 h-px bg-gray-200" />
                        <span className="text-xs text-gray-400 bg-[#F6F8FB] px-2 whitespace-nowrap">
                          {dayLabel(msg.created_at)}
                        </span>
                        <div className="flex-1 h-px bg-gray-200" />
                      </div>
                    )}

                    {/* Message bubble */}
                    <div className={`flex items-end gap-2 ${isMe ? "justify-end" : "justify-start"} ${isLastInGroup ? "mb-2" : "mb-0.5"}`}>
                      {/* Other user avatar*/}
                      {!isMe && (
                        <div className={`w-7 h-7 rounded-full bg-[#052379] flex items-center justify-center text-white text-[10px] font-medium flex-shrink-0 ${isLastInGroup ? "opacity-100" : "opacity-0"}`}>
                          {msg.sender_name ? msg.sender_name.split(" ").map((n) => n[0]).join("").substring(0, 2).toUpperCase() : "?"}
                        </div>
                      )}

                      <div className={`flex flex-col ${isMe ? "items-end" : "items-start"}`}>
                        {/* Sender name for incoming messages*/}
                        {showSenderName && (
                          <span className="text-[11px] text-gray-400 font-medium mb-1 ml-1">
                            {msg.sender_name}
                          </span>
                        )}

                        <div className={`relative max-w-xs lg:max-w-sm xl:max-w-md px-3.5 py-2 text-sm
                          ${isMe
                            ? "bg-[#052379] text-white rounded-2xl rounded-br-md"
                            : "bg-white text-gray-900 border border-gray-200 rounded-2xl rounded-bl-md shadow-sm"
                          }`}
                        >
                          <p className="leading-relaxed whitespace-pre-wrap break-words">{msg.content}</p>
                          <p className={`text-[10px] mt-1 text-right ${isMe ? "text-blue-200" : "text-gray-400"}`}>
                            {new Date(msg.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
              <div ref={bottomRef} />
            </div>
          )}
        </div>

        <form
          onSubmit={handleSend}
          className="flex items-center gap-3 px-4 py-3 bg-white border-t border-gray-200 flex-shrink-0"
        >
          <input
            ref={inputRef}
            type="text"
            value={newMessage}
            onChange={(e) => setNewMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type a message…"
            className="flex-1 px-4 py-2.5 bg-[#F6F8FB] border border-gray-200 rounded-full text-sm text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-[#052379]/20 focus:border-[#052379] transition-colors"
          />
          <button
            type="submit"
            disabled={!newMessage.trim() || sending}
            className="w-10 h-10 bg-[#052379] rounded-full flex items-center justify-center text-white hover:bg-[#041d5c] transition-colors disabled:opacity-40 flex-shrink-0"
          >
            {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          </button>
        </form>
      </div>
    </div>
  );
}
