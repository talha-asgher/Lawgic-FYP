"use client";

import React, { useState, useEffect } from 'react';
import { 
  Search, 
  MapPin, 
  Star, 
  Filter, 
  Briefcase, 
  Clock, 
  DollarSign, 
  ChevronDown, 
  Loader2 
} from 'lucide-react';

export default function FindLawyersPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [filters, setFilters] = useState({
    location: '',
    rating: '',
    feeRange: ''
  });

  const [lawyers, setLawyers] = useState([
    {
      id: 1,
      name: "Advocate Sarah Khan",
      image: "https://placehold.co/100x100",
      specializations: ["Civil Law", "Family Law"],
      location: "Lahore",
      experience: "12 years",
      rating: 4.8,
      reviews: 124,
      fee: "PKR 5,000 - 15,000",
      description: "Specializes in property, contract, and family dispute cases with a high success rate in civil litigation."
    },
    {
      id: 2,
      name: "Advocate Ahmed Malik",
      image: "https://placehold.co/100x100",
      specializations: ["Criminal Law", "Corporate Law"],
      location: "Karachi",
      experience: "15 years",
      rating: 4.9,
      reviews: 89,
      fee: "PKR 10,000 - 25,000",
      description: "Expert in criminal defense and corporate structuring. Former legal advisor to multinational corporations."
    },
    {
      id: 3,
      name: "Advocate Fatima Ali",
      image: "https://placehold.co/100x100",
      specializations: ["Family Law", "Immigration"],
      location: "Islamabad",
      experience: "8 years",
      rating: 4.7,
      reviews: 56,
      fee: "PKR 8,000 - 20,000",
      description: "Dedicated to helping families navigate complex legal matters including divorce, custody, and immigration."
    }
  ]);

  useEffect(() => {
    fetchLawyers();
  }, [filters]); 

  const fetchLawyers = async (query = searchQuery) => {
    setIsLoading(true);
    try {
     
      /*
      // Build query string from filters
      const queryParams = new URLSearchParams({
        search: query,
        location: filters.location,
        minRating: filters.rating,
        // ... other filters
      }).toString();

      const response = await fetch(`http://localhost:5000/api/lawyers?${queryParams}`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' }
      });
      
      const data = await response.json();
      setLawyers(data.lawyers);
      */

       await new Promise(resolve => setTimeout(resolve, 600)); // Simulate network load
     
    } catch (error) {
      console.error("Failed to fetch lawyers:", error);
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
                  <button className="w-full md:w-auto px-6 py-2.5 bg-[#052379] text-white text-sm font-medium rounded-lg hover:bg-[#041d5c] transition-colors">
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