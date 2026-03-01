"use client";

import React, { useState, useEffect } from 'react';
import { 
  Users, 
  Calendar, 
  DollarSign, 
  Star, 
  Edit, 
  Clock, 
  MessageSquare, 
  CheckCircle, 
  AlertCircle,
  Settings,
  MoreVertical
} from 'lucide-react';

export default function LawyerDashboard() {

  const [loading, setLoading] = useState(true);
  const [profile, setProfile] = useState({
    name: "",
    email: "",
    barId: "",
    rating: 0,
    initials: ""
  });
  const [stats, setStats] = useState({
    activeClients: 0,
    appointmentsThisWeek: 0,
    earnings: "0",
    averageRating: 0
  });
  const [appointments, setAppointments] = useState([]);
  const [messages, setMessages] = useState([]);

  
  useEffect(() => {
    const fetchDashboardData = async () => {
      try {
        setLoading(true);

        // backend here
        
        /* // Example API Call structure:
        const response = await fetch('http://localhost:5000/api/lawyer/dashboard', {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        const data = await response.json();
        setProfile(data.profile);
        setStats(data.stats);
        // ... map other data
        */
        await new Promise(resolve => setTimeout(resolve, 800)); // Simulate latency

        setProfile({
          name: "Advocate Ali Ahmed",
          email: "ali.ahmed@lawfirm.pk",
          barId: "L/12345/2015",
          rating: 4.8,
          initials: "AA"
        });

        setStats({
          activeClients: 24,
          appointmentsThisWeek: 8,
          earnings: "125K",
          averageRating: 4.8
        });

        setAppointments([
          {
            id: 1,
            clientName: "Advocate Sarah Khan", 
            date: "2025-10-15",
            time: "10:00 AM",
            status: "Confirmed",
            type: "confirmed"
          },
          {
            id: 2,
            clientName: "Advocate Ahmed Malik",
            date: "2025-10-12",
            time: "2:30 PM",
            status: "Pending",
            type: "pending"
          }
        ]);

        setMessages([
          {
            id: 1,
            sender: "Ahmed Khan",
            text: "Need consultation about property dispute",
            time: "2 hours ago",
            isNew: true
          },
          {
            id: 2,
            sender: "Sara Ali",
            text: "Following up on divorce case",
            time: "5 hours ago",
            isNew: true
          },
          {
            id: 3,
            sender: "Hassan Raza",
            text: "Thank you for the consultation",
            time: "1 day ago",
            isNew: false
          }
        ]);
        

      } catch (error) {
        console.error("Failed to load dashboard:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchDashboardData();
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#F6F8FB]">
        <div className="animate-pulse flex flex-col items-center">
          <div className="h-12 w-12 bg-gray-300 rounded-full mb-4"></div>
          <div className="h-4 w-32 bg-gray-300 rounded"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#F6F8FB] p-6 lg:p-12">
      <div className="max-w-7xl mx-auto space-y-8">
        
        {/*  Profile Header */}
        <div className="bg-white rounded-2xl border border-gray-200 p-6 flex flex-col md:flex-row items-center justify-between gap-6 shadow-sm">
          <div className="flex items-center gap-6 w-full md:w-auto">
            <div className="w-24 h-24 bg-[#052379] rounded-full flex items-center justify-center flex-shrink-0 text-white text-3xl font-medium">
              {profile.initials}
            </div>
            
            <div className="space-y-1">
              <div className="flex items-center gap-3">
                <h1 className="text-2xl font-semibold text-gray-900">{profile.name}</h1>
                <div className="bg-[#052379] text-white text-xs px-2 py-0.5 rounded-full flex items-center gap-1">
                  <Star className="w-3 h-3 fill-current" />
                  {profile.rating}
                </div>
              </div>
              <p className="text-gray-500">{profile.email}</p>
              <p className="text-gray-500 text-sm">Bar Council ID: {profile.barId}</p>
            </div>
          </div>

          <button className="flex items-center gap-2 px-4 py-2 border border-gray-200 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors w-full md:w-auto justify-center">
            <Edit className="w-4 h-4" />
            Edit Profile
          </button>
        </div>

        {/* Navigation Tabs (Visual) */}
        <div className="flex flex-wrap gap-2">
          {["Overview", "Appointments", "Messages", "Availability", "Settings"].map((tab, idx) => (
            <button 
              key={tab}
              className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${
                idx === 0 
                  ? 'bg-white text-gray-900 shadow-sm ring-1 ring-gray-200' 
                  : 'text-gray-500 hover:text-gray-900 hover:bg-gray-100'
              }`}
            >
              {tab}
            </button>
          ))}
        </div>

        {/*  Stats Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          <StatCard 
            label="Active Clients" 
            value={stats.activeClients} 
            icon={<Users className="w-6 h-6 text-blue-600" />} 
            bg="bg-blue-50"
          />
          <StatCard 
            label="This Week" 
            value={stats.appointmentsThisWeek} 
            icon={<Calendar className="w-6 h-6 text-emerald-600" />} 
            bg="bg-emerald-50"
          />
          <StatCard 
            label="This Month" 
            value={`PKR ${stats.earnings}`} 
            icon={<DollarSign className="w-6 h-6 text-amber-600" />} 
            bg="bg-amber-50"
          />
          <StatCard 
            label="Average Rating" 
            value={stats.averageRating} 
            icon={<Star className="w-6 h-6 text-purple-600 fill-purple-600" />} 
            bg="bg-purple-50"
          />
        </div>

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          
          {/* Upcoming Appointments */}
          <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-medium text-gray-900">Upcoming Appointments</h2>
              <button className="text-gray-400 hover:text-gray-600">
                <MoreVertical className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-4">
              {appointments.map((apt) => (
                <div key={apt.id} className="flex items-center justify-between p-4 bg-[#F6F8FB] rounded-xl">
                  <div>
                    <h3 className="text-sm font-medium text-gray-900">{apt.clientName}</h3>
                    <div className="flex items-center gap-2 mt-1 text-xs text-gray-500">
                      <span>{apt.date}</span>
                      <span>•</span>
                      <span>{apt.time}</span>
                    </div>
                  </div>
                  <span className={`px-3 py-1 rounded-full text-xs font-medium ${
                    apt.type === 'confirmed' 
                      ? 'bg-emerald-100 text-emerald-700' 
                      : 'bg-amber-100 text-amber-700'
                  }`}>
                    {apt.status}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Recent Messages */}
          <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-medium text-gray-900">Recent Messages</h2>
              <button className="text-gray-400 hover:text-gray-600">
                <MoreVertical className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-4">
              {messages.map((msg) => (
                <div key={msg.id} className="p-4 bg-[#F6F8FB] rounded-xl hover:bg-gray-50 transition-colors cursor-pointer group">
                  <div className="flex justify-between items-start mb-1">
                    <div className="flex items-center gap-2">
                      <h3 className="text-sm font-medium text-gray-900">{msg.sender}</h3>
                      {msg.isNew && (
                        <span className="px-2 py-0.5 bg-red-500 text-white text-[10px] font-bold rounded-full">
                          New
                        </span>
                      )}
                    </div>
                    <span className="text-xs text-gray-400">{msg.time}</span>
                  </div>
                  <p className="text-sm text-gray-600 line-clamp-1 group-hover:text-gray-900">
                    {msg.text}
                  </p>
                </div>
              ))}
            </div>
          </div>

        </div>
      </div>
    </div>
  );
}

function StatCard({ label, value, icon, bg }) {
  return (
    <div className="bg-white p-6 rounded-2xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow">
      <div className="flex justify-between items-start mb-4">
        <div className={`w-12 h-12 ${bg} rounded-xl flex items-center justify-center`}>
          {icon}
        </div>
      </div>
      <div>
        <div className="text-3xl font-medium text-gray-900 mb-1">{value}</div>
        <div className="text-sm text-gray-500">{label}</div>
      </div>
    </div>
  );
}