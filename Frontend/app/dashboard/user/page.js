"use client";

import React, { useState, useEffect } from 'react';
import { 
  Plus, 
  MessageSquare, 
  Clock, 
  FileText, 
  Calendar, 
  Settings, 
  Edit, 
  User,
  CheckCircle,
  FileCheck
} from 'lucide-react';

export default function UserDashboard() {
  // --- STATE MANAGEMENT ---
  const [loading, setLoading] = useState(true);
  
  // 1. User Profile State
  const [user, setUser] = useState({
    name: "John Doe",
    email: "johndoe@example.com",
    location: "Karachi, Pakistan",
    initials: "JD"
  });

  // 2. Stats State
  const [stats, setStats] = useState({
    documents: 12,
    chats: 5,
    appointments: 3
  });

  // 3. Recent Activity State
  const [activities, setActivities] = useState([
    {
      id: 1,
      title: "Document analyzed",
      time: "2 hours ago",
      type: "document",
      icon: <FileCheck className="w-5 h-5 text-blue-600" />,
      bg: "bg-blue-50"
    },
    {
      id: 2,
      title: "Appointment booked",
      time: "1 day ago",
      type: "appointment",
      icon: <CheckCircle className="w-5 h-5 text-emerald-600" />,
      bg: "bg-emerald-50"
    }
  ]);

  // 4. Chat History State (Sidebar)
  const [chatHistory, setChatHistory] = useState([
    { id: 1, title: 'Tenant Rights Question', time: '2h ago' },
    { id: 2, title: 'Property Dispute', time: '1d ago' },
    { id: 3, title: 'Divorce Process', time: '3d ago' },
  ]);

  useEffect(() => {
    const fetchDashboardData = async () => {
      try {
        setLoading(true);
       
        //  CONNECT BACKEND
       
        
        /*
        // 1. Fetch User Profile
        const userRes = await fetch('http://localhost:5000/api/user/profile');
        const userData = await userRes.json();
        setUser(userData);

        // 2. Fetch Stats
        const statsRes = await fetch('http://localhost:5000/api/user/stats');
        const statsData = await statsRes.json();
        setStats(statsData);

        // 3. Fetch Activity
        const activityRes = await fetch('http://localhost:5000/api/user/activity');
        const activityData = await activityRes.json();
        setActivities(activityData);
        */

        await new Promise(resolve => setTimeout(resolve, 800)); // Simulate loading

      } catch (error) {
        console.error("Failed to fetch dashboard data:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchDashboardData();
  }, []);

  return (
    <div className="flex min-h-[calc(100vh-80px)] bg-[#F6F8FB]">
      
      {/*  SIDEBAR  */}
      <aside className="hidden lg:flex w-80 bg-white border-r border-gray-200 flex-col sticky top-0 h-screen overflow-y-auto">
        
        {/* New Chat Button */}
        <div className="p-6 border-b border-gray-100">
          <button className="w-full flex items-center justify-center gap-2 bg-[#052379] hover:bg-[#041d5c] text-white py-3 rounded-xl font-medium transition-colors shadow-sm">
            <Plus className="w-5 h-5" />
            New Chat
          </button>
        </div>

        {/* History List */}
        <div className="flex-1 p-4 space-y-2">
          <h3 className="text-xs font-medium text-gray-400 uppercase tracking-wider px-2 mb-2">
            Recent Conversations
          </h3>
          {chatHistory.map((item) => (
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

      {/* main contnt  */}
      <main className="flex-1 p-6 lg:p-12 overflow-y-auto">
        
        {/* Profile  Card */}
        <div className="bg-white rounded-2xl border border-gray-200 p-6 mb-8 flex flex-col md:flex-row items-start md:items-center gap-6 shadow-sm">
         
          <div className="w-24 h-24 bg-gray-100 rounded-full flex items-center justify-center flex-shrink-0">
            <span className="text-3xl font-medium text-gray-600">{user.initials}</span>
          </div>
          
          {/* Info */}
          <div className="flex-1 space-y-1">
            <h1 className="text-2xl font-semibold text-gray-900">{user.name}</h1>
            <p className="text-gray-500">{user.email}</p>
            <p className="text-gray-500 flex items-center gap-1">
              <span className="w-2 h-2 bg-green-500 rounded-full inline-block" />
              {user.location}
            </p>
          </div>

          {/* Edit Button */}
          <button className="flex items-center gap-2 px-4 py-2 border border-gray-200 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors">
            <Edit className="w-4 h-4" />
            Edit Profile
          </button>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          
          {/* Documents Stat */}
          <div className="bg-white p-6 rounded-2xl border border-gray-200 hover:shadow-md transition-shadow">
            <div className="flex items-center gap-4 mb-4">
              <div className="w-12 h-12 bg-blue-50 rounded-xl flex items-center justify-center">
                <FileText className="w-6 h-6 text-blue-600" />
              </div>
              <span className="text-sm font-medium text-gray-500">My Documents</span>
            </div>
            <div className="text-4xl font-bold text-gray-900">{stats.documents}</div>
          </div>

          {/* Chats Stat */}
          <div className="bg-white p-6 rounded-2xl border border-gray-200 hover:shadow-md transition-shadow">
            <div className="flex items-center gap-4 mb-4">
              <div className="w-12 h-12 bg-purple-50 rounded-xl flex items-center justify-center">
                <MessageSquare className="w-6 h-6 text-purple-600" />
              </div>
              <span className="text-sm font-medium text-gray-500">My Chats</span>
            </div>
            <div className="text-4xl font-bold text-gray-900">{stats.chats}</div>
          </div>

          {/* Appointments */}
          <div className="bg-white p-6 rounded-2xl border border-gray-200 hover:shadow-md transition-shadow">
            <div className="flex items-center gap-4 mb-4">
              <div className="w-12 h-12 bg-amber-50 rounded-xl flex items-center justify-center">
                <Calendar className="w-6 h-6 text-amber-600" />
              </div>
              <span className="text-sm font-medium text-gray-500">Appointments</span>
            </div>
            <div className="text-4xl font-bold text-gray-900">{stats.appointments}</div>
          </div>
        </div>

        {/*  Activity Section */}
        <div className="bg-white rounded-2xl border border-gray-200 p-6">
          <h2 className="text-lg font-medium text-gray-900 mb-6">Recent Activity</h2>
          
          <div className="space-y-4">
            {activities.map((activity) => (
              <div key={activity.id} className="flex items-center gap-4 p-4 bg-[#F6F8FB] rounded-xl">
                <div className={`w-10 h-10 ${activity.bg} rounded-full flex items-center justify-center flex-shrink-0`}>
                  {activity.icon}
                </div>
                <div className="flex-1">
                  <h4 className="text-sm font-medium text-gray-900">{activity.title}</h4>
                  <p className="text-xs text-gray-500">{activity.time}</p>
                </div>
              </div>
            ))}
            
            {/* if no activity*/}
            {activities.length === 0 && (
              <p className="text-gray-500 text-sm text-center py-4">No recent activity found.</p>
            )}
          </div>
        </div>

      </main>
    </div>
  );
}