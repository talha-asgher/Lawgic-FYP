"use client";

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
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
import { getMyProfile, getMyStats, getAISessions, isLoggedIn, getUser } from '@/lib/api';
import { useLanguage } from '@/app/lib/LanguageContext';

export default function UserDashboard() {
  const router = useRouter();
  const { t } = useLanguage();
  const [loading, setLoading] = useState(true);

  const [user, setUser] = useState({
    name: "",
    email: "",
    location: "",
    initials: ""
  });

  const [stats, setStats] = useState({
    documents: 0,
    chats: 0,
    appointments: 0
  });

  const [activities, setActivities] = useState([]);
  const [chatHistory, setChatHistory] = useState([]);

  useEffect(() => {
    if (!isLoggedIn()) { router.replace('/login'); return; }
    const u = getUser();
    if (u?.role !== 'client') { router.replace('/dashboard/lawyer'); return; }

    const fetchDashboardData = async () => {
      try {
        setLoading(true);
        const [profile, statsData, sessions] = await Promise.all([
          getMyProfile(),
          getMyStats().catch(() => ({})),
          getAISessions().catch(() => []),
        ]);
        setUser({
          name: profile.name,
          email: profile.email,
          location: 'Pakistan',
          initials: profile.name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase(),
        });
        setStats({
          documents: statsData.documents || 0,
          chats: statsData.qa_sessions || 0,
          appointments: statsData.appointments || 0,
        });
        setChatHistory(sessions.slice(0, 5).map(s => ({
          id: s.session_id,
          title: s.title || 'Legal Question',
          time: new Date(s.created_at).toLocaleDateString(),
        })));
      } catch (error) {
        console.error('Failed to fetch dashboard data:', error);
      } finally {
        setLoading(false);
      }
    };
    fetchDashboardData();
  }, []);

  return (
    <div className="flex min-h-[calc(100vh-80px)] bg-[#F6F8FB]">

      <main className="flex-1 p-6 lg:p-12 overflow-y-auto">

        <div className="bg-white rounded-2xl border border-gray-200 p-6 mb-8 flex flex-col md:flex-row items-start md:items-center gap-6 shadow-sm">

          <div className="w-24 h-24 bg-gray-100 rounded-full flex items-center justify-center flex-shrink-0">
            <span className="text-3xl font-medium text-gray-600">{user.initials}</span>
          </div>

          <div className="flex-1 space-y-1">
            <h1 className="text-2xl font-semibold text-gray-900">{user.name}</h1>
            <p className="text-gray-500">{user.email}</p>
            <p className="text-gray-500 flex items-center gap-1">
              <span className="w-2 h-2 bg-green-500 rounded-full inline-block" />
              {user.location}
            </p>
          </div>

          <button className="flex items-center gap-2 px-4 py-2 border border-gray-200 rounded-lg text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors">
            <Edit className="w-4 h-4" />
            {t("dashboardUser.editProfile")}
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">

          <div className="bg-white p-6 rounded-2xl border border-gray-200 hover:shadow-md transition-shadow">
            <div className="flex items-center gap-4 mb-4">
              <div className="w-12 h-12 bg-blue-50 rounded-xl flex items-center justify-center">
                <FileText className="w-6 h-6 text-blue-600" />
              </div>
              <span className="text-sm font-medium text-gray-500">{t("dashboardUser.myDocuments")}</span>
            </div>
            <div className="text-4xl font-bold text-gray-900">{stats.documents}</div>
          </div>

          <div className="bg-white p-6 rounded-2xl border border-gray-200 hover:shadow-md transition-shadow">
            <div className="flex items-center gap-4 mb-4">
              <div className="w-12 h-12 bg-purple-50 rounded-xl flex items-center justify-center">
                <MessageSquare className="w-6 h-6 text-purple-600" />
              </div>
              <span className="text-sm font-medium text-gray-500">{t("dashboardUser.myChats")}</span>
            </div>
            <div className="text-4xl font-bold text-gray-900">{stats.chats}</div>
          </div>

          <div className="bg-white p-6 rounded-2xl border border-gray-200 hover:shadow-md transition-shadow">
            <div className="flex items-center gap-4 mb-4">
              <div className="w-12 h-12 bg-amber-50 rounded-xl flex items-center justify-center">
                <Calendar className="w-6 h-6 text-amber-600" />
              </div>
              <span className="text-sm font-medium text-gray-500">{t("dashboardUser.appointments")}</span>
            </div>
            <div className="text-4xl font-bold text-gray-900">{stats.appointments}</div>
          </div>
        </div>
      </main>
    </div>
  );
}
