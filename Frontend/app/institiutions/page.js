"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import dynamic from 'next/dynamic';
import { 
  Search, MapPin, Loader2, Phone, Scale, Globe, X, ExternalLink, Navigation 
} from "lucide-react";

const Map = dynamic(() => import('../lib/Map'), { 
  ssr: false,
  loading: () => (
    <div className="w-full h-full bg-gray-100 flex items-center justify-center">
      <Loader2 className="animate-spin text-blue-600" />
      <span className="ml-2 text-gray-500">Loading Map...</span>
    </div>
  )
});

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

const TYPE_CONFIG = {
  all:    { label: "All Institutions", icon: <Globe className="w-4 h-4" /> },
  police: { label: "Police Stations", icon: <Scale className="w-4 h-4" /> },
  court:  { label: "Legal Courts", icon: <Scale className="w-4 h-4" /> },
  lawyer: { label: "Law Firms", icon: <Search className="w-4 h-4" /> },
};

function InstitutionCard({ inst, onViewDetails }) {
  const typeStyles = {
    police: "text-blue-600 bg-blue-50 border-blue-100",
    court: "text-purple-600 bg-purple-50 border-purple-100",
    lawyer: "text-emerald-600 bg-emerald-50 border-emerald-100",
    default: "text-gray-600 bg-gray-50 border-gray-100"
  };

  const style = typeStyles[inst.type] || typeStyles.default;

  return (
    <div className="group bg-white rounded-2xl border border-gray-100 p-5 hover:border-blue-200 hover:shadow-xl hover:shadow-blue-500/5 transition-all duration-300 cursor-pointer"
         onClick={() => onViewDetails(inst)}>
      <div className="flex justify-between items-start mb-4">
        <span className={`text-[10px] uppercase tracking-wider font-bold px-2.5 py-1 rounded-lg border ${style}`}>
          {inst.type}
        </span>
      </div>
      
      <h3 className="font-bold text-gray-900 text-lg mb-2 group-hover:text-blue-700 transition-colors">
        {inst.name}
      </h3>

      <div className="space-y-2 mb-5">
        <p className="text-sm text-gray-500 flex items-center gap-2">
          <MapPin className="w-4 h-4 text-gray-400" />
          <span className="truncate">{inst.address || "Location not listed"}</span>
        </p>
      </div>

      <button className="w-full bg-gray-50 text-gray-700 font-medium py-2.5 rounded-xl text-sm group-hover:bg-[#052379] group-hover:text-white transition-all flex items-center justify-center gap-2">
        View Details
        <ExternalLink className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}

export default function InstitutionsPage() {
  const [institutions, setInstitutions] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedType, setSelectedType] = useState("all");
  const [selectedInstitution, setSelectedInstitution] = useState(null);
  const debounceRef = useRef(null);

  const fetchInstitutions = useCallback(async (query, type) => {
    setIsLoading(true);
    try {
      const params = new URLSearchParams();
      if (query) params.append("q", query);
      if (type !== "all") params.append("inst_type", type);
      const res = await fetch(`${API_BASE_URL}/institutions/?${params}`);
      const data = await res.json();
      setInstitutions(data);
    } catch (err) {
      console.error("Fetch error:", err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { fetchInstitutions("", "all"); }, [fetchInstitutions]);

  const handleSearch = (e) => {
    const val = e.target.value;
    setSearchQuery(val);
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => fetchInstitutions(val, selectedType), 400);
  };

  return (
    <div className="p-6 md:p-10 bg-[#FAFBFE] min-h-screen font-sans">
      
      {/* Header Section */}
      <div className="max-w-7xl mx-auto mb-10">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div>
            <h1 className="text-3xl font-extrabold text-gray-900 tracking-tight">Legal Directory</h1>
            <p className="text-gray-500 mt-1">Find and contact legal institutions for Lawgic.</p>
          </div>
          
          <div className="relative w-full md:w-96">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              value={searchQuery}
              onChange={handleSearch}
              placeholder="Search by name or specialty..."
              className="w-full pl-12 pr-4 py-3.5 bg-white border border-gray-200 rounded-2xl focus:ring-4 focus:ring-blue-500/10 focus:border-blue-500 outline-none transition-all shadow-sm"
            />
          </div>
        </div>

        {/* Filters */}
        <div className="flex gap-3 mt-8 overflow-x-auto pb-2 scrollbar-hide">
          {Object.entries(TYPE_CONFIG).map(([key, { label, icon }]) => (
            <button
              key={key}
              onClick={() => { setSelectedType(key); fetchInstitutions(searchQuery, key); }}
              className={`flex items-center gap-2 px-5 py-2.5 rounded-full text-sm font-semibold whitespace-nowrap transition-all border ${
                selectedType === key 
                ? "bg-[#052379] text-white border-[#052379] shadow-lg shadow-blue-900/20" 
                : "bg-white text-gray-600 border-gray-200 hover:border-gray-300"
              }`}
            >
              {icon}
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto">
        {isLoading ? (
          <div className="flex flex-col items-center justify-center py-20">
            <Loader2 className="w-10 h-10 animate-spin text-blue-600 mb-4" />
            <p className="text-gray-500 font-medium">Loading...</p>
          </div>
        ) : institutions.length > 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {institutions.map((inst) => (
              <InstitutionCard key={inst.inst_id} inst={inst} onViewDetails={setSelectedInstitution} />
            ))}
          </div>
        ) : (
          <div className="text-center py-20 bg-white rounded-3xl border border-dashed border-gray-300">
            <p className="text-gray-500">No results found.</p>
          </div>
        )}
      </div>

      {/* Modal with Dynamic Map */}
      {selectedInstitution && (
        <div className="fixed inset-0 bg-gray-900/60 backdrop-blur-sm flex justify-center items-center z-[1000] p-4">
          <div className="bg-white w-full max-w-5xl h-[90vh] md:h-[70vh] rounded-[2rem] shadow-2xl overflow-hidden flex flex-col md:flex-row animate-in fade-in zoom-in duration-300">
            
            {/* Map Area */}
            <div className="w-full md:w-1/2 h-64 md:h-auto relative bg-gray-100">
                <Map 
                  latitude={selectedInstitution.latitude} 
                  longitude={selectedInstitution.longitude} 
                  name={selectedInstitution.name} 
                />
            </div>

            {/* Content Area */}
            <div className="w-full md:w-1/2 p-8 flex flex-col overflow-y-auto">
              <div className="flex justify-between items-start mb-6">
                <div>
                  <span className="text-blue-600 font-bold text-xs uppercase tracking-widest">{selectedInstitution.type}</span>
                  <h2 className="text-2xl font-bold text-gray-900 mt-1">{selectedInstitution.name}</h2>
                </div>
                <button onClick={() => setSelectedInstitution(null)} className="p-2 hover:bg-gray-100 rounded-full transition-colors">
                  <X className="w-6 h-6 text-gray-400" />
                </button>
              </div>

              <div className="space-y-6 flex-grow">
                <DetailRow icon={<MapPin className="text-blue-600" />} label="Address" value={selectedInstitution.address} />
                <DetailRow icon={<Phone className="text-green-600" />} label="Contact" value={selectedInstitution.phone} />
                <DetailRow icon={<Scale className="text-purple-600" />} label="Jurisdiction" value={selectedInstitution.jurisdiction} />
              </div>

              <div className="mt-8 pt-6 border-t border-gray-100">
                <button
                  onClick={() => window.open(`https://www.google.com/maps?q=${selectedInstitution.latitude},${selectedInstitution.longitude}`)}
                  className="w-full bg-[#052379] text-white py-4 rounded-2xl font-bold flex items-center justify-center gap-3 hover:bg-[#041d5c] transition-all"
                >
                  <Navigation className="w-5 h-5" />
                  Get Directions
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function DetailRow({ icon, label, value }) {
  return (
    <div className="flex gap-4">
      <div className="p-3 bg-gray-50 rounded-xl h-fit">{icon}</div>
      <div>
        <p className="text-xs text-gray-400 font-bold uppercase">{label}</p>
        <p className="text-gray-700">{value || "Information not available"}</p>
      </div>
    </div>
  );
}