"use client";

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import {
  Users,
  Star,
  Edit,
  X,
  Phone,
  Mail,
  MapPin,
  Briefcase,
  Scale,
  Loader2,
  CheckCircle2,
  User,
  Calendar,
  MessageSquare,
} from 'lucide-react';
import {
  getMyProfile,
  getMyStats,
  getMyLawyerProfile,
  getMyAppointments,
  getMyConversations,
  isLoggedIn,
  getUser,
  updateMyProfile,
  updateLawyerProfile,
} from '../../lib/api';

export default function LawyerDashboard() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showEdit, setShowEdit] = useState(false);
  const [errors, setErrors] = useState({});

  const [profile, setProfile] = useState({
    name: "",
    email: "",
    phone_num: "",
    initials: "",
  });

  const [lawyer, setLawyer] = useState(null);
  const [formData, setFormData] = useState({});
  const [stats, setStats] = useState({
    activeClients: 0,
    appointmentsThisWeek: 0,
    averageRating: 0,
  });
  const [messages, setMessages] = useState([]);

  const buildInitials = (name) =>
    name.split(' ').filter(Boolean).map((n) => n[0]).join('').substring(0, 2).toUpperCase();

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
          phone_num: userProfile.phone_num || "",
          initials: buildInitials(userProfile.name),
        });

        setLawyer(lawyerProfile);

        setStats({
          activeClients: statsData.open_cases || 0,
          appointmentsThisWeek: statsData.appointments || 0,
          averageRating: lawyerProfile?.average_rating || 0,
        });

        setMessages(convs.slice(0, 5).map((c) => {
          const other = c.participants?.find((p) => p.name !== userProfile.name);
          return {
            id: c.conv_id,
            sender: other?.name || 'Client',
            text: c.last_message || 'New conversation',
            time: c.last_message_at ? new Date(c.last_message_at).toLocaleDateString() : '',
            isNew: c.unread_count > 0,
          };
        }));

      } catch (error) {
        console.error(error);
      } finally {
        setLoading(false);
      }
    };

    fetchDashboardData();
  }, [router]);

  const validate = () => {
    const errs = {};
    if (!formData.name?.trim()) errs.name = "Name is required.";
    if (!formData.email?.trim()) {
      errs.email = "Email is required.";
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      errs.email = "Enter a valid email address.";
    }
    if (formData.phone_num && formData.phone_num.replace(/\D/g, "").length < 7) {
      errs.phone_num = "Phone number must be at least 7 digits.";
    }
    if (!formData.specialization?.trim()) errs.specialization = "Specialization is required.";
    return errs;
  };

  const handleSave = async () => {
    const errs = validate();
    if (Object.keys(errs).length > 0) { setErrors(errs); return; }
    setErrors({});
    setSaving(true);
    try {
      const [updatedUser, updatedLawyer] = await Promise.all([
        updateMyProfile({
          name: formData.name.trim(),
          email: formData.email.trim(),
          phone_num: formData.phone_num?.trim() || null,
        }),
        updateLawyerProfile({
          specialization: formData.specialization.trim(),
          bio_data: formData.bio_data?.trim() || null,
          years_of_experience: formData.years_of_experience ? parseInt(formData.years_of_experience) : null,
          office_address: formData.office_address?.trim() || null,
          consultation_fee: formData.consultation_fee ? parseFloat(formData.consultation_fee) : null,
          city: formData.city?.trim() || null,
          languages: formData.languages?.trim() || null,
          bar_council_number: formData.bar_council_number?.trim() || null,
          law_school: formData.law_school?.trim() || null,
          grad_year: formData.grad_year ? parseInt(formData.grad_year) : null,
          degree_type: formData.degree_type?.trim() || null,
        }),
      ]);

      setProfile({
        name: updatedUser.name,
        email: updatedUser.email,
        phone_num: updatedUser.phone_num || "",
        initials: buildInitials(updatedUser.name),
      });
      setLawyer(updatedLawyer);
      setShowEdit(false);
    } catch (err) {
      setErrors({ api: err.message || "Failed to update profile." });
    } finally {
      setSaving(false);
    }
  };

  const handleDiscard = () => {
    setErrors({});
    setShowEdit(false);
  };

  const set = (field) => (val) => {
    setFormData((prev) => ({ ...prev, [field]: val }));
    setErrors((prev) => ({ ...prev, [field]: undefined }));
  };

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-[#F8FAFC]">
        <Loader2 className="w-8 h-8 animate-spin text-[#052379]" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#F8FAFC] p-6 lg:p-12 font-sans">
      <div className="max-w-7xl mx-auto space-y-8">

        <div className="bg-white rounded-[2rem] p-8 shadow-sm border border-gray-100 flex flex-col md:flex-row justify-between items-center gap-6">
          <div className="flex gap-6 items-center">
            <div className="w-24 h-24 bg-[#052379] text-white flex items-center justify-center rounded-3xl text-3xl font-bold shadow-lg shadow-blue-900/20">
              {profile.initials}
            </div>
            <div className="space-y-1">
              <h1 className="text-3xl font-black text-gray-900 tracking-tight">{profile.name}</h1>
              <div className="flex flex-wrap gap-4 text-gray-500 text-sm font-medium">
                <span className="flex items-center gap-1.5"><Mail className="w-4 h-4 text-blue-500" /> {profile.email}</span>
                {lawyer?.city && <span className="flex items-center gap-1.5"><MapPin className="w-4 h-4 text-red-500" /> {lawyer.city}</span>}
              </div>
            </div>
          </div>

          <button
            onClick={() => {
              setFormData({
                name: profile.name,
                email: profile.email,
                phone_num: profile.phone_num,
                specialization: lawyer?.specialization || "",
                bio_data: lawyer?.bio_data || "",
                years_of_experience: lawyer?.years_of_experience ?? "",
                office_address: lawyer?.office_address || "",
                consultation_fee: lawyer?.consultation_fee ?? "",
                city: lawyer?.city || "",
                languages: lawyer?.languages || "",
                bar_council_number: lawyer?.bar_council_number || "",
                law_school: lawyer?.law_school || "",
                grad_year: lawyer?.grad_year ?? "",
                degree_type: lawyer?.degree_type || "",
              });
              setErrors({});
              setShowEdit(true);
            }}
            className="w-full md:w-auto bg-[#052379] text-white px-8 py-3.5 rounded-2xl font-bold shadow-lg shadow-blue-900/20 hover:bg-[#041d5e] transition-all flex items-center justify-center gap-2"
          >
            <Edit className="w-4 h-4" />
            Edit Profile
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <StatCard label="Open Cases" value={stats.activeClients} icon={<Users />} color="blue" />
          <StatCard label="Appts. This Week" value={stats.appointmentsThisWeek} icon={<Calendar />} color="indigo" />
          <StatCard label="Average Rating" value={stats.averageRating} icon={<Star />} color="amber" />
        </div>

        <div className="grid lg:grid-cols-3 gap-8">
          <div className="lg:col-span-2 space-y-8">
            {lawyer && (
              <div className="bg-white p-8 rounded-[2rem] shadow-sm border border-gray-100">
                <h2 className="text-xl font-bold text-gray-900 mb-8 flex items-center gap-2">
                  <Scale className="w-5 h-5 text-[#052379]" /> Professional Credentials
                </h2>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-8">
                  <InfoItem label="Specialization" value={lawyer.specialization} />
                  <InfoItem label="Experience" value={lawyer.years_of_experience ? `${lawyer.years_of_experience} Years` : null} />
                  <InfoItem label="Consultation Fee" value={lawyer.consultation_fee ? `Rs ${lawyer.consultation_fee}` : null} />
                  <InfoItem label="Bar Council #" value={lawyer.bar_council_number} />
                  <InfoItem label="Verified Status" value={lawyer.verification_status} isStatus />
                  <InfoItem label="Languages" value={lawyer.languages} />
                </div>
                <div className="mt-10 pt-8 border-t border-gray-50">
                  <p className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-3">Professional Bio</p>
                  <p className="text-gray-800 leading-relaxed">"{lawyer.bio_data || 'No bio available'}"</p>
                </div>
              </div>
            )}
          </div>

          <div className="bg-white p-8 rounded-[2rem] shadow-sm border border-gray-100 h-fit">
            <h2 className="text-xl font-bold text-gray-900 mb-6 flex items-center gap-2">
              <MessageSquare className="w-5 h-5 text-indigo-500" /> Recent Messages
            </h2>
            <div className="space-y-4">
              {messages.length > 0 ? messages.map((m) => (
                <div key={m.id} className="p-4 bg-gray-50 rounded-2xl hover:bg-blue-50 transition-all cursor-pointer group"
                  onClick={() => router.push('/chat/' + m.id)}>
                  <div className="flex justify-between items-start mb-1">
                    <span className="font-bold text-gray-900 group-hover:text-blue-700">{m.sender}</span>
                    <span className="text-[10px] font-bold text-gray-400 uppercase">{m.time}</span>
                  </div>
                  <p className="text-sm text-gray-500 truncate">{m.text}</p>
                </div>
              )) : (
                <p className="text-center py-10 text-gray-400 text-sm italic">No recent messages</p>
              )}
            </div>
          </div>
        </div>

        {showEdit && (
          <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-2xl w-full max-w-3xl max-h-[90vh] shadow-2xl overflow-hidden flex flex-col">

              <div className="px-8 py-6 border-b border-gray-100 flex justify-between items-center">
                <div>
                  <h2 className="text-xl font-bold text-gray-900">Profile Settings</h2>
                  <p className="text-sm text-gray-500 mt-0.5">Manage your professional identity on Lawgic</p>
                </div>
                <button onClick={handleDiscard} className="text-gray-400 hover:text-gray-700 transition">
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="flex-1 overflow-y-auto p-8 space-y-8">

                <section>
                  <h3 className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-5 pb-2 border-b border-gray-100">Identity & Contact</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                    <FormInput label="Full Name" value={formData.name} onChange={set("name")} icon={<User size={16} />} error={errors.name} />
                    <FormInput label="Email Address" value={formData.email} onChange={set("email")} icon={<Mail size={16} />} error={errors.email} />
                    <FormInput label="Phone Number" value={formData.phone_num} onChange={set("phone_num")} icon={<Phone size={16} />} error={errors.phone_num} />
                    <FormInput label="City" value={formData.city} onChange={set("city")} icon={<MapPin size={16} />} />
                  </div>
                </section>

                <section>
                  <h3 className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-5 pb-2 border-b border-gray-100">Professional Credentials</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                    <FormInput label="Specialization" value={formData.specialization} onChange={set("specialization")} icon={<Scale size={16} />} error={errors.specialization} />
                    <FormInput label="Experience (Years)" value={formData.years_of_experience} onChange={set("years_of_experience")} icon={<Briefcase size={16} />} />
                    <FormInput label="Consultation Fee (Rs)" value={formData.consultation_fee} onChange={set("consultation_fee")} />
                    <FormInput label="Bar Council #" value={formData.bar_council_number} onChange={set("bar_council_number")} />
                    <div className="md:col-span-2">
                      <FormInput label="Office Address" value={formData.office_address} onChange={set("office_address")} />
                    </div>
                    <FormInput label="Languages" value={formData.languages} onChange={set("languages")} />
                    <FormInput label="Law School" value={formData.law_school} onChange={set("law_school")} icon={<Scale size={16} />} />
                    <FormInput label="Graduation Year" value={formData.grad_year} onChange={set("grad_year")} />
                    <FormInput label="Degree Type" value={formData.degree_type} onChange={set("degree_type")} />
                  </div>
                </section>

                <section>
                  <h3 className="text-xs font-bold text-gray-400 uppercase tracking-widest mb-5 pb-2 border-b border-gray-100">About You</h3>
                  <div className="space-y-1.5">
                    <label className="block text-sm font-medium text-gray-700">Public Bio</label>
                    <textarea
                      className="w-full border border-gray-200 rounded-xl px-4 py-3 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-[#052379]/30 focus:border-[#052379] min-h-[120px] resize-none transition"
                      placeholder="Tell clients about your expertise..."
                      value={formData.bio_data || ""}
                      onChange={(e) => set("bio_data")(e.target.value)}
                    />
                  </div>
                </section>

                {errors.api && (
                  <p className="text-sm text-red-500 bg-red-50 rounded-xl px-4 py-2">{errors.api}</p>
                )}
              </div>

              <div className="px-8 py-6 border-t border-gray-100 flex gap-3">
                <button
                  onClick={handleDiscard}
                  className="flex-1 py-2.5 rounded-xl border border-gray-200 text-sm font-medium text-gray-600 hover:bg-gray-50 transition"
                >
                  Discard
                </button>
                <button
                  disabled={saving}
                  onClick={handleSave}
                  className="flex-[2] py-2.5 rounded-xl bg-[#052379] text-white text-sm font-medium hover:bg-blue-900 transition disabled:opacity-60 flex items-center justify-center gap-2"
                >
                  {saving ? <><Loader2 className="animate-spin w-4 h-4" /> Saving...</> : "Save Profile"}
                </button>
              </div>

            </div>
          </div>
        )}

      </div>
    </div>
  );
}

function InfoItem({ label, value, isStatus }) {
  return (
    <div className="group">
      <p className="text-[10px] font-black text-gray-400 uppercase tracking-widest mb-1 group-hover:text-blue-500 transition-colors">{label}</p>
      {isStatus ? (
        <span className="inline-flex items-center gap-1 text-sm font-bold text-emerald-600 bg-emerald-50 px-2.5 py-0.5 rounded-full border border-emerald-100">
          <CheckCircle2 className="w-3 h-3" /> {value || 'Pending'}
        </span>
      ) : (
        <p className="font-bold text-gray-800 tracking-tight">{value || 'Not Listed'}</p>
      )}
    </div>
  );
}

function StatCard({ label, value, icon, color }) {
  const colors = {
    blue: "bg-blue-50 text-blue-600",
    indigo: "bg-indigo-50 text-indigo-600",
    amber: "bg-amber-50 text-amber-600",
  };
  return (
    <div className="bg-white p-8 rounded-[2rem] border border-gray-100 shadow-sm flex items-center gap-6 group hover:shadow-xl transition-all duration-500">
      <div className={`w-16 h-16 rounded-2xl flex items-center justify-center transition-transform group-hover:scale-110 duration-300 ${colors[color]}`}>
        {React.cloneElement(icon, { size: 28 })}
      </div>
      <div>
        <p className="text-[10px] font-black text-gray-400 uppercase tracking-[0.15em] mb-1">{label}</p>
        <h2 className="text-3xl font-black text-gray-900 tracking-tight">{value}</h2>
      </div>
    </div>
  );
}

function FormInput({ label, value, onChange, icon, error }) {
  return (
    <div className="space-y-1.5">
      <label className="block text-sm font-medium text-gray-700">{label}</label>
      <div className="relative">
        {icon && (
          <div className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">
            {icon}
          </div>
        )}
        <input
          className={`w-full border rounded-xl py-2.5 text-sm text-gray-700 focus:outline-none focus:ring-2 focus:ring-[#052379]/30 focus:border-[#052379] transition ${icon ? 'pl-9 pr-4' : 'px-4'} ${error ? 'border-red-400' : 'border-gray-200'}`}
          value={value ?? ""}
          onChange={(e) => onChange(e.target.value)}
        />
      </div>
      {error && <p className="text-xs text-red-500">{error}</p>}
    </div>
  );
}
