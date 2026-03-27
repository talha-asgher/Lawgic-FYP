"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import {
  Send,
  Plus,
  MessageSquare,
  Clock,
  Scale,
  User,
  Loader2,
  Square,
  Copy,
  RotateCcw,
  ChevronDown,
  ChevronUp,
  Trash2,
  Pencil,
} from "lucide-react";
import { ragAsk, isLoggedIn } from "@/lib/api";

const STORAGE_KEY = "lawgic_ai_qa_sessions_v1";

function formatNowTime() {
  return new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function greetingMessage() {
  return {
    id: "greeting",
    role: "assistant",
    text: "Hello! I'm your AI legal assistant. I can help you understand Pakistani laws, or find legal procedures. How can I help you today?",
    timestamp: formatNowTime(),
  };
}

function sessionTitleFromMessages(messages) {
  const u = messages.find((m) => m.role === "user");
  if (!u?.text) return "New chat";
  const t = u.text.trim();
  return t.length > 56 ? `${t.slice(0, 53)}…` : t;
}

function formatRelativeTime(ts) {
  const diff = Date.now() - ts;
  if (diff < 60_000) return "Just now";
  if (diff < 3600_000) return `${Math.floor(diff / 60_000)}m ago`;
  if (diff < 86400_000) return `${Math.floor(diff / 3600_000)}h ago`;
  return `${Math.floor(diff / 86400_000)}d ago`;
}

function formatSourceOneLine(src) {
  const parts = [];
  if (src.act_name) parts.push(String(src.act_name).trim());
  const sec = src.section_number != null ? String(src.section_number).trim() : "";
  if (sec) parts.push(`Sec. ${sec}`);
  if (src.section_title) parts.push(String(src.section_title).trim());
  if (Array.isArray(src.page_numbers) && src.page_numbers.length > 0) {
    parts.push(`Page ${src.page_numbers.join(", ")}`);
  }
  return parts.length ? parts.join(" — ") : "Source";
}

export default function AiQAPage() {
  const router = useRouter();
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [sessions, setSessions] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [expandedSources, setExpandedSources] = useState({});
  const [editingUserMsgId, setEditingUserMsgId] = useState(null);
  const [editDraft, setEditDraft] = useState("");
  const abortRef = useRef(null);
  const editTextareaRef = useRef(null);

  const activeSession = sessions.find((s) => s.id === activeId);
  const messages = activeSession?.messages ?? [];

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const data = JSON.parse(raw);
        if (Array.isArray(data.sessions) && data.sessions.length) {
          setSessions(data.sessions);
          setActiveId(data.activeId || data.sessions[0].id);
          return;
        }
      }
    } catch (_) {
      /* ignore */
    }
    const id =
      typeof crypto !== "undefined" && crypto.randomUUID
        ? crypto.randomUUID()
        : `s-${Date.now()}`;
    const initial = {
      id,
      title: "New chat",
      updatedAt: Date.now(),
      messages: [greetingMessage()],
    };
    setSessions([initial]);
    setActiveId(id);
  }, []);

  useEffect(() => {
    if (!sessions.length || !activeId) return;
    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ sessions, activeId })
      );
    } catch (_) {
      /* ignore */
    }
  }, [sessions, activeId]);

  useEffect(() => {
    setEditingUserMsgId(null);
    setEditDraft("");
  }, [activeId]);

  useEffect(() => {
    if (editingUserMsgId == null) return;
    const t = requestAnimationFrame(() => {
      editTextareaRef.current?.focus();
      editTextareaRef.current?.select();
    });
    return () => cancelAnimationFrame(t);
  }, [editingUserMsgId]);

  const patchActiveMessages = useCallback(
    (updater) => {
      setSessions((prev) =>
        prev.map((s) => {
          if (s.id !== activeId) return s;
          const nextMsgs =
            typeof updater === "function" ? updater(s.messages) : updater;
          return {
            ...s,
            messages: nextMsgs,
            updatedAt: Date.now(),
            title: sessionTitleFromMessages(nextMsgs),
          };
        })
      );
    },
    [activeId]
  );

  const runAsk = async (text, { appendUser = true } = {}) => {
    if (!text.trim()) return;

    if (!isLoggedIn()) {
      router.replace("/login");
      return;
    }

    const currentTime = formatNowTime();
    const userMessage = {
      id: Date.now(),
      role: "user",
      text: text.trim(),
      timestamp: currentTime,
    };

    if (appendUser) {
      patchActiveMessages((prev) => [...prev, userMessage]);
      setInput("");
    }

    setIsLoading(true);
    setError(null);
    abortRef.current = new AbortController();

    try {
      const data = await ragAsk(text.trim(), {
        topKRetrieval: 15,
        topKContext: 6,
        signal: abortRef.current.signal,
      });
      const botMessage = {
        id: Date.now() + 1,
        role: "assistant",
        text: data.answer || "",
        sources: data.sources || [],
        retrievedSources: data.retrieved_sources || [],
        insufficientContext: !!data.insufficient_context,
        usedSourceIndexes: data.used_source_indexes || [],
        confidenceLabel: data.confidence_label,
        confidenceScore: data.confidence_score,
        retrievalMeta: data.retrieval_meta,
        timestamp: formatNowTime(),
      };
      patchActiveMessages((prev) => [...prev, botMessage]);
    } catch (err) {
      const aborted =
        err?.name === "AbortError" ||
        (typeof err?.message === "string" &&
          err.message.toLowerCase().includes("abort"));
      if (aborted) {
        setError(null);
        return;
      }
      const msg = err?.message || "Could not get an answer. Try again.";
      setError(msg);
      console.error("RAG ask error:", err);
    } finally {
      setIsLoading(false);
      abortRef.current = null;
    }
  };

  const handleSend = async (text = input) => {
    await runAsk(text, { appendUser: true });
  };

  const handleStop = () => {
    abortRef.current?.abort();
  };

  const startNewChat = () => {
    const id =
      typeof crypto !== "undefined" && crypto.randomUUID
        ? crypto.randomUUID()
        : `s-${Date.now()}`;
    const fresh = {
      id,
      title: "New chat",
      updatedAt: Date.now(),
      messages: [greetingMessage()],
    };
    setSessions((prev) => [fresh, ...prev]);
    setActiveId(id);
    setError(null);
    setExpandedSources({});
    setEditingUserMsgId(null);
    setEditDraft("");
  };

  const selectSession = (sessionId) => {
    setActiveId(sessionId);
    setError(null);
    setExpandedSources({});
    setEditingUserMsgId(null);
    setEditDraft("");
  };

  const deleteSession = (e, sessionId) => {
    e.stopPropagation();
    if (!window.confirm("Delete this chat? This cannot be undone.")) return;

    const remaining = sessions.filter((s) => s.id !== sessionId);
    if (remaining.length === 0) {
      const id =
        typeof crypto !== "undefined" && crypto.randomUUID
          ? crypto.randomUUID()
          : `s-${Date.now()}`;
      setSessions([
        {
          id,
          title: "New chat",
          updatedAt: Date.now(),
          messages: [greetingMessage()],
        },
      ]);
      setActiveId(id);
    } else {
      setSessions(remaining);
      if (activeId === sessionId) {
        const sorted = [...remaining].sort(
          (a, b) => (b.updatedAt || 0) - (a.updatedAt || 0)
        );
        setActiveId(sorted[0].id);
      }
    }
    setExpandedSources({});
    setError(null);
  };

  const copyText = async (label, t) => {
    try {
      await navigator.clipboard.writeText(t || "");
    } catch (_) {
      setError(`Could not copy ${label}`);
    }
  };

  const retryUserMessage = (userMsgId) => {
    const idx = messages.findIndex((m) => m.id === userMsgId);
    if (idx < 0) return;
    const text = messages[idx].text;
    setEditingUserMsgId(null);
    setEditDraft("");
    patchActiveMessages((msgs) => msgs.slice(0, idx + 1));
    runAsk(text, { appendUser: false });
  };

  const startEditUserMessage = (msg) => {
    if (isLoading) return;
    setEditingUserMsgId(msg.id);
    setEditDraft(msg.text || "");
  };

  const cancelEditUserMessage = () => {
    setEditingUserMsgId(null);
    setEditDraft("");
  };

  const submitEditedUserMessage = async (userMsgId) => {
    const text = editDraft.trim();
    if (!text) return;
    const idx = messages.findIndex((m) => m.id === userMsgId);
    if (idx < 0) return;
    setEditingUserMsgId(null);
    setEditDraft("");
    patchActiveMessages((msgs) => [
      ...msgs.slice(0, idx),
      {
        ...msgs[idx],
        text,
        timestamp: formatNowTime(),
      },
    ]);
    await runAsk(text, { appendUser: false });
  };

  const toggleSourceExpanded = (msgId, listPrefix, srcIndex) => {
    const key = `${msgId}-${listPrefix}-${srcIndex}`;
    setExpandedSources((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const sortedRecent = [...sessions].sort(
    (a, b) => (b.updatedAt || 0) - (a.updatedAt || 0)
  );

  return (
    <div className="flex h-[85vh] bg-[#F6F8FB] border-t border-gray-200">
      <aside className="hidden md:flex w-80 bg-white border-r border-gray-200 flex-col">
        <div className="p-6 border-b border-gray-100">
          <button
            type="button"
            onClick={startNewChat}
            className="w-full flex items-center justify-center gap-2 bg-[#052379] hover:bg-[#041d5c] text-white py-3 rounded-xl font-medium transition-colors shadow-sm"
          >
            <Plus className="w-5 h-5" />
            New Chat
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          <h3 className="text-xs font-medium text-gray-400 uppercase tracking-wider px-2 mb-2">
            Recent Conversations
          </h3>
          {sortedRecent.length === 0 ? (
            <p className="text-xs text-gray-500 px-2">No conversations yet.</p>
          ) : (
            sortedRecent.map((item) => (
              <div
                key={item.id}
                className={`flex items-stretch gap-1 rounded-lg transition-colors group ${
                  item.id === activeId
                    ? "bg-[#052379]/10 ring-1 ring-[#052379]/20"
                    : "hover:bg-gray-50"
                }`}
              >
                <button
                  type="button"
                  onClick={() => selectSession(item.id)}
                  className="flex-1 min-w-0 text-left p-3 rounded-lg"
                >
                  <div className="flex items-center gap-3 mb-1">
                    <MessageSquare
                      className={`w-4 h-4 shrink-0 ${
                        item.id === activeId
                          ? "text-[#052379]"
                          : "text-gray-400 group-hover:text-[#052379]"
                      }`}
                    />
                    <span className="text-sm text-gray-900 font-medium truncate">
                      {item.title || "Chat"}
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5 pl-7">
                    <Clock className="w-3 h-3 text-gray-400" />
                    <span className="text-xs text-gray-500">
                      {formatRelativeTime(item.updatedAt || Date.now())}
                    </span>
                  </div>
                </button>
                <button
                  type="button"
                  onClick={(e) => deleteSession(e, item.id)}
                  className="shrink-0 self-stretch px-2 mr-1 my-2 rounded-md text-gray-400 hover:text-red-600 hover:bg-red-50 transition-colors"
                  title="Delete chat"
                  aria-label="Delete chat"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))
          )}
        </div>
      </aside>

      <main className="flex-1 flex flex-col relative">
        <div className="bg-white border-b border-gray-200 px-6 py-4 shadow-sm z-10">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-[#052379]/10 rounded-lg flex items-center justify-center">
              <Scale className="w-5 h-5 text-[#052379]" />
            </div>
            <h1 className="text-xl font-medium text-gray-900">
              Lawgic AI Assistant
            </h1>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-6 scroll-smooth">
          {error && (
            <div className="mx-auto max-w-3xl rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
              {error}
            </div>
          )}
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex gap-4 ${
                msg.role === "user" ? "justify-end" : "justify-start"
              }`}
            >
              {msg.role === "assistant" && (
                <div className="w-8 h-8 bg-[#052379] rounded-full flex items-center justify-center flex-shrink-0 mt-1">
                  <Scale className="w-4 h-4 text-white" />
                </div>
              )}

              <div
                className={`max-w-[80%] rounded-2xl px-5 py-3 shadow-sm ${
                  msg.role === "user"
                    ? "bg-[#052379] text-white rounded-br-none"
                    : "bg-white text-gray-800 border border-gray-100 rounded-bl-none"
                }`}
              >
                {msg.role === "user" && editingUserMsgId === msg.id ? (
                  <div className="space-y-2">
                    <textarea
                      ref={editTextareaRef}
                      value={editDraft}
                      onChange={(e) => setEditDraft(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Escape") {
                          e.preventDefault();
                          cancelEditUserMessage();
                        }
                        if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
                          e.preventDefault();
                          submitEditedUserMessage(msg.id);
                        }
                      }}
                      rows={4}
                      disabled={isLoading}
                      className="w-full min-w-[min(100%,16rem)] text-sm leading-relaxed text-white bg-white/10 placeholder-white/50 border border-white/30 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-white/40 resize-y"
                      placeholder="Edit your question…"
                      aria-label="Edit question"
                    />
                    <div className="flex flex-wrap gap-2 justify-end">
                      <button
                        type="button"
                        disabled={isLoading}
                        onClick={cancelEditUserMessage}
                        className="text-[11px] font-medium px-2 py-1 rounded-md bg-white/10 hover:bg-white/20 disabled:opacity-50"
                      >
                        Cancel
                      </button>
                      <button
                        type="button"
                        disabled={isLoading || !editDraft.trim()}
                        onClick={() => submitEditedUserMessage(msg.id)}
                        className="text-[11px] font-medium px-2 py-1 rounded-md bg-white text-[#052379] hover:bg-white/90 disabled:opacity-50"
                      >
                        Send updated question
                      </button>
                    </div>
                    <p className="text-[10px] text-white/60">
                      Ctrl+Enter to send · Esc to cancel
                    </p>
                  </div>
                ) : (
                  <p className="text-sm leading-relaxed whitespace-pre-wrap">
                    {msg.text}
                  </p>
                )}

                {msg.role === "assistant" && msg.insufficientContext && (
                  <p className="mt-2 text-xs font-medium text-amber-800 bg-amber-50 border border-amber-100 rounded-lg px-2 py-1.5">
                    Marked as insufficient context in the model output — verify
                    against the sources below.
                  </p>
                )}

                {msg.role === "assistant" &&
                  Array.isArray(msg.usedSourceIndexes) &&
                  msg.usedSourceIndexes.length > 0 && (
                    <p className="mt-2 text-[11px] text-gray-500">
                      Sources referenced in model output:{" "}
                      {msg.usedSourceIndexes.join(", ")}
                    </p>
                  )}

                {msg.role === "assistant" &&
                  (msg.confidenceLabel != null ||
                    msg.confidenceScore != null) && (
                    <p className="mt-2 text-xs text-gray-500">
                      Retrieval confidence:{" "}
                      <span className="font-medium text-gray-700">
                        {msg.confidenceLabel}
                      </span>
                      {msg.confidenceScore != null && (
                        <span>
                          {" "}
                          ({Number(msg.confidenceScore).toFixed(2)})
                        </span>
                      )}
                    </p>
                  )}

                {msg.role === "assistant" &&
                  (() => {
                    const used = Array.isArray(msg.sources) ? msg.sources : [];
                    const retr = Array.isArray(msg.retrievedSources)
                      ? msg.retrievedSources
                      : [];
                    const blocks = [];
                    if (used.length)
                      blocks.push({
                        title: "Sources used in answer",
                        prefix: "u",
                        items: used,
                      });
                    if (retr.length)
                      blocks.push({
                        title:
                          "Retrieved passages (no used indexes reported by model)",
                        prefix: "r",
                        items: retr,
                      });
                    if (!blocks.length) return null;
                    return (
                      <div className="mt-3 border-t border-gray-100 pt-3 text-left space-y-3">
                        {blocks.map((block) => (
                          <div key={block.prefix}>
                            <p className="text-xs font-semibold text-gray-600 mb-1.5">
                              {block.title}
                            </p>
                            <ul className="space-y-1.5 text-xs text-gray-800">
                              {block.items.map((src, i) => {
                                const expKey = `${msg.id}-${block.prefix}-${i}`;
                                const expanded = !!expandedSources[expKey];
                                const full = src.full_source_text || "";
                                const line = formatSourceOneLine(src);
                                return (
                                  <li
                                    key={`${block.prefix}-${src.object_id || i}-${i}`}
                                    className="rounded-lg border border-gray-100 bg-gray-50/80 px-2 py-1.5"
                                  >
                                    <div className="flex items-start justify-between gap-2">
                                      <p
                                        className="min-w-0 flex-1 leading-snug truncate"
                                        title={line}
                                      >
                                        {line}
                                      </p>
                                      {full ? (
                                        <button
                                          type="button"
                                          onClick={() =>
                                            toggleSourceExpanded(
                                              msg.id,
                                              block.prefix,
                                              i
                                            )
                                          }
                                          className="shrink-0 text-[11px] font-medium text-[#052379] hover:underline whitespace-nowrap"
                                        >
                                          {expanded ? (
                                            <span className="inline-flex items-center gap-0.5">
                                              <ChevronUp className="w-3 h-3" />
                                              Hide
                                            </span>
                                          ) : (
                                            <span className="inline-flex items-center gap-0.5">
                                              <ChevronDown className="w-3 h-3" />
                                              Show full source
                                            </span>
                                          )}
                                        </button>
                                      ) : null}
                                    </div>
                                    {expanded && full ? (
                                      <div className="mt-2 text-gray-700 whitespace-pre-wrap text-[11px] leading-relaxed max-h-64 overflow-y-auto border-t border-gray-100 pt-2">
                                        {full}
                                      </div>
                                    ) : null}
                                  </li>
                                );
                              })}
                            </ul>
                          </div>
                        ))}
                      </div>
                    );
                  })()}

                <div
                  className={`flex flex-wrap items-center gap-2 mt-2 ${
                    msg.role === "user" ? "justify-end" : "justify-start"
                  }`}
                >
                  <span
                    className={`text-[10px] opacity-70 ${
                      msg.role === "user" ? "order-last" : ""
                    }`}
                  >
                    {msg.timestamp}
                  </span>
                  {msg.role === "user" &&
                    msg.id !== "greeting" &&
                    editingUserMsgId !== msg.id && (
                    <>
                      <button
                        type="button"
                        onClick={() => copyText("question", msg.text)}
                        className="inline-flex items-center gap-1 text-[10px] font-medium text-white/90 hover:text-white"
                      >
                        <Copy className="w-3 h-3" />
                        Copy
                      </button>
                      <button
                        type="button"
                        disabled={isLoading}
                        onClick={() => startEditUserMessage(msg)}
                        className="inline-flex items-center gap-1 text-[10px] font-medium text-white/90 hover:text-white disabled:opacity-50"
                      >
                        <Pencil className="w-3 h-3" />
                        Edit
                      </button>
                      <button
                        type="button"
                        disabled={isLoading}
                        onClick={() => retryUserMessage(msg.id)}
                        className="inline-flex items-center gap-1 text-[10px] font-medium text-white/90 hover:text-white disabled:opacity-50"
                      >
                        <RotateCcw className="w-3 h-3" />
                        Retry
                      </button>
                    </>
                  )}
                  {msg.role === "assistant" && (
                    <button
                      type="button"
                      onClick={() => copyText("answer", msg.text)}
                      className="inline-flex items-center gap-1 text-[10px] font-medium text-[#052379] hover:underline"
                    >
                      <Copy className="w-3 h-3" />
                      Copy
                    </button>
                  )}
                </div>
              </div>

              {msg.role === "user" && (
                <div className="w-8 h-8 bg-gray-200 rounded-full flex items-center justify-center flex-shrink-0 mt-1">
                  <User className="w-4 h-4 text-gray-500" />
                </div>
              )}
            </div>
          ))}

          {isLoading && (
            <div className="flex gap-4">
              <div className="w-8 h-8 bg-[#052379] rounded-full flex items-center justify-center flex-shrink-0">
                <Scale className="w-4 h-4 text-white" />
              </div>
              <div className="bg-white px-5 py-3 rounded-2xl rounded-bl-none border border-gray-100 shadow-sm flex items-center gap-3">
                <Loader2 className="w-4 h-4 text-[#052379] animate-spin" />
                <span className="text-sm text-gray-500">
                  Processing legal text…
                </span>
                <button
                  type="button"
                  onClick={handleStop}
                  className="ml-2 inline-flex items-center gap-1 rounded-lg border border-gray-200 bg-gray-50 px-2 py-1 text-xs font-medium text-gray-700 hover:bg-gray-100"
                >
                  <Square className="w-3 h-3" />
                  Stop
                </button>
              </div>
            </div>
          )}
        </div>

        <div className="p-6 bg-white border-t border-gray-200">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSend();
            }}
            className="relative flex items-center"
          >
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Type your legal question..."
              disabled={isLoading}
              className="w-full bg-[#F6F8FB] text-gray-900 placeholder-gray-500 border border-gray-200 rounded-xl pl-4 pr-14 py-3.5 focus:outline-none focus:ring-2 focus:ring-[#052379]/20 focus:border-[#052379] transition-all"
            />
            <button
              type="submit"
              disabled={!input.trim() || isLoading}
              className="absolute right-2 p-2 bg-[#052379] text-white rounded-lg hover:bg-[#041d5c] disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
            >
              <Send className="w-4 h-4" />
            </button>
          </form>
          <p className="text-center text-xs text-gray-400 mt-3">
            Lawgic AI can make mistakes. Always consult a verified lawyer for
            critical matters.
          </p>
        </div>
      </main>
    </div>
  );
}
"use client";

import React from 'react';
import {
  Send,
  Plus,
  MessageSquare,
  Clock,
  Scale,
  User,
} from 'lucide-react';

export default function AiQAPage() {
  const messages = [
    {
      id: 1,
      role: 'assistant',
      text: "Hello! I'm your AI legal assistant. I can help you understand Pakistani laws, draft documents, or find legal procedures. How can I help you today?",
      timestamp: 'Just now'
    },
    {
      id: 2,
      role: 'user',
      text: 'What are tenant rights in Pakistan?',
      timestamp: '10:24 AM'
    },
    {
      id: 3,
      role: 'assistant',
      text: 'Tenant rights in Pakistan generally depend on the tenancy agreement and local rent laws. Common areas include rent amount, notice period, eviction process, and maintenance responsibilities.',
      timestamp: '10:25 AM'
    }
  ];

  const history = [
    { id: 1, title: 'Tenant Rights Question', time: '2h ago' },
    { id: 2, title: 'Property Dispute', time: '1d ago' },
    { id: 3, title: 'Divorce Process', time: '3d ago' },
  ];

  const quickQuestions = [
    "Tenant rights in Pakistan",
    "How to file an FIR",
    "Rent agreement dispute",
    "Property inheritance laws"
  ];

  return (
    <div className="flex h-[85vh] bg-[#F6F8FB] border-t border-gray-200">
      <aside className="hidden md:flex w-80 bg-white border-r border-gray-200 flex-col">
        <div className="p-6 border-b border-gray-100">
          <button className="w-full flex items-center justify-center gap-2 bg-[#052379] text-white py-3 rounded-xl font-medium shadow-sm">
            <Plus className="w-5 h-5" />
            New Chat
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          <h3 className="text-xs font-medium text-gray-400 uppercase tracking-wider px-2 mb-2">
            Recent Conversations
          </h3>
          {history.map((item) => (
            <div
              key={item.id}
              className="w-full text-left p-3 rounded-lg hover:bg-gray-50 transition-colors group cursor-pointer"
            >
              <div className="flex items-center gap-3 mb-1">
                <MessageSquare className="w-4 h-4 text-gray-400 group-hover:text-[#052379]" />
                <span className="text-sm text-gray-900 font-medium truncate">{item.title}</span>
              </div>
              <div className="flex items-center gap-1.5 pl-7">
                <Clock className="w-3 h-3 text-gray-400" />
                <span className="text-xs text-gray-500">{item.time}</span>
              </div>
            </div>
          ))}
        </div>
      </aside>

      <main className="flex-1 flex flex-col relative">
        <div className="bg-white border-b border-gray-200 px-6 py-4 shadow-sm z-10">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-[#052379]/10 rounded-lg flex items-center justify-center">
              <Scale className="w-5 h-5 text-[#052379]" />
            </div>
            <h1 className="text-xl font-medium text-gray-900">Lawgic AI Assistant</h1>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-6 scroll-smooth">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex gap-4 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              {msg.role === 'assistant' && (
                <div className="w-8 h-8 bg-[#052379] rounded-full flex items-center justify-center flex-shrink-0 mt-1">
                  <Scale className="w-4 h-4 text-white" />
                </div>
              )}

              <div
                className={`max-w-[80%] rounded-2xl px-5 py-3 shadow-sm ${
                  msg.role === 'user'
                    ? 'bg-[#052379] text-white rounded-br-none'
                    : 'bg-white text-gray-800 border border-gray-100 rounded-bl-none'
                }`}
              >
                <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.text}</p>
                <span
                  className={`text-[10px] mt-2 block opacity-70 ${
                    msg.role === 'user' ? 'text-right' : 'text-left'
                  }`}
                >
                  {msg.timestamp}
                </span>
              </div>

              {msg.role === 'user' && (
                <div className="w-8 h-8 bg-gray-200 rounded-full flex items-center justify-center flex-shrink-0 mt-1">
                  <User className="w-4 h-4 text-gray-500" />
                </div>
              )}
            </div>
          ))}

          <div className="mt-8">
            <p className="text-sm text-gray-500 mb-4 px-12">Quick Questions</p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 px-12">
              {quickQuestions.map((q, idx) => (
                <div
                  key={idx}
                  className="text-left px-4 py-3 bg-white border border-gray-200 rounded-xl text-sm text-gray-700 hover:border-[#052379] hover:text-[#052379] hover:shadow-sm transition-all cursor-pointer"
                >
                  {q}
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="p-6 bg-white border-t border-gray-200">
          <div className="relative flex items-center">
            <input
              type="text"
              placeholder="Type your legal question..."
              className="w-full bg-[#F6F8FB] text-gray-900 placeholder-gray-500 border border-gray-200 rounded-xl pl-4 pr-14 py-3.5 focus:outline-none"
            />
            <button
              type="button"
              className="absolute right-2 p-2 bg-[#052379] text-white rounded-lg"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
          <p className="text-center text-xs text-gray-400 mt-3">
            Lawgic AI can make mistakes. Always consult a verified lawyer for critical matters.
          </p>
        </div>
      </main>
    </div>
  );
}
