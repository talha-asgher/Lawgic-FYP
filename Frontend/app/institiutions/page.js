"use client";

import React, { useState } from 'react';
import {
  Search,
  MapPin,
  Phone,
  Clock,
  Navigation,
  Loader2
} from 'lucide-react';
import { useLanguage } from '@/app/lib/LanguageContext';

export default function InstitutionsPage() {
  const { t, lang } = useLanguage();
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedType, setSelectedType] = useState('all');
  const [isLoading, setIsLoading] = useState(false);

  const [institutions] = useState([
    {
      id: 1,
      name: 'Police Station - Defence A',
      city: 'Lahore',
      distance: '1.3 km',
      phone: '+92 308 7777361',
      hours: 'Open 24 hours',
      type: 'police',
      coordinates: { lat: 31.48, lng: 74.39 }
    },
    {
      id: 2,
      name: 'Police Station - Defence B',
      city: 'Lahore',
      distance: '1.8 km',
      phone: '+92 300 4793328',
      hours: 'Open 24 hours',
      type: 'police',
      coordinates: { lat: 31.49, lng: 74.40 }
    },
    {
      id: 3,
      name: 'Lahore High Court',
      city: 'Lahore',
      distance: '5.2 km',
      phone: '+92 42 99212951',
      hours: 'Mon-Sat: 8:00 AM - 4:00 PM',
      type: 'court',
      coordinates: { lat: 31.55, lng: 74.34 }
    }
  ]);

  const fetchInstitutions = async (query = '', type = 'all') => {
    setIsLoading(true);
    try {
      await new Promise(resolve => setTimeout(resolve, 800));
    } catch (error) {
      console.error("Failed to fetch institutions:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSearch = (e) => {
    setSearchQuery(e.target.value);
    fetchInstitutions(e.target.value, selectedType);
  };

  const handleTypeChange = (type) => {
    setSelectedType(type);
    fetchInstitutions(searchQuery, type);
  };

  const typeLabels = {
    all: t("institutions.allTypes"),
    police: t("institutions.typePolice"),
    court: t("institutions.typeCourt"),
    lawyer: t("institutions.typeLawyer"),
  };

  return (
    <div className="w-full min-h-screen bg-[#F6F8FB] px-6 lg:px-12 py-12">

      <div className="mb-8">
        <h1 className="text-3xl font-medium text-gray-900 mb-2">
          {t("institutions.heading")}
        </h1>
        <p className="text-gray-600">{t("institutions.subtitle")}</p>
      </div>

      <div className="bg-white rounded-2xl border border-gray-200 p-6 mb-8 shadow-sm">
        <div className="flex flex-col md:flex-row gap-4">

          <div className="flex-1 relative">
            <Search className={`absolute ${lang === 'ur' ? 'end-4' : 'start-4'} top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400`} />
            <input
              type="text"
              value={searchQuery}
              onChange={handleSearch}
              placeholder={t("institutions.searchPlaceholder")}
              className={`w-full ${lang === 'ur' ? 'pe-12 ps-4' : 'ps-12 pe-4'} py-3 bg-[#F6F8FB] border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#052379]/20 focus:border-[#052379] transition-all`}
            />
          </div>

          <div className="flex gap-3 overflow-x-auto pb-2 md:pb-0">
            {['all', 'police', 'court', 'lawyer'].map((type) => (
              <button
                key={type}
                onClick={() => handleTypeChange(type)}
                className={`px-6 py-3 rounded-xl text-sm font-medium whitespace-nowrap transition-all border ${
                  selectedType === type
                    ? 'bg-[#052379] text-white border-[#052379]'
                    : 'bg-white text-gray-700 border-gray-200 hover:bg-gray-50'
                }`}
              >
                {typeLabels[type]}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 h-[calc(100vh-300px)] min-h-[500px]">

        <div className="bg-white rounded-2xl border border-gray-200 overflow-hidden relative shadow-sm group">

          <img
            src="/map-placeholder.png"
            alt={t("institutions.mapView")}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-700"
            onError={(e) => {
              e.target.onerror = null;
              e.target.src = "https://placehold.co/600x800?text=Map+View";
            }}
          />

          <div className="absolute inset-0 bg-gradient-to-t from-black/50 to-transparent opacity-60" />
          <div className="absolute bottom-6 start-6 text-white">
            <div className="flex items-center gap-2 mb-1">
              <MapPin className="w-5 h-5" />
              <span className="font-medium">{t("institutions.mapView")}</span>
            </div>
            <p className="text-sm opacity-90">{t("institutions.mapResults", { count: institutions.length })}</p>
          </div>
        </div>

        <div className="overflow-y-auto pe-2 space-y-4">
          {isLoading ? (
            <div className="flex flex-col items-center justify-center h-40">
              <Loader2 className="w-8 h-8 text-[#052379] animate-spin mb-2" />
              <p className="text-gray-500">{t("institutions.findingNearby")}</p>
            </div>
          ) : (
            institutions.map((item) => (
              <div
                key={item.id}
                className="bg-white rounded-2xl border border-gray-200 p-6 hover:shadow-md hover:border-[#052379]/30 transition-all duration-300 group"
              >
                <div className="flex justify-between items-start mb-4">
                  <div>
                    <h3 className="text-lg font-medium text-gray-900 mb-1 group-hover:text-[#052379] transition-colors">
                      {item.name}
                    </h3>
                    <p className="text-gray-500 text-sm flex items-center gap-1">
                      <MapPin className="w-3 h-3" /> {item.city}
                    </p>
                  </div>
                  <span className="px-3 py-1 bg-gray-100 text-gray-700 text-xs font-medium rounded-full">
                    {item.distance}
                  </span>
                </div>

                <div className="space-y-3 mb-6">
                  <div className="flex items-center gap-3 text-gray-600 text-sm">
                    <Phone className="w-4 h-4 text-gray-400" />
                    {item.phone}
                  </div>
                  <div className="flex items-center gap-3 text-gray-600 text-sm">
                    <Clock className="w-4 h-4 text-gray-400" />
                    <span className={item.hours.includes('24') ? 'text-emerald-600 font-medium' : ''}>
                      {item.hours}
                    </span>
                  </div>
                </div>

                <div className="flex gap-3">
                  <button className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-[#052379] text-white rounded-xl text-sm font-medium hover:bg-[#041d5c] transition-colors">
                    <Navigation className="w-4 h-4" />
                    {t("institutions.getDirections")}
                  </button>
                  <button className="px-4 py-2.5 border border-gray-200 text-gray-700 rounded-xl text-sm font-medium hover:bg-gray-50 transition-colors">
                    {t("institutions.call")}
                  </button>
                </div>
              </div>
            ))
          )}
        </div>

      </div>
    </div>
  );
}
