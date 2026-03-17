"use client";

import React, { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import {
  Star, MapPin, Briefcase, Phone, Mail, Shield, ChevronLeft,
  Calendar, MessageSquare, Clock, Award, Loader2, AlertCircle, DollarSign
} from 'lucide-react';
import { getLawyerById, getLawyerReviews, getOrCreateConversation, createAppointment, getUser, isLoggedIn } from '@/lib/api';

export default function LawyerDetailsPage() {
  const { id } = useParams();
  const [lawyer, setLawyer] = useState(null);
  const [reviews, setReviews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionLoading, setActionLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('about');

  useEffect(() => {
    if (!id) return;
    const load = async () => {
      try {
        const [lawyerData, reviewData] = await Promise.all([
          getLawyerById(id),
          getLawyerReviews(id).catch(() => []),
        ]);
        setLawyer(lawyerData);
        setReviews(reviewData);
      } catch (err) {
        setError(err.message || 'Failed to load lawyer profile');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [id]);

  const handleChat = async () => {
    if (!isLoggedIn()) { window.location.href = '/login'; return; }
    setActionLoading(true);
    try {
      const conv = await getOrCreateConversation(parseInt(id), null, null);
      window.location.href = '/chat/' + conv.conv_id;
    } catch (err) {
      alert(err.message || 'Could not start conversation');
    } finally {
      setActionLoading(false); }
  };

  const handleBookAppointment = () => {
    if (!isLoggedIn()) { window.location.href = '/login'; return; }
    window.location.href = '/appointments/new?lawyer=' + id;
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#F6F8FB]">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="w-10 h-10 text-[#052379] animate-spin" />
          <p className="text-gray-500">Loading profile...</p>
        </div>
      </div>
    );
  }

  if (error || !lawyer) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#F6F8FB]">
        <div className="text-center">
          <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-3" />
          <p className="text-gray-700">{error || 'Lawyer not found'}</p>
          <button onClick={() => window.history.back()} className="mt-4 text-[#052379] hover:underline text-sm">Go back</button>
        </div>
      </div>
    );
  }

  const initials = lawyer.name.split(' ').map(n => n[0]).join('').substring(0, 2).toUpperCase();

  return (
    <div className="min-h-screen bg-[#F6F8FB]">
      <div className="max-w-5xl mx-auto px-4 lg:px-8 py-8">
        {/* Back */}
        <button onClick={() => window.location.href = '/find-lawyers'}
          className="flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-6 text-sm">
          <ChevronLeft className="w-4 h-4" />
          Back to Lawyers
        </button>

        {/* Profile Header */}
        <div className="bg-white rounded-2xl border border-gray-200 p-6 mb-6 shadow-sm">
          <div className="flex flex-col md:flex-row gap-6">
            <div className="w-24 h-24 bg-[#052379] rounded-2xl flex items-center justify-center flex-shrink-0 text-white text-3xl font-medium">
              {initials}
            </div>
            <div className="flex-1">
              <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
                <div>
                  <div className="flex items-center gap-3 flex-wrap mb-1">
                    <h1 className="text-2xl font-semibold text-gray-900">{lawyer.name}</h1>
                    {lawyer.verification_status === 'verified' && (
                      <span className="flex items-center gap-1 px-2 py-0.5 bg-emerald-100 text-emerald-700 text-xs font-medium rounded-full">
                        <Shield className="w-3 h-3" /> Verified
                      </span>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-2 mb-3">
                    {(lawyer.specializations || [lawyer.specialization]).map((s, i) => (
                      <span key={i} className="px-3 py-1 bg-blue-50 text-[#052379] text-xs font-medium rounded-full">{s}</span>
                    ))}
                  </div>
                  <div className="flex flex-wrap gap-4 text-sm text-gray-500">
                    {lawyer.city && <span className="flex items-center gap-1"><MapPin className="w-4 h-4" />{lawyer.city}</span>}
                    {lawyer.years_of_experience && <span className="flex items-center gap-1"><Briefcase className="w-4 h-4" />{lawyer.years_of_experience} years</span>}
                    {lawyer.bar_council_number && <span className="flex items-center gap-1"><Award className="w-4 h-4" />Bar ID: {lawyer.bar_council_number}</span>}
                  </div>
                </div>
                <div className="flex flex-col items-start md:items-end gap-3">
                  {lawyer.average_rating > 0 && (
                    <div className="flex items-center gap-1 bg-amber-50 px-3 py-1.5 rounded-lg border border-amber-100">
                      <Star className="w-4 h-4 text-amber-500 fill-amber-500" />
                      <span className="text-sm font-bold text-amber-700">{lawyer.average_rating?.toFixed(1)}</span>
                      <span className="text-xs text-amber-600">({lawyer.review_count} reviews)</span>
                    </div>
                  )}
                  {lawyer.consultation_fee && (
                    <div className="flex items-center gap-1 text-gray-700 text-sm font-medium">
                      <DollarSign className="w-4 h-4 text-gray-400" />
                      PKR {lawyer.consultation_fee.toLocaleString()} / consultation
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* CTA Buttons */}
          <div className="flex flex-col sm:flex-row gap-3 mt-6 pt-6 border-t border-gray-100">
            <button onClick={handleChat} disabled={actionLoading}
              className="flex items-center justify-center gap-2 flex-1 px-6 py-3 bg-[#052379] text-white text-sm font-medium rounded-xl hover:bg-[#041d5c] transition-colors disabled:opacity-50">
              {actionLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <MessageSquare className="w-4 h-4" />}
              Message Lawyer
            </button>
            <button onClick={handleBookAppointment}
              className="flex items-center justify-center gap-2 flex-1 px-6 py-3 bg-white border border-gray-200 text-gray-900 text-sm font-medium rounded-xl hover:bg-gray-50 transition-colors">
              <Calendar className="w-4 h-4" />
              Book Appointment
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 mb-6 bg-white rounded-xl border border-gray-200 p-1">
          {['about', 'reviews'].map(tab => (
            <button key={tab} onClick={() => setActiveTab(tab)}
              className={`flex-1 py-2 text-sm font-medium rounded-lg transition-colors capitalize
                ${activeTab === tab ? 'bg-[#052379] text-white' : 'text-gray-600 hover:text-gray-900'}`}>
              {tab === 'reviews' ? `Reviews (${lawyer.review_count || 0})` : tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        {activeTab === 'about' && (
          <div className="space-y-6">
            {lawyer.bio_data && (
              <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm">
                <h2 className="text-lg font-medium text-gray-900 mb-3">About</h2>
                <p className="text-gray-600 leading-relaxed">{lawyer.bio_data}</p>
              </div>
            )}
            <div className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm">
              <h2 className="text-lg font-medium text-gray-900 mb-4">Professional Details</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {lawyer.law_school && (
                  <div className="flex flex-col gap-1">
                    <span className="text-xs text-gray-400 uppercase tracking-wide">Education</span>
                    <span className="text-sm font-medium text-gray-900">{lawyer.law_school}{lawyer.degree_type ? ` — ${lawyer.degree_type}` : ''}{lawyer.grad_year ? ` (${lawyer.grad_year})` : ''}</span>
                  </div>
                )}
                {lawyer.languages && (
                  <div className="flex flex-col gap-1">
                    <span className="text-xs text-gray-400 uppercase tracking-wide">Languages</span>
                    <span className="text-sm font-medium text-gray-900">{lawyer.languages.replace(/,/g, ', ')}</span>
                  </div>
                )}
                {lawyer.office_address && (
                  <div className="flex flex-col gap-1">
                    <span className="text-xs text-gray-400 uppercase tracking-wide">Office</span>
                    <span className="text-sm font-medium text-gray-900">{lawyer.office_address}</span>
                  </div>
                )}
                {lawyer.email && (
                  <div className="flex flex-col gap-1">
                    <span className="text-xs text-gray-400 uppercase tracking-wide">Contact</span>
                    <span className="text-sm font-medium text-gray-900">{lawyer.email}</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'reviews' && (
          <div className="space-y-4">
            {reviews.length === 0 ? (
              <div className="bg-white rounded-2xl border border-gray-200 p-8 text-center">
                <p className="text-gray-500">No reviews yet.</p>
              </div>
            ) : (
              reviews.map((r) => (
                <div key={r.rating_id} className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm">
                  <div className="flex items-start justify-between mb-3">
                    <div>
                      <p className="font-medium text-gray-900 text-sm">{r.reviewer_name || 'Client'}</p>
                      <p className="text-xs text-gray-400">{new Date(r.created_at).toLocaleDateString()}</p>
                    </div>
                    <div className="flex items-center gap-0.5">
                      {[1,2,3,4,5].map(s => (
                        <Star key={s} className={`w-4 h-4 ${s <= r.stars ? 'text-amber-500 fill-amber-500' : 'text-gray-200 fill-gray-200'}`} />
                      ))}
                    </div>
                  </div>
                  {r.comment && <p className="text-gray-600 text-sm">{r.comment}</p>}
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  );
}
