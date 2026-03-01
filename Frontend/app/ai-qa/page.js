"use client";

import React, { useState, useRef, useEffect } from 'react';
import { 
  Send, 
  Plus, 
  MessageSquare, 
  Clock, 
  Scale, 
  User, 
  Loader2,
  ChevronRight
} from 'lucide-react';

export default function AiQAPage() {
  
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  
 
  const [messages, setMessages] = useState([
    {
      id: 1,
      role: 'assistant',
      text: "Hello! I'm your AI legal assistant. I can help you understand Pakistani laws, draft documents, or find legal procedures. How can I help you today?",
      timestamp: 'Just now' 
    }
  ]);

  
  const [history, setHistory] = useState([
    { id: 1, title: 'Tenant Rights Question', time: '2h ago' },
    { id: 2, title: 'Property Dispute', time: '1d ago' },
    { id: 3, title: 'Divorce Process', time: '3d ago' },
  ]);

  const messagesEndRef = useRef(null);

  
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async (text = input) => {
    if (!text.trim()) return;

    const currentTime = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    const userMessage = {
      id: Date.now(),
      role: 'user',
      text: text,
      timestamp: currentTime
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
    
      // CONNECTBACKEND HERE
      
      /*
      const response = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, history: messages })
      });
      const data = await response.json();
      const botResponseText = data.reply; 
      */

      // MOCK SIMULATION 
      
      await new Promise(resolve => setTimeout(resolve, 1500)); // Simulate thinking
      const botResponseText = "This is a simulated response based on Pakistani Law. [Backend Integration Required]";
      

    
      const botMessage = {
        id: Date.now() + 1,
        role: 'assistant',
        text: botResponseText,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      };
      setMessages(prev => [...prev, botMessage]);

    } catch (error) {
      console.error("Chat Error:", error);
      // Handle error state here
    } finally {
      setIsLoading(false);
    }
  };

  const handleQuickQuestion = (question) => {
    handleSend(question);
  };

  const startNewChat = () => {
    setMessages([messages[0]]); // Reset to greeting
   
  };

  return (
   
    <div className="flex h-[85vh] bg-[#F6F8FB] border-t border-gray-200"> 
      
      {/* SIDEBAR */}
      <aside className="hidden md:flex w-80 bg-white border-r border-gray-200 flex-col">
        {/* New Chat Button */}
        <div className="p-6 border-b border-gray-100">
          <button 
            onClick={startNewChat}
            className="w-full flex items-center justify-center gap-2 bg-[#052379] hover:bg-[#041d5c] text-white py-3 rounded-xl font-medium transition-colors shadow-sm"
          >
            <Plus className="w-5 h-5" />
            New Chat
          </button>
        </div>

        {/* History List */}
        <div className="flex-1 overflow-y-auto p-4 space-y-2">
          <h3 className="text-xs font-medium text-gray-400 uppercase tracking-wider px-2 mb-2">
            Recent Conversations
          </h3>
          {history.map((item) => (
            <button 
              key={item.id}
              className="w-full text-left p-3 rounded-lg hover:bg-gray-50 transition-colors group"
            >
              <div className="flex items-center gap-3 mb-1">
                <MessageSquare className="w-4 h-4 text-gray-400 group-hover:text-[#052379]" />
                <span className="text-sm text-gray-900 font-medium truncate">{item.title}</span>
              </div>
              <div className="flex items-center gap-1.5 pl-7">
                <Clock className="w-3 h-3 text-gray-400" />
                <span className="text-xs text-gray-500">{item.time}</span>
              </div>
            </button>
          ))}
        </div>
      </aside>

      {/*  MAIN CHAT AREA  */}
      <main className="flex-1 flex flex-col relative">
        
        {/* Chat Header */}
        <div className="bg-white border-b border-gray-200 px-6 py-4 shadow-sm z-10">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-[#052379]/10 rounded-lg flex items-center justify-center">
              <Scale className="w-5 h-5 text-[#052379]" />
            </div>
            <h1 className="text-xl font-medium text-gray-900">Lawgic AI Assistant</h1>
          </div>
        </div>

        {/* Messages Container */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6 scroll-smooth">
          {messages.map((msg) => (
            <div 
              key={msg.id} 
              className={`flex gap-4 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              {/* Assistant area */}
              {msg.role === 'assistant' && (
                <div className="w-8 h-8 bg-[#052379] rounded-full flex items-center justify-center flex-shrink-0 mt-1">
                  <Scale className="w-4 h-4 text-white" />
                </div>
              )}

              {/* Message Bubble */}
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

              {/* user  */}
              {msg.role === 'user' && (
                <div className="w-8 h-8 bg-gray-200 rounded-full flex items-center justify-center flex-shrink-0 mt-1">
                  <User className="w-4 h-4 text-gray-500" />
                </div>
              )}
            </div>
          ))}

          {/* Quick Suggestions */}
          {messages.length < 3 && !isLoading && (
            <div className="mt-8">
              <p className="text-sm text-gray-500 mb-4 px-12">Quick Questions</p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 px-12">
                {[
                  "Tenant rights in Pakistan", 
                  "How to file an FIR", 
                  "Rent agreement dispute", 
                  "Property inheritance laws"
                ].map((q, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleQuickQuestion(q)}
                    className="text-left px-4 py-3 bg-white border border-gray-200 rounded-xl text-sm text-gray-700 hover:border-[#052379] hover:text-[#052379] hover:shadow-sm transition-all"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Loading Indicator */}
          {isLoading && (
            <div className="flex gap-4">
              <div className="w-8 h-8 bg-[#052379] rounded-full flex items-center justify-center flex-shrink-0">
                <Scale className="w-4 h-4 text-white" />
              </div>
              <div className="bg-white px-5 py-3 rounded-2xl rounded-bl-none border border-gray-100 shadow-sm flex items-center gap-2">
                <Loader2 className="w-4 h-4 text-[#052379] animate-spin" />
                <span className="text-sm text-gray-500">Analyzing legal context...</span>
              </div>
            </div>
          )}
          
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="p-6 bg-white border-t border-gray-200">
          <form 
            onSubmit={(e) => { e.preventDefault(); handleSend(); }}
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
            Lawgic AI can make mistakes. Always consult a verified lawyer for critical matters.
          </p>
        </div>

      </main>
    </div>
  );
}