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