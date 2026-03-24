"use client";

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import {
  Search,
  MapPin,
  Star,
  Briefcase,
  DollarSign,
  ChevronDown,
  Loader2
} from 'lucide-react';
import { searchLawyers } from '@/lib/api';

export default function FindLawyersPage() {
  const router = useRouter();
  const [searchQuery, setSearchQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [filters, setFilters] = useState({
    location: '',
    rating: '',
    feeRange: ''
  });

  const [lawyers, setLawyers] = useState([]);

  useEffect(() => {
    if (typeof window !== 'undefined') {
      try {
        const u = JSON.parse(localStorage.getItem('lawgic_user') || 'null');
        if (u?.role === 'lawyer') { router.replace('/dashboard/lawyer'); return; }
      } catch {}
    }
    fetchLawyers();
  }, [filters]);

  const fetchLawyers = async (query = searchQuery) => {
    setIsLoading(true);
    try {
      const params = {};
      if (query) params.q = query;
      if (filters.location) params.city = filters.location;
      const data = await searchLawyers(params);
      // Map API response to FE shape
      setLawyers(data.map(l => ({
        id: l.lawyer_id,
        name: l.name,
        image: 'https://placehold.co/100x100',
        specializations: l.specializations && l.specializations.length > 0 ? l.specializations : [l.specialization],
        location: l.city || l.office_address || 'Pakistan',
        experience: l.years_of_experience ? l.years_of_experience + ' years' : 'N/A',
        rating: l.average_rating || 0,
        reviews: l.review_count || 0,
        fee: l.consultation_fee ? 'PKR ' + l.consultation_fee.toLocaleString() : 'Contact for fee',
        description: l.bio_data || 'Experienced legal professional.',
      })));
    } catch (error) {
      console.error('Failed to fetch lawyers:', error);
    } finally {
      setIsLoading(false);
    }
  };

  
  const handleSearch = (e) => {
    setSearchQuery(e.target.value);
    
    fetchLawyers(e.target.value); 
  };

  return (
    <div className="w-full min-h-screen bg-[#F6F8FB] px-6 lg:px-12 py-12">
      
      <div className="mb-8">
        <h1 className="text-3xl font-medium text-gray-900 mb-2">Find a Lawyer</h1>
        <p className="text-gray-600">Connect with verified legal professionals in your area.</p>
      </div>

   
      <div className="bg-white rounded-2xl border border-gray-200 p-4 mb-8 shadow-sm">
        <div className="flex flex-col lg:flex-row gap-4">
          
          <div className="flex-1 relative">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input 
              type="text" 
              value={searchQuery}
              onChange={handleSearch}
              placeholder="Search by name, specialization..." 
              className="w-full pl-12 pr-4 py-3 bg-[#F6F8FB] border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#052379]/20 focus:border-[#052379] transition-all"
            />
          </div>

          <div className="flex gap-3 overflow-x-auto pb-2 lg:pb-0">
            <button className="flex items-center gap-2 px-4 py-3 bg-[#F6F8FB] border border-gray-200 rounded-xl text-sm font-medium text-gray-700 hover:bg-gray-50 whitespace-nowrap">
              <span>Location</span>
              <ChevronDown className="w-4 h-4 text-gray-400" />
            </button>

            <button className="flex items-center gap-2 px-4 py-3 bg-[#F6F8FB] border border-gray-200 rounded-xl text-sm font-medium text-gray-700 hover:bg-gray-50 whitespace-nowrap">
              <span>Rating</span>
              <ChevronDown className="w-4 h-4 text-gray-400" />
            </button>

            <button className="flex items-center gap-2 px-4 py-3 bg-[#F6F8FB] border border-gray-200 rounded-xl text-sm font-medium text-gray-700 hover:bg-gray-50 whitespace-nowrap">
              <span>Fee Range</span>
              <ChevronDown className="w-4 h-4 text-gray-400" />
            </button>
          </div>
        </div>
      </div>

      <div className="mb-6">
        <p className="text-gray-600">Showing {lawyers.length} verified lawyers</p>
      </div>

      <div className="grid grid-cols-1 gap-6">
        {isLoading ? (
          <div className="flex flex-col items-center justify-center py-20">
            <Loader2 className="w-10 h-10 text-[#052379] animate-spin mb-4" />
            <p className="text-gray-500">Searching for lawyers...</p>
          </div>
        ) : (
          lawyers.map((lawyer) => (
            <div 
              key={lawyer.id} 
              className="bg-white rounded-2xl border border-gray-200 p-6 hover:shadow-md transition-all duration-300 flex flex-col md:flex-row gap-6"
            >
              
              <div className="flex-shrink-0">
                <img 
                  src={lawyer.image} 
                  alt={lawyer.name} 
                  className="w-24 h-24 md:w-32 md:h-32 rounded-xl object-cover bg-gray-100"
                />
              </div>

              <div className="flex-1">
                <div className="flex flex-col md:flex-row md:items-start justify-between mb-2">
                  <div>
                    <h3 className="text-xl font-semibold text-gray-900 mb-1">{lawyer.name}</h3>
                    <div className="flex flex-wrap gap-2 mb-3">
                      {lawyer.specializations.map((spec, index) => (
                        <span key={index} className="px-3 py-1 bg-blue-50 text-[#052379] text-xs font-medium rounded-full">
                          {spec}
                        </span>
                      ))}
                    </div>
                  </div>
              
                  <div className="flex items-center gap-1 bg-amber-50 px-2 py-1 rounded-lg border border-amber-100 self-start">
                    <Star className="w-4 h-4 text-amber-500 fill-amber-500" />
                    <span className="text-sm font-bold text-amber-700">{lawyer.rating}</span>
                    <span className="text-xs text-amber-600">({lawyer.reviews})</span>
                  </div>
                </div>

                <p className="text-gray-600 text-sm mb-6 leading-relaxed">
                  {lawyer.description}
                </p>

                <div className="grid grid-cols-2 md:grid-cols-3 gap-4 border-t border-gray-100 pt-4 mb-6">
                  <div className="flex flex-col gap-1">
                    <span className="text-xs text-gray-500 uppercase tracking-wide">Experience</span>
                    <div className="flex items-center gap-2 text-gray-900 text-sm font-medium">
                      <Briefcase className="w-4 h-4 text-gray-400" />
                      {lawyer.experience}
                    </div>
                  </div>
                  
                  <div className="flex flex-col gap-1">
                    <span className="text-xs text-gray-500 uppercase tracking-wide">Location</span>
                    <div className="flex items-center gap-2 text-gray-900 text-sm font-medium">
                      <MapPin className="w-4 h-4 text-gray-400" />
                      {lawyer.location}
                    </div>
                  </div>

                  <div className="flex flex-col gap-1 col-span-2 md:col-span-1">
                    <span className="text-xs text-gray-500 uppercase tracking-wide">Consultation Fee</span>
                    <div className="flex items-center gap-2 text-gray-900 text-sm font-medium">
                      <DollarSign className="w-4 h-4 text-gray-400" />
                      {lawyer.fee}
                    </div>
                  </div>
                </div>

               
                <div className="flex justify-end">
                  <button onClick={() => { window.location.href = '/lawyers/' + lawyer.id; }} className="w-full md:w-auto px-6 py-2.5 bg-[#052379] text-white text-sm font-medium rounded-lg hover:bg-[#041d5c] transition-colors">
                    View Profile
                  </button>
                </div>
              </div>
            </div>
          ))
        )}
      </div>

    </div>
  );
}