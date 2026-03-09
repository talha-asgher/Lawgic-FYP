"use client";

import React, { useState, useEffect } from 'react';
import { MessageSquare, Loader2, Search } from 'lucide-react';
import { getMyConversations, getUser, isLoggedIn } from '@/lib/api';

export default function ChatListPage() {
  const [conversations, setConversations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    if (!isLoggedIn()) { window.location.href = '/login'; return; }
    const load = async () => {
      try {
        const data = await getMyConversations();
        setConversations(data);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const currentUser = getUser();

  const filtered = conversations.filter(c => {
    const other = c.participants?.find(p => p.user_id !== currentUser?.user_id);
    return !searchQuery || other?.name?.toLowerCase().includes(searchQuery.toLowerCase());
  });

  return (
    <div className="min-h-screen bg-[#F6F8FB] px-4 lg:px-8 py-8">
      <div className="max-w-2xl mx-auto">
        <h1 className="text-2xl font-semibold text-gray-900 mb-6">Messages</h1>
        <div className="relative mb-4">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
          <input type="text" value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
            placeholder="Search conversations..."
            className="w-full pl-10 pr-4 py-2.5 bg-white border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-[#052379]/20" />
        </div>
        {loading ? (
          <div className="flex justify-center py-12"><Loader2 className="w-8 h-8 text-[#052379] animate-spin" /></div>
        ) : filtered.length === 0 ? (
          <div className="bg-white rounded-2xl border border-gray-200 p-12 text-center">
            <MessageSquare className="w-12 h-12 text-gray-300 mx-auto mb-3" />
            <p className="text-gray-500">No conversations yet.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {filtered.map(conv => {
              const other = conv.participants?.find(p => p.user_id !== currentUser?.user_id);
              const initials = other?.name?.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase() || '?';
              return (
                <button key={conv.conv_id}
                  onClick={() => { window.location.href = '/chat/' + conv.conv_id; }}
                  className="w-full flex items-center gap-4 bg-white rounded-2xl border border-gray-200 p-4 hover:shadow-md transition-all text-left">
                  <div className="w-12 h-12 bg-[#052379] rounded-full flex items-center justify-center text-white font-medium flex-shrink-0">
                    {initials}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <h3 className="font-medium text-gray-900 text-sm">{other?.name || 'Unknown'}</h3>
                      {conv.last_message_at && (
                        <span className="text-xs text-gray-400">{new Date(conv.last_message_at).toLocaleDateString()}</span>
                      )}
                    </div>
                    <p className="text-sm text-gray-500 truncate">{conv.last_message || 'No messages yet'}</p>
                  </div>
                  {conv.unread_count > 0 && (
                    <span className="w-5 h-5 bg-red-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center flex-shrink-0">
                      {conv.unread_count}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
