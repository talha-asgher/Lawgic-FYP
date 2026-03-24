"use client";

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
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
import { getMyProfile, getMyStats, getMyLawyerProfile, getMyAppointments, getMyConversations, isLoggedIn, getUser } from '@/lib/api';

export default function LawyerDashboard() {
  const router = useRouter();
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
    if (!isLoggedIn()) { router.replace('/login'); return; }
    const u = getUser();
    if (u?.role !== 'lawyer') { router.replace('/dashboard/user'); return; }

    const fetchDashboardData = async () => {
      try {
        setLoading(true);
        const [userProfile, lawyerProfile, statsData, appts, convs] = await Promise.all([
          getMyProfile(),
          getMyLawyerProfile().catch(() => null),
          getMyStats().catch(() => ({})),
          getMyAppointments({ upcoming_only: true }).catch(() => []),
          getMyConversations().catch(() => []),
        ]);
        setProfile({
          name: userProfile.name,
          email: userProfile.email,
          barId: lawyerProfile?.bar_council_number || 'N/A',
          rating: lawyerProfile?.average_rating || 0,
          initials: userProfile.name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase(),
        });
        setStats({
          activeClients: statsData.open_cases || 0,
          appointmentsThisWeek: statsData.appointments || 0,
          earnings: '—',
          averageRating: lawyerProfile?.average_rating || 0,
        });
        setAppointments(appts.slice(0, 5).map(a => ({
          id: a.appt_id,
          clientName: a.client_name || 'Client',
          date: new Date(a.scheduled_at).toLocaleDateString(),
          time: new Date(a.scheduled_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          status: a.status === 'accepted' ? 'Confirmed' : a.status.charAt(0).toUpperCase() + a.status.slice(1),
          type: a.status === 'accepted' ? 'confirmed' : 'pending',
        })));
        setMessages(convs.slice(0, 5).map(c => {
          const other = c.participants?.find(p => p.name !== userProfile.name);
          return {
            id: c.conv_id,
            sender: other?.name || 'Client',
            text: c.last_message || 'New conversation',
            time: c.last_message_at ? new Date(c.last_message_at).toLocaleDateString() : '',
            isNew: c.unread_count > 0,
          };
        }));
      } catch (error) {
        console.error('Failed to load dashboard:', error);
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
                <div key={msg.id} onClick={() => router.push('/chat/' + msg.id)} className="p-4 bg-[#F6F8FB] rounded-xl hover:bg-gray-50 transition-colors cursor-pointer group">
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