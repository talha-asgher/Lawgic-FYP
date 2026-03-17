"use client";

import React, { useState, useEffect } from 'react';
import {
  Plus, Briefcase, Clock, CheckCircle, AlertCircle, Loader2,
  ChevronRight, MessageSquare, Users
} from 'lucide-react';
import { getMyCases, getMyRequests, respondToRequest, createCase, getUser, isLoggedIn } from '@/lib/api';

export default function CasesPage() {
  const [cases, setCases] = useState([]);
  const [requests, setRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showNewCase, setShowNewCase] = useState(false);
  const [creating, setCreating] = useState(false);
  const [activeTab, setActiveTab] = useState('cases');
  const [newCase, setNewCase] = useState({ title: '', description: '', law_domain: '', jurisdiction: '' });
  const currentUser = getUser();

  useEffect(() => {
    if (!isLoggedIn()) { window.location.href = '/login'; return; }
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [casesData, reqData] = await Promise.all([
        getMyCases(),
        currentUser?.role === 'lawyer' ? getMyRequests() : Promise.resolve([]),
      ]);
      setCases(casesData);
      setRequests(reqData);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateCase = async (e) => {
    e.preventDefault();
    setCreating(true);
    try {
      await createCase(newCase);
      setShowNewCase(false);
      setNewCase({ title: '', description: '', law_domain: '', jurisdiction: '' });
      loadData();
    } catch (err) {
      alert(err.message || 'Failed to create case');
    } finally {
      setCreating(false);
    }
  };

  const handleRespond = async (requestId, status) => {
    try {
      await respondToRequest(requestId, status);
      loadData();
    } catch (err) {
      alert(err.message || 'Failed to respond');
    }
  };

  const statusConfig = {
    open: { label: 'Open', bg: 'bg-blue-50', text: 'text-blue-700', icon: <Clock className="w-3 h-3" /> },
    in_progress: { label: 'In Progress', bg: 'bg-amber-50', text: 'text-amber-700', icon: <AlertCircle className="w-3 h-3" /> },
    closed: { label: 'Closed', bg: 'bg-gray-100', text: 'text-gray-600', icon: <CheckCircle className="w-3 h-3" /> },
  };

  return (
    <div className="min-h-screen bg-[#F6F8FB] px-4 lg:px-8 py-8">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-semibold text-gray-900">My Cases</h1>
            <p className="text-gray-500 text-sm mt-1">Manage your legal cases</p>
          </div>
          {currentUser?.role === 'client' && (
            <button onClick={() => setShowNewCase(true)}
              className="flex items-center gap-2 px-4 py-2.5 bg-[#052379] text-white text-sm font-medium rounded-xl hover:bg-[#041d5c] transition-colors">
              <Plus className="w-4 h-4" />
              New Case
            </button>
          )}
        </div>

        {currentUser?.role === 'lawyer' && (
          <div className="flex gap-1 mb-6 bg-white rounded-xl border border-gray-200 p-1">
            {['cases', 'requests'].map(tab => (
              <button key={tab} onClick={() => setActiveTab(tab)}
                className={`flex-1 py-2 text-sm font-medium rounded-lg transition-colors capitalize
                  ${activeTab === tab ? 'bg-[#052379] text-white' : 'text-gray-600 hover:text-gray-900'}`}>
                {tab === 'requests' ? `Pending Requests (${requests.length})` : 'My Cases'}
              </button>
            ))}
          </div>
        )}

        {/* New Case Form */}
        {showNewCase && (
          <div className="bg-white rounded-2xl border border-gray-200 p-6 mb-6 shadow-sm">
            <h2 className="text-lg font-medium text-gray-900 mb-4">Create New Case</h2>
            <form onSubmit={handleCreateCase} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="text-sm text-gray-600 mb-1 block">Case Title *</label>
                  <input required type="text" value={newCase.title}
                    onChange={e => setNewCase({ ...newCase, title: e.target.value })}
                    className="w-full p-3 bg-gray-50 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[#052379]/20" />
                </div>
                <div>
                  <label className="text-sm text-gray-600 mb-1 block">Law Domain *</label>
                  <select required value={newCase.law_domain}
                    onChange={e => setNewCase({ ...newCase, law_domain: e.target.value })}
                    className="w-full p-3 bg-gray-50 border border-gray-200 rounded-lg text-sm focus:outline-none">
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
                <label className="text-sm text-gray-600 mb-1 block">Description *</label>
                <textarea required rows="3" value={newCase.description}
                  onChange={e => setNewCase({ ...newCase, description: e.target.value })}
                  className="w-full p-3 bg-gray-50 border border-gray-200 rounded-lg text-sm focus:outline-none resize-none" />
              </div>
              <div>
                <label className="text-sm text-gray-600 mb-1 block">Jurisdiction</label>
                <input type="text" value={newCase.jurisdiction}
                  onChange={e => setNewCase({ ...newCase, jurisdiction: e.target.value })}
                  placeholder="e.g. Lahore High Court"
                  className="w-full p-3 bg-gray-50 border border-gray-200 rounded-lg text-sm focus:outline-none" />
              </div>
              <div className="flex gap-3">
                <button type="submit" disabled={creating}
                  className="flex items-center gap-2 px-6 py-2.5 bg-[#052379] text-white text-sm font-medium rounded-lg hover:bg-[#041d5c] transition-colors disabled:opacity-50">
                  {creating ? <><Loader2 className="w-4 h-4 animate-spin" />Creating...</> : 'Create Case'}
                </button>
                <button type="button" onClick={() => setShowNewCase(false)}
                  className="px-6 py-2.5 border border-gray-200 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-50 transition-colors">
                  Cancel
                </button>
              </div>
            </form>
          </div>
        )}

        {loading ? (
          <div className="flex justify-center py-12"><Loader2 className="w-8 h-8 text-[#052379] animate-spin" /></div>
        ) : activeTab === 'cases' ? (
          <div className="space-y-4">
            {cases.length === 0 ? (
              <div className="bg-white rounded-2xl border border-gray-200 p-12 text-center">
                <Briefcase className="w-12 h-12 text-gray-300 mx-auto mb-3" />
                <p className="text-gray-500">No cases yet.</p>
                {currentUser?.role === 'client' && (
                  <button onClick={() => setShowNewCase(true)} className="mt-4 text-[#052379] hover:underline text-sm">Create your first case</button>
                )}
              </div>
            ) : (
              cases.map(c => {
                const st = statusConfig[c.status] || statusConfig.open;
                return (
                  <div key={c.case_id} className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm hover:shadow-md transition-all">
                    <div className="flex items-start justify-between mb-3">
                      <div>
                        <h3 className="font-semibold text-gray-900">{c.title}</h3>
                        <p className="text-sm text-gray-500 mt-0.5">{c.law_domain}{c.jurisdiction ? ` · ${c.jurisdiction}` : ''}</p>
                      </div>
                      <span className={`flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium ${st.bg} ${st.text}`}>
                        {st.icon}{st.label}
                      </span>
                    </div>
                    <p className="text-sm text-gray-600 mb-4 line-clamp-2">{c.description}</p>
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-gray-400">{new Date(c.created_at).toLocaleDateString()}</span>
                      <div className="flex gap-2">
                        <button onClick={() => { window.location.href = '/find-lawyers'; }}
                          className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-[#052379] border border-[#052379]/20 bg-blue-50 rounded-lg hover:bg-blue-100 transition-colors">
                          <Users className="w-3 h-3" />Find Lawyer
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        ) : (
          <div className="space-y-4">
            {requests.length === 0 ? (
              <div className="bg-white rounded-2xl border border-gray-200 p-12 text-center">
                <p className="text-gray-500">No pending case requests.</p>
              </div>
            ) : (
              requests.map(req => (
                <div key={req.request_id} className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm">
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <h3 className="font-semibold text-gray-900">{req.case_title || `Case #${req.case_id}`}</h3>
                      <p className="text-sm text-gray-500">From: {req.client_name || 'Client'}</p>
                    </div>
                    <span className="px-2.5 py-1 bg-amber-50 text-amber-700 rounded-full text-xs font-medium">Pending</span>
                  </div>
                  <div className="flex gap-3 mt-4">
                    <button onClick={() => handleRespond(req.request_id, 'accepted')}
                      className="flex-1 py-2 bg-emerald-600 text-white text-sm font-medium rounded-lg hover:bg-emerald-700 transition-colors">
                      Accept
                    </button>
                    <button onClick={() => handleRespond(req.request_id, 'rejected')}
                      className="flex-1 py-2 bg-white border border-gray-200 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-50 transition-colors">
                      Decline
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  );
}
