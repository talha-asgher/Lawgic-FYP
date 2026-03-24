"use client";

import { useState, useEffect } from 'react';
import {
  Plus, Briefcase, Clock, CheckCircle, AlertCircle, Loader2,
  MessageSquare, Calendar, ChevronDown, ChevronUp, XCircle
} from 'lucide-react';
import { useRouter } from 'next/navigation';
import {
  getMyCases, getMyRequests, getClientRequests, respondToRequest,
  createCase, updateCaseStatus, getOrCreateConversation, getUser, isLoggedIn
} from '@/lib/api';

export default function CasesPage() {
  const [cases, setCases] = useState([]);
  const [requests, setRequests] = useState([]);
  const [clientRequests, setClientRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showNewCase, setShowNewCase] = useState(false);
  const [creating, setCreating] = useState(false);
  const [activeTab, setActiveTab] = useState('cases');
  const [newCase, setNewCase] = useState({ title: '', description: '', law_domain: '', jurisdiction: '' });
  const [expandedCase, setExpandedCase] = useState(null);
  const [actionLoading, setActionLoading] = useState({});
  const router = useRouter();
  const currentUser = getUser();

  useEffect(() => {
    if (!isLoggedIn()) { router.push('/login'); return; }
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [casesData, reqData, clientReqData] = await Promise.all([
        getMyCases(),
        currentUser?.role === 'lawyer' ? getMyRequests('') : Promise.resolve([]),
        currentUser?.role === 'client' ? getClientRequests().catch(() => []) : Promise.resolve([]),
      ]);
      setCases(casesData);
      setRequests(reqData);
      setClientRequests(clientReqData);
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
    setActionLoading(prev => ({ ...prev, [requestId]: status }));
    try {
      await respondToRequest(requestId, status);
      loadData();
    } catch (err) {
      alert(err.message || 'Failed to respond');
    } finally {
      setActionLoading(prev => { const n = { ...prev }; delete n[requestId]; return n; });
    }
  };

  const handleCloseCase = async (caseId) => {
    if (!confirm('Mark this case as closed? This cannot be undone.')) return;
    setActionLoading(prev => ({ ...prev, [`close_${caseId}`]: true }));
    try {
      await updateCaseStatus(caseId, 'closed');
      loadData();
    } catch (err) {
      alert(err.message || 'Failed to update case status');
    } finally {
      setActionLoading(prev => { const n = { ...prev }; delete n[`close_${caseId}`]; return n; });
    }
  };

  const handleOpenChat = async (lawyerUserId) => {
    setActionLoading(prev => ({ ...prev, [`chat_${lawyerUserId}`]: true }));
    try {
      const conv = await getOrCreateConversation(lawyerUserId, null, null);
      router.push('/chat/' + conv.conv_id);
    } catch (err) {
      alert(err.message || 'Could not open chat');
    } finally {
      setActionLoading(prev => { const n = { ...prev }; delete n[`chat_${lawyerUserId}`]; return n; });
    }
  };

  const statusConfig = {
    open: { label: 'Open', bg: 'bg-blue-50', text: 'text-blue-700', icon: <Clock className="w-3 h-3" /> },
    in_progress: { label: 'Ongoing', bg: 'bg-amber-50', text: 'text-amber-700', icon: <AlertCircle className="w-3 h-3" /> },
    closed: { label: 'Closed', bg: 'bg-gray-100', text: 'text-gray-600', icon: <CheckCircle className="w-3 h-3" /> },
  };

  const requestStatusConfig = {
    pending: { label: 'Pending', bg: 'bg-amber-50', text: 'text-amber-700' },
    accepted: { label: 'Accepted', bg: 'bg-emerald-50', text: 'text-emerald-700' },
    rejected: { label: 'Declined', bg: 'bg-red-50', text: 'text-red-700' },
  };

  const getRequestsForCase = (caseId) =>
    clientRequests.filter(r => r.case_id === caseId);

  return (
    <div className="min-h-screen bg-[#F6F8FB] px-4 lg:px-8 py-8">
      <div className="max-w-4xl mx-auto">
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
                {tab === 'requests' ? `Pending Requests (${requests.filter(r => r.status === 'pending').length})` : 'My Cases'}
              </button>
            ))}
          </div>
        )}

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
                const caseRequests = currentUser?.role === 'client' ? getRequestsForCase(c.case_id) : [];
                const isExpanded = expandedCase === c.case_id;
                const isInProgress = c.status === 'in_progress';
                const isClosed = c.status === 'closed';

                return (
                  <div key={c.case_id} className="bg-white rounded-2xl border border-gray-200 shadow-sm">
                    <div className="p-6">
                      <div className="flex items-start justify-between mb-3">
                        <div className="flex-1 min-w-0">
                          <h3 className="font-semibold text-gray-900">{c.title}</h3>
                          <p className="text-sm text-gray-500 mt-0.5">{c.law_domain}{c.jurisdiction ? ` · ${c.jurisdiction}` : ''}</p>
                        </div>
                        <span className={`flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium flex-shrink-0 ml-3 ${st.bg} ${st.text}`}>
                          {st.icon}{st.label}
                        </span>
                      </div>
                      <p className="text-sm text-gray-600 mb-4 line-clamp-2">{c.description}</p>

                      {currentUser?.role === 'client' && isInProgress && c.assigned_lawyer_name && (
                        <p className="text-xs text-emerald-700 bg-emerald-50 rounded-lg px-3 py-1.5 mb-3 inline-block">
                          Assigned to: {c.assigned_lawyer_name}
                        </p>
                      )}

                      {currentUser?.role === 'lawyer' && isInProgress && (
                        <p className="text-xs text-emerald-700 bg-emerald-50 rounded-lg px-3 py-1.5 mb-3 inline-block">
                          Client: {c.client_name || 'Client'}
                        </p>
                      )}

                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <span className="text-xs text-gray-400">{new Date(c.created_at).toLocaleDateString()}</span>

                        <div className="flex flex-wrap gap-2">
                          {currentUser?.role === 'client' && !isClosed && (
                            <>
                              {c.status === 'open' && (
                                <button onClick={() => router.push('/find-lawyers')}
                                  className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-[#052379] border border-[#052379]/20 bg-blue-50 rounded-lg hover:bg-blue-100 transition-colors">
                                  Find Lawyer
                                </button>
                              )}
                              {isInProgress && (() => {
                                const acceptedReq = clientRequests.find(r => r.case_id === c.case_id && r.status === 'accepted');
                                const lawyerId = acceptedReq?.lawyer_id;
                                return (
                                  <>
                                    <button
                                      onClick={() => lawyerId && handleOpenChat(lawyerId)}
                                      disabled={!lawyerId || !!actionLoading[`chat_${lawyerId}`]}
                                      className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-white bg-[#052379] rounded-lg hover:bg-[#041d5c] transition-colors disabled:opacity-50">
                                      {actionLoading[`chat_${lawyerId}`]
                                        ? <Loader2 className="w-3 h-3 animate-spin" />
                                        : <MessageSquare className="w-3 h-3" />}
                                      Chat
                                    </button>
                                    <button onClick={() => lawyerId && router.push(`/appointments/new?lawyer=${lawyerId}&case=${c.case_id}`)}
                                      disabled={!lawyerId}
                                      className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-gray-700 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-50">
                                      <Calendar className="w-3 h-3" />
                                      Appointment
                                    </button>
                                    <button onClick={() => handleCloseCase(c.case_id)}
                                      disabled={actionLoading[`close_${c.case_id}`]}
                                      className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-red-600 border border-red-200 rounded-lg hover:bg-red-50 transition-colors disabled:opacity-50">
                                      {actionLoading[`close_${c.case_id}`] ? <Loader2 className="w-3 h-3 animate-spin" /> : <XCircle className="w-3 h-3" />}
                                      Close Case
                                    </button>
                                  </>
                                );
                              })()}
                            </>
                          )}

                          {currentUser?.role === 'lawyer' && isInProgress && (
                            <>
                              <button
                                onClick={() => handleOpenChat(c.user_id)}
                                disabled={actionLoading[`chat_${c.user_id}`]}
                                className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-white bg-[#052379] rounded-lg hover:bg-[#041d5c] transition-colors disabled:opacity-50">
                                {actionLoading[`chat_${c.user_id}`]
                                  ? <Loader2 className="w-3 h-3 animate-spin" />
                                  : <MessageSquare className="w-3 h-3" />}
                                Chat
                              </button>
                              <button onClick={() => handleCloseCase(c.case_id)}
                                disabled={actionLoading[`close_${c.case_id}`]}
                                className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-red-600 border border-red-200 rounded-lg hover:bg-red-50 transition-colors disabled:opacity-50">
                                {actionLoading[`close_${c.case_id}`] ? <Loader2 className="w-3 h-3 animate-spin" /> : <XCircle className="w-3 h-3" />}
                                Close Case
                              </button>
                            </>
                          )}

                          {currentUser?.role === 'client' && caseRequests.length > 0 && c.status === 'open' && (
                            <button onClick={() => setExpandedCase(isExpanded ? null : c.case_id)}
                              className="flex items-center gap-1 px-3 py-1.5 text-xs font-medium text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors">
                              {isExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                              Requests ({caseRequests.length})
                            </button>
                          )}
                        </div>
                      </div>

                      {currentUser?.role === 'client' && isExpanded && caseRequests.length > 0 && (
                        <div className="mt-4 pt-4 border-t border-gray-100 space-y-2">
                          <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">Case Requests</p>
                          {caseRequests.map(req => {
                            const rSt = requestStatusConfig[req.status] || requestStatusConfig.pending;
                            return (
                              <div key={req.request_id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                                <span className="text-sm text-gray-700">{req.lawyer_name || `Lawyer #${req.lawyer_id}`}</span>
                                <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${rSt.bg} ${rSt.text}`}>
                                  {rSt.label}
                                </span>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        ) : (
          <div className="space-y-4">
            {requests.filter(r => r.status === 'pending').length === 0 ? (
              <div className="bg-white rounded-2xl border border-gray-200 p-12 text-center">
                <p className="text-gray-500">No pending case requests.</p>
              </div>
            ) : (
              requests.filter(r => r.status === 'pending').map(req => (
                <div key={req.request_id} className="bg-white rounded-2xl border border-gray-200 p-6 shadow-sm">
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <h3 className="font-semibold text-gray-900">{req.case_title || `Case #${req.case_id}`}</h3>
                      <p className="text-sm text-gray-500 mt-0.5">From: {req.client_name || 'Client'}</p>
                      {req.case_law_domain && (
                        <p className="text-xs text-gray-400 mt-0.5">{req.case_law_domain}</p>
                      )}
                    </div>
                    <span className="px-2.5 py-1 bg-amber-50 text-amber-700 rounded-full text-xs font-medium flex-shrink-0 ml-3">Pending</span>
                  </div>
                  {req.case_description && (
                    <p className="text-sm text-gray-600 mb-4 line-clamp-3">{req.case_description}</p>
                  )}
                  <div className="flex gap-3 mt-4">
                    <button onClick={() => handleRespond(req.request_id, 'accepted')}
                      disabled={!!actionLoading[req.request_id]}
                      className="flex-1 py-2 bg-emerald-600 text-white text-sm font-medium rounded-lg hover:bg-emerald-700 transition-colors disabled:opacity-50 flex items-center justify-center gap-2">
                      {actionLoading[req.request_id] === 'accepted' ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                      Accept
                    </button>
                    <button onClick={() => handleRespond(req.request_id, 'rejected')}
                      disabled={!!actionLoading[req.request_id]}
                      className="flex-1 py-2 bg-white border border-gray-200 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-50 flex items-center justify-center gap-2">
                      {actionLoading[req.request_id] === 'rejected' ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
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
