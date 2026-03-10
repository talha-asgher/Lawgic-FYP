"use client";

import React, { useState, useEffect, useRef } from 'react';
import { useParams } from 'next/navigation';
import { ChevronLeft, Send, Loader2 } from 'lucide-react';
import { getConversationMessages, sendConversationMessage, getMyConversations, getUser, isLoggedIn } from '@/lib/api';

export default function ChatThreadPage() {
  const { id } = useParams();
  const [messages, setMessages] = useState([]);
  const [newMessage, setNewMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [convTitle, setConvTitle] = useState('');
  const messagesContainerRef = useRef(null);
  const bottomRef = useRef(null);
  const currentUser = getUser();

  useEffect(() => {
    if (!isLoggedIn()) { window.location.href = '/login'; return; }
    if (!id) return;
    const load = async () => {
      try {
        const [msgs, convs] = await Promise.all([
          getConversationMessages(id),
          getMyConversations().catch(() => []),
        ]);
        setMessages(msgs);
        const conv = convs.find(c => c.conv_id === parseInt(id));
        if (conv && currentUser) {
          const other = conv.participants?.find(p => p.user_id !== currentUser.user_id);
          setConvTitle(other?.name || 'Conversation');
        }
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    load();
    const interval = setInterval(async () => {
      try {
        const msgs = await getConversationMessages(id);
        setMessages(msgs);
      } catch {}
    }, 5000);
    return () => clearInterval(interval);
  }, [id]);

  useEffect(() => {
    const container = messagesContainerRef.current;
    if (!container) return;
  }, [messages]);

  const handleSend = async (e) => {
    e.preventDefault();
    if (!newMessage.trim() || sending) return;
    setSending(true);
    try {
      const msg = await sendConversationMessage(id, newMessage.trim());
      setMessages(prev => [...prev, msg]);
      setNewMessage('');
    } catch (err) {
      alert(err.message || 'Failed to send message');
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-80px)] bg-[#F6F8FB]">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-4 py-3 flex items-center gap-3 shadow-sm">
        <button onClick={() => window.location.href = '/chat'}
          className="text-gray-600 hover:text-gray-900">
          <ChevronLeft className="w-5 h-5" />
        </button>
        <div className="w-9 h-9 bg-[#052379] rounded-full flex items-center justify-center text-white text-sm font-medium">
          {convTitle.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase() || 'C'}
        </div>
        <div>
          <h2 className="font-medium text-gray-900 text-sm">{convTitle || 'Conversation'}</h2>
          <p className="text-xs text-gray-400">Active now</p>
        </div>
      </div>

      {/* Messages */}
      <div
        ref={messagesContainerRef}
        className="flex-1 overflow-y-auto p-4 space-y-3"
      >
        {loading ? (
          <div className="flex justify-center py-8"><Loader2 className="w-6 h-6 text-[#052379] animate-spin" /></div>
        ) : messages.length === 0 ? (
          <div className="text-center py-8 text-gray-400 text-sm">No messages yet. Start the conversation!</div>
        ) : (
          messages.map(msg => {
            const isMe = msg.sender_id === currentUser?.user_id;
            return (
              <div key={msg.message_id} className={`flex ${isMe ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-xs lg:max-w-md px-4 py-2.5 rounded-2xl text-sm
                  ${isMe ? 'bg-[#052379] text-white rounded-br-sm' : 'bg-white text-gray-900 border border-gray-200 rounded-bl-sm shadow-sm'}`}>
                  {!isMe && <p className="text-xs font-medium text-gray-500 mb-1">{msg.sender_name}</p>}
                  <p>{msg.content}</p>
                  <p className={`text-[10px] mt-1 ${isMe ? 'text-blue-200' : 'text-gray-400'}`}>
                    {new Date(msg.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </p>
                </div>
              </div>
            );
          })
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSend} className="bg-white border-t border-gray-200 p-4 flex items-center gap-3">
        <input
          type="text"
          value={newMessage}
          onChange={(e) => setNewMessage(e.target.value)}
          placeholder="Type a message..."
          className="flex-1 px-4 py-2.5 bg-[#F6F8FB] border border-gray-200 rounded-xl text-sm text-black placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-[#052379]/20"
        />
        <button
          type="submit"
          disabled={!newMessage.trim() || sending}
          className="w-10 h-10 bg-[#052379] rounded-xl flex items-center justify-center text-white hover:bg-[#041d5c] transition-colors disabled:opacity-40"
        >
          {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
        </button>
      </form>
    </div>
  );
}
