"use client";

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import {
  MessageSquare,
  FileText,
  Calendar,
  Edit,
  MapPin,
  Mail,
  X,
  Phone,
} from 'lucide-react';

import { getMyProfile, getMyStats, getAISessions, isLoggedIn, getUser, updateMyProfile } from '../../lib/api';

export default function UserDashboard() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [showEdit, setShowEdit] = useState(false);
  const [saving, setSaving] = useState(false);
  const [errors, setErrors] = useState({});

  const [formData, setFormData] = useState({
    name: "",
    email: "",
    phone_num: "",
    city: "",
  });

  const [profile, setProfile] = useState({
    name: "",
    email: "",
    location: "",
    initials: "",
    phone_num: "",
    city: "",
  });

  const [stats, setStats] = useState({
    documents: 0,
    chats: 0,
    appointments: 0
  });

  const [chatHistory, setChatHistory] = useState([]);

  const buildInitials = (name) =>
    name
      .split(" ")
      .filter(Boolean)
      .map((n) => n[0])
      .join("")
      .substring(0, 2)
      .toUpperCase();

  useEffect(() => {
    if (!isLoggedIn()) {
      router.replace('/login');
      return;
    }

    const u = getUser();
    if (u?.role !== 'client') {
      router.replace('/dashboard/lawyer');
      return;
    }

    const fetchDashboardData = async () => {
      try {
        setLoading(true);

        const [profileData, statsData, sessions] = await Promise.all([
          getMyProfile(),
          getMyStats(),
          getAISessions(),
        ]);

        const name = profileData?.name || u?.name || "";
        const email = profileData?.email || u?.email || "";
        const city = profileData?.city || profileData?.location || "";
        const phone_num = profileData?.phone_num || "";

        setProfile({
          name,
          email,
          location: city,
          city,
          phone_num,
          initials: buildInitials(name),
        });

        setFormData({ name, email, phone_num, city });

        setStats({
          documents: statsData?.documents || 0,
          chats: statsData?.qa_sessions || 0,
          appointments: statsData?.appointments || 0,
        });

        setChatHistory(
          (sessions || []).slice(0, 5).map((s) => ({
            id: s.session_id,
            title: s.title || 'Legal Question',
            time: new Date(s.created_at).toLocaleDateString(),
          }))
        );
      } catch (error) {
        if (error.message.includes("401")) {
          localStorage.clear();
          router.replace('/login');
        }
      } finally {
        setLoading(false);
      }
    };

    fetchDashboardData();
  }, [router]);

  const validate = () => {
    const errs = {};
    if (!formData.name.trim()) errs.name = "Name is required.";
    if (!formData.email.trim()) {
      errs.email = "Email is required.";
    } else if (
          !formData.email.includes("@") ||
          !formData.email.includes(".com") ||
          formData.email.startsWith("@") ||
          formData.email.endsWith("@") ||
          formData.email.indexOf("@") === formData.email.length - 1 ||
          formData.email.split("@")[0].length === 0 ||
          formData.email.split("@")[1].split(".com")[0].length === 0
        ) {
      errs.email = "Enter a valid email address.";
    }
    if (formData.phone_num && formData.phone_num.replace(/\D/g, "").length < 7) {
      errs.phone_num = "Phone number must be at least 7 digits.";
    }
    return errs;
  };

  const handleSave = async () => {
    const errs = validate();
    if (Object.keys(errs).length > 0) {
      setErrors(errs);
      return;
    }
    setErrors({});
    setSaving(true);
    try {
      const updated = await updateMyProfile({
        name: formData.name.trim(),
        email: formData.email.trim(),
        phone_num: formData.phone_num.trim() || null,
        city: formData.city.trim() || null,
      });

      const name = updated.name || formData.name;
      const city = updated.city || formData.city;

      setProfile({
        name,
        email: updated.email || formData.email,
        location: city,
        city,
        phone_num: updated.phone_num || formData.phone_num,
        initials: buildInitials(name),
      });
      setShowEdit(false);
    } catch (err) {
      setErrors({ api: err.message || "Failed to update profile." });
    } finally {
      setSaving(false);
    }
  };

  const handleDiscard = () => {
    setFormData({
      name: profile.name,
      email: profile.email,
      phone_num: profile.phone_num,
      city: profile.city,
    });
    setErrors({});
    setShowEdit(false);
  };

  const handleChange = (field) => (e) => {
    setFormData((prev) => ({ ...prev, [field]: e.target.value }));
    setErrors((prev) => ({ ...prev, [field]: undefined }));
  };

  return (
    <div className="flex min-h-[calc(100vh-80px)] bg-gradient-to-br from-[#f8fafc] to-[#eef2ff]">
      <main className="flex-1 p-6 lg:p-12">
        <div className="bg-white rounded-[2rem] p-8 shadow-sm border border-gray-100 flex flex-col md:flex-row justify-between items-center gap-6 mb-10">
          <div className="flex gap-6 items-center">
            <div className="w-24 h-24 bg-[#052379] text-white flex items-center justify-center rounded-3xl text-3xl font-bold shadow-lg shadow-blue-900/20">
              {profile.initials || "U"}
            </div>

            <div className="space-y-1">
              <h1 className="text-3xl font-black text-gray-900 tracking-tight">{profile.name}</h1>
              <div className="flex flex-wrap gap-4 text-gray-500 text-sm font-medium">
                <span className="flex items-center gap-1.5">
                  <Mail className="w-4 h-4 text-blue-500" />
                  {profile.email}
                </span>
                {(profile.city || profile.location) && (
                  <span className="flex items-center gap-1.5">
                    <MapPin className="w-4 h-4 text-red-500" />
                    {profile.city || profile.location}
                  </span>
                )}
              </div>
            </div>
          </div>

          <button
            onClick={() => {
              setFormData({
                name: profile.name,
                email: profile.email,
                phone_num: profile.phone_num,
                city: profile.city,
              });
              setErrors({});
              setShowEdit(true);
            }}
            className="px-5 py-2.5 bg-[#052379] text-white rounded-xl text-sm font-medium hover:bg-gray-800 transition-all shadow"
          >
            <Edit className="inline w-4 h-4 mr-2" />
            Edit Profile
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
          <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
            <div className="flex items-center gap-3 mb-3">
              <FileText className="w-5 h-5 text-blue-600" />
              <h3 className="text-sm font-semibold text-gray-600">Documents</h3>
            </div>
            <p className="text-3xl font-bold text-gray-900">{stats.documents}</p>
          </div>

          <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
            <div className="flex items-center gap-3 mb-3">
              <MessageSquare className="w-5 h-5 text-indigo-600" />
              <h3 className="text-sm font-semibold text-gray-600">AI Chats</h3>
            </div>
            <p className="text-3xl font-bold text-gray-900">{stats.chats}</p>
          </div>

          <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100">
            <div className="flex items-center gap-3 mb-3">
              <Calendar className="w-5 h-5 text-emerald-600" />
              <h3 className="text-sm font-semibold text-gray-600">Appointments</h3>
            </div>
            <p className="text-3xl font-bold text-gray-900">{stats.appointments}</p>
          </div>
        </div>
      </main>

      {showEdit && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm px-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md p-8 relative">
            <button
              onClick={handleDiscard}
              className="absolute top-5 right-5 text-gray-400 hover:text-gray-700 transition"
            >
              <X className="w-5 h-5" />
            </button>

            <h2 className="text-xl font-bold text-gray-900 mb-1">Profile Settings</h2>
            <p className="text-sm text-gray-500 mb-6">Update your personal information</p>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Full Name</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={handleChange("name")}
                  placeholder="Your full name"
                  className={`w-full px-4 py-2.5 rounded-xl border text-sm focus:outline-none focus:ring-2 focus:ring-[#052379]/30 ${errors.name ? "border-red-400" : "border-gray-200"}`}
                />
                {errors.name && <p className="text-xs text-red-500 mt-1">{errors.name}</p>}
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Email Address</label>
                <input
                  type="email"
                  value={formData.email}
                  onChange={handleChange("email")}
                  placeholder="you@example.com"
                  className={`w-full px-4 py-2.5 rounded-xl border text-sm focus:outline-none focus:ring-2 focus:ring-[#052379]/30 ${errors.email ? "border-red-400" : "border-gray-200"}`}
                />
                {errors.email && <p className="text-xs text-red-500 mt-1">{errors.email}</p>}
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Phone Number</label>
                <div className="relative">
                  <Phone className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                  <input
                    type="tel"
                    value={formData.phone_num}
                    onChange={handleChange("phone_num")}
                    placeholder="+92 300 0000000"
                    className={`w-full pl-9 pr-4 py-2.5 rounded-xl border text-sm focus:outline-none focus:ring-2 focus:ring-[#052379]/30 ${errors.phone_num ? "border-red-400" : "border-gray-200"}`}
                  />
                </div>
                {errors.phone_num && <p className="text-xs text-red-500 mt-1">{errors.phone_num}</p>}
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">City</label>
                <div className="relative">
                  <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                  <input
                    type="text"
                    value={formData.city}
                    onChange={handleChange("city")}
                    placeholder="Your city"
                    className="w-full pl-9 pr-4 py-2.5 rounded-xl border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-[#052379]/30"
                  />
                </div>
              </div>

              {errors.api && (
                <p className="text-sm text-red-500 bg-red-50 rounded-xl px-4 py-2">{errors.api}</p>
              )}
            </div>

            <div className="flex gap-3 mt-7">
              <button
                onClick={handleDiscard}
                className="flex-1 px-4 py-2.5 rounded-xl border border-gray-200 text-sm font-medium text-gray-600 hover:bg-gray-50 transition"
              >
                Discard
              </button>
              <button
                onClick={handleSave}
                disabled={saving}
                className="flex-1 px-4 py-2.5 rounded-xl bg-[#052379] text-white text-sm font-medium hover:bg-blue-900 transition disabled:opacity-60"
              >
                {saving ? "Saving..." : "Save Profile"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
