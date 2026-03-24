"use client";

import React, { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import {
  Star, MapPin, Briefcase, Shield, ChevronLeft,
  Clock, Award, Loader2, AlertCircle, DollarSign, Plus, X, CheckCircle
} from 'lucide-react';
import {
  getLawyerById, getLawyerReviews, getMyCases, createCase,
  inviteLawyerToCase, getClientRequests, getUser, isLoggedIn
} from '@/lib/api';

export default function LawyerDetailsPage() {
  const { id } = useParams();
  const router = useRouter();
  const [lawyer, setLawyer] = useState(null);
  const [reviews, setReviews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [activeTab, setActiveTab] = useState('about');

  const [showRequestModal, setShowRequestModal] = useState(false);
  const [cases, setCases] = useState([]);
  const [casesLoading, setCasesLoading] = useState(false);
  const [existingRequests, setExistingRequests] = useState([]);
  const [selectedCaseId, setSelectedCaseId] = useState('');
  const [showNewCase, setShowNewCase] = useState(false);
  const [newCase, setNewCase] = useState({ title: '', description: '', law_domain: '', jurisdiction: '' });
  const [submitting, setSubmitting] = useState(false);
  const [requestResult, setRequestResult] = useState(null);

  const currentUser = getUser();

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

  const handleOpenRequestModal = async () => {
    if (!isLoggedIn()) { router.push('/login'); return; }
    if (currentUser?.role === 'lawyer') return;

    setShowRequestModal(true);
    setRequestResult(null);
    setCasesLoading(true);
    try {
      const [casesData, requestsData] = await Promise.all([
        getMyCases(),
        getClientRequests().catch(() => []),
      ]);
      setCases(casesData.filter(c => c.status !== 'closed'));
      setExistingRequests(requestsData);
    } catch {
      setCases([]);
      setExistingRequests([]);
    } finally {
      setCasesLoading(false);
    }
  };

  const lawyerIdNum = parseInt(id);

  const existingRequestForLawyer = existingRequests.find(
    r => r.lawyer_id === lawyerIdNum && (r.status === 'pending' || r.status === 'accepted')
  );

  const handleSubmitRequest = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      let caseId = selectedCaseId;
      if (showNewCase) {
        const created = await createCase({ ...newCase, lawyer_ids: [lawyerIdNum] });
        caseId = created.case_id;
      } else {
        await inviteLawyerToCase(parseInt(caseId), lawyerIdNum);
      }
      setRequestResult({ success: true, message: 'Case request submitted successfully. The lawyer will be notified.' });
    } catch (err) {
      setRequestResult({ success: false, message: err.message || 'Failed to submit request' });
    } finally {
      setSubmitting(false);
    }
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
        <button onClick={() => router.push('/find-lawyers')}
          className="flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-6 text-sm">
          <ChevronLeft className="w-4 h-4" />
          Back to Lawyers
        </button>

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

          <div className="mt-6 pt-6 border-t border-gray-100">
            {!isLoggedIn() ? (
              <button onClick={() => router.push('/login')}
                className="flex items-center justify-center gap-2 w-full sm:w-auto px-8 py-3 bg-[#052379] text-white text-sm font-medium rounded-xl hover:bg-[#041d5c] transition-colors">
                Login to Submit Case Request
              </button>
            ) : currentUser?.role === 'lawyer' ? (
              <p className="text-sm text-gray-500 italic">Lawyer-to-lawyer contact is not available through this platform.</p>
            ) : (
              <button onClick={handleOpenRequestModal}
                className="flex items-center justify-center gap-2 w-full sm:w-auto px-8 py-3 bg-[#052379] text-white text-sm font-medium rounded-xl hover:bg-[#041d5c] transition-colors">
                <Plus className="w-4 h-4" />
                Submit Case Request
              </button>
            )}
          </div>
        </div>

        <div className="flex gap-1 mb-6 bg-white rounded-xl border border-gray-200 p-1">
          {['about', 'reviews'].map(tab => (
            <button key={tab} onClick={() => setActiveTab(tab)}
              className={`flex-1 py-2 text-sm font-medium rounded-lg transition-colors capitalize
                ${activeTab === tab ? 'bg-[#052379] text-white' : 'text-gray-600 hover:text-gray-900'}`}>
              {tab === 'reviews' ? `Reviews (${lawyer.review_count || 0})` : tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </div>

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

      {showRequestModal && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between p-6 border-b border-gray-100">
              <h2 className="text-lg font-semibold text-gray-900">Submit Case Request</h2>
              <button onClick={() => { setShowRequestModal(false); setRequestResult(null); setShowNewCase(false); setSelectedCaseId(''); }}
                className="text-gray-400 hover:text-gray-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6">
              {requestResult ? (
                <div className={`flex flex-col items-center text-center py-4 gap-4`}>
                  {requestResult.success ? (
                    <CheckCircle className="w-12 h-12 text-emerald-500" />
                  ) : (
                    <AlertCircle className="w-12 h-12 text-red-400" />
                  )}
                  <p className={`text-sm font-medium ${requestResult.success ? 'text-emerald-700' : 'text-red-700'}`}>
                    {requestResult.message}
                  </p>
                  {requestResult.success ? (
                    <button onClick={() => { setShowRequestModal(false); router.push('/cases'); }}
                      className="px-6 py-2.5 bg-[#052379] text-white text-sm font-medium rounded-xl hover:bg-[#041d5c] transition-colors">
                      View My Cases
                    </button>
                  ) : (
                    <button onClick={() => setRequestResult(null)}
                      className="px-6 py-2.5 border border-gray-200 text-gray-700 text-sm font-medium rounded-xl hover:bg-gray-50 transition-colors">
                      Try Again
                    </button>
                  )}
                </div>
              ) : existingRequestForLawyer ? (
                <div className="flex flex-col items-center text-center py-4 gap-3">
                  <Clock className="w-10 h-10 text-amber-500" />
                  <p className="text-sm font-medium text-gray-900">
                    {existingRequestForLawyer.status === 'accepted'
                      ? 'You already have an ongoing case with this lawyer.'
                      : 'You already have a pending case request with this lawyer.'}
                  </p>
                  <button onClick={() => { setShowRequestModal(false); router.push('/cases'); }}
                    className="px-6 py-2.5 bg-[#052379] text-white text-sm font-medium rounded-xl hover:bg-[#041d5c] transition-colors">
                    View My Cases
                  </button>
                </div>
              ) : casesLoading ? (
                <div className="flex justify-center py-8">
                  <Loader2 className="w-8 h-8 text-[#052379] animate-spin" />
                </div>
              ) : (
                <form onSubmit={handleSubmitRequest} className="space-y-4">
                  <div className="flex gap-2 mb-2">
                    <button type="button"
                      onClick={() => { setShowNewCase(false); setSelectedCaseId(''); }}
                      className={`flex-1 py-2 text-sm font-medium rounded-lg border transition-colors ${!showNewCase ? 'bg-[#052379] text-white border-[#052379]' : 'bg-white text-gray-700 border-gray-200 hover:bg-gray-50'}`}>
                      Select Existing Case
                    </button>
                    <button type="button"
                      onClick={() => { setShowNewCase(true); setSelectedCaseId(''); }}
                      className={`flex-1 py-2 text-sm font-medium rounded-lg border transition-colors ${showNewCase ? 'bg-[#052379] text-white border-[#052379]' : 'bg-white text-gray-700 border-gray-200 hover:bg-gray-50'}`}>
                      Create New Case
                    </button>
                  </div>

                  {!showNewCase ? (
                    <>
                      {cases.length === 0 ? (
                        <div className="bg-gray-50 rounded-xl p-4 text-center">
                          <p className="text-sm text-gray-500 mb-3">You have no open cases.</p>
                          <button type="button" onClick={() => setShowNewCase(true)}
                            className="text-[#052379] text-sm hover:underline">
                            Create a new case to submit this request
                          </button>
                        </div>
                      ) : (
                        <div className="space-y-2 max-h-48 overflow-y-auto">
                          {cases.map(c => (
                            <label key={c.case_id}
                              className={`flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition-colors ${selectedCaseId === String(c.case_id) ? 'border-[#052379] bg-blue-50' : 'border-gray-200 hover:bg-gray-50'}`}>
                              <input type="radio" name="case" value={c.case_id}
                                checked={selectedCaseId === String(c.case_id)}
                                onChange={e => setSelectedCaseId(e.target.value)}
                                className="mt-0.5 accent-[#052379]" />
                              <div>
                                <p className="text-sm font-medium text-gray-900">{c.title}</p>
                                <p className="text-xs text-gray-500">{c.law_domain}{c.jurisdiction ? ` · ${c.jurisdiction}` : ''}</p>
                              </div>
                            </label>
                          ))}
                        </div>
                      )}
                    </>
                  ) : (
                    <div className="space-y-3">
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        <div>
                          <label className="text-xs text-gray-600 mb-1 block">Case Title *</label>
                          <input required type="text" value={newCase.title}
                            onChange={e => setNewCase({ ...newCase, title: e.target.value })}
                            className="w-full p-2.5 bg-gray-50 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#052379]/20" />
                        </div>
                        <div>
                          <label className="text-xs text-gray-600 mb-1 block">Law Domain *</label>
                          <select required value={newCase.law_domain}
                            onChange={e => setNewCase({ ...newCase, law_domain: e.target.value })}
                            className="w-full p-2.5 bg-gray-50 border border-gray-200 rounded-lg text-sm focus:outline-none">
                            <option value="">Select domain</option>
                            <option value="Criminal Law">Criminal Law</option>
                            <option value="Family Law">Family Law</option>
                            <option value="Property Law">Property Law</option>
                            <option value="Corporate Law">Corporate Law</option>
                            <option value="Civil Law">Civil Law</option>
                            <option value="Other">Other</option>
                          </select>
                        </div>
                      </div>
                      <div>
                        <label className="text-xs text-gray-600 mb-1 block">Description *</label>
                        <textarea required rows="3" value={newCase.description}
                          onChange={e => setNewCase({ ...newCase, description: e.target.value })}
                          className="w-full p-2.5 bg-gray-50 border border-gray-200 rounded-lg text-sm focus:outline-none resize-none" />
                      </div>
                      <div>
                        <label className="text-xs text-gray-600 mb-1 block">Jurisdiction</label>
                        <input type="text" value={newCase.jurisdiction}
                          onChange={e => setNewCase({ ...newCase, jurisdiction: e.target.value })}
                          placeholder="e.g. Lahore High Court"
                          className="w-full p-2.5 bg-gray-50 border border-gray-200 rounded-lg text-sm focus:outline-none" />
                      </div>
                    </div>
                  )}

                  <div className="flex gap-3 pt-2">
                    <button type="submit"
                      disabled={submitting || (!showNewCase && !selectedCaseId)}
                      className="flex-1 py-2.5 bg-[#052379] text-white text-sm font-medium rounded-xl hover:bg-[#041d5c] transition-colors disabled:opacity-50 flex items-center justify-center gap-2">
                      {submitting ? <><Loader2 className="w-4 h-4 animate-spin" />Submitting...</> : 'Submit Request'}
                    </button>
                    <button type="button"
                      onClick={() => { setShowRequestModal(false); setShowNewCase(false); setSelectedCaseId(''); }}
                      className="px-4 py-2.5 border border-gray-200 text-gray-700 text-sm font-medium rounded-xl hover:bg-gray-50 transition-colors">
                      Cancel
                    </button>
                  </div>
                </form>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
