"use client";

import React, { useState, useEffect } from 'react';
import { 
  Check, 
  ChevronRight, 
  ChevronLeft, 
  UploadCloud, 
  ShieldCheck, 
  FileText, 
  Briefcase, 
  User, 
  Phone, 
  GraduationCap, 
  Loader2
} from 'lucide-react';

export default function LawyerRegistration() {

  const [currentStep, setCurrentStep] = useState(1);
  const [loading, setLoading] = useState(false);

  const [formData, setFormData] = useState({
    fullName: '',
    barNumber: '',
    jurisdiction: '',
    experience: '',
    specialization: '',
    firmName: '',
    email: '',
    phone: '',
    officeAddress: '',
    city: '',
    lawSchool: '',
    gradYear: '',
    degreeType: 'LLB',
    barLicenseFile: null,
    cnicFile: null,
    password: '',
    confirmPassword: '',
    bio: '',
    hourlyRate: '',
    languages: []
  });

  
  const steps = [
    { id: 1, title: 'Professional', icon: <Briefcase className="w-5 h-5" /> },
    { id: 2, title: 'Contact', icon: <Phone className="w-5 h-5" /> },
    { id: 3, title: 'Education', icon: <GraduationCap className="w-5 h-5" /> },
    { id: 4, title: 'Documents', icon: <FileText className="w-5 h-5" /> },
    { id: 5, title: 'Security', icon: <ShieldCheck className="w-5 h-5" /> },
    { id: 6, title: 'Additional', icon: <User className="w-5 h-5" /> },
  ];

  
  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleFileChange = (e) => {
    const { name, files } = e.target;
    setFormData(prev => ({ ...prev, [name]: files[0] }));
  };

  const handleNext = () => {
    if (currentStep < steps.length) {
      setCurrentStep(prev => prev + 1);
      window.scrollTo(0, 0);
    } else {
      handleSubmit();
    }
  };

  const handleBack = () => {
    if (currentStep > 1) {
      setCurrentStep(prev => prev - 1);
      window.scrollTo(0, 0);
    }
  };

  const handleSubmit = async () => {
    setLoading(true);
    try {
      const dataPayload = new FormData();
      
      Object.keys(formData).forEach(key => {
        if (key !== 'barLicenseFile' && key !== 'cnicFile') {
          dataPayload.append(key, formData[key]);
        }
      });

      if (formData.barLicenseFile) dataPayload.append('barLicense', formData.barLicenseFile);
      if (formData.cnicFile) dataPayload.append('cnic', formData.cnicFile);

      /*
      const response = await fetch('http://localhost:5000/api/auth/register-lawyer', {
        method: 'POST',
        body: dataPayload, // No Content-Type header needed for FormData
      });

      if (!response.ok) throw new Error('Registration failed');
      
      // Redirect to Login
      window.location.href = '/login';
      */

      console.log("Submitting Lawyer Data:", formData);
      await new Promise(resolve => setTimeout(resolve, 2000));
      alert("Registration Submitted for Review!");
      
    } catch (error) {
      console.error("Submission Error:", error);
    } finally {
      setLoading(false);
    }
  };

  const renderStepContent = () => {
    switch (currentStep) {
      case 1: 
        return (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-900">Full Legal Name <span className="text-red-500">*</span></label>
              <input 
                type="text" 
                name="fullName" 
                value={formData.fullName} 
                onChange={handleChange} 
                placeholder="Advocate Name" 
                className="w-full p-3 bg-gray-50 border border-gray-200 rounded-lg focus:ring-2 focus:ring-[#052379]/20 outline-none text-gray-900 placeholder:text-gray-500" 
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-900">Bar Association ID <span className="text-red-500">*</span></label>
              <input 
                type="text" 
                name="barNumber" 
                value={formData.barNumber} 
                onChange={handleChange} 
                placeholder="e.g., PK-BAR-2023" 
                className="w-full p-3 bg-gray-50 border border-gray-200 rounded-lg focus:ring-2 focus:ring-[#052379]/20 outline-none text-gray-900 placeholder:text-gray-500" 
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-900">Jurisdiction <span className="text-red-500">*</span></label>
              <select 
                name="jurisdiction" 
                value={formData.jurisdiction} 
                onChange={handleChange} 
                className="w-full p-3 bg-gray-50 border border-gray-200 rounded-lg focus:ring-2 focus:ring-[#052379]/20 outline-none text-gray-900"
              >
                <option value="">Select Jurisdiction</option>
                <option value="lahore">Lahore High Court</option>
                <option value="karachi">Sindh High Court</option>
                <option value="islamabad">Islamabad High Court</option>
              </select>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-900">Experience (Years) <span className="text-red-500">*</span></label>
              <input 
                type="number" 
                name="experience" 
                value={formData.experience} 
                onChange={handleChange} 
                placeholder="e.g. 5" 
                className="w-full p-3 bg-gray-50 border border-gray-200 rounded-lg focus:ring-2 focus:ring-[#052379]/20 outline-none text-gray-900 placeholder:text-gray-500" 
              />
            </div>
            <div className="col-span-1 md:col-span-2 space-y-2">
              <label className="text-sm font-medium text-gray-900">Primary Specialization <span className="text-red-500">*</span></label>
              <select 
                name="specialization" 
                value={formData.specialization} 
                onChange={handleChange} 
                className="w-full p-3 bg-gray-50 border border-gray-200 rounded-lg focus:ring-2 focus:ring-[#052379]/20 outline-none text-gray-900"
              >
                <option value="">Select Specialization</option>
                <option value="criminal">Criminal Law</option>
                <option value="family">Family Law</option>
                <option value="corporate">Corporate Law</option>
                <option value="property">Property/Real Estate</option>
              </select>
            </div>
          </div>
        );
      
      case 2: 
        return (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-900">Email Address <span className="text-red-500">*</span></label>
              <input 
                type="email" 
                name="email" 
                value={formData.email} 
                onChange={handleChange} 
                className="w-full p-3 bg-gray-50 border border-gray-200 rounded-lg outline-none focus:ring-2 focus:ring-[#052379]/20 text-gray-900 placeholder:text-gray-500" 
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-900">Phone Number <span className="text-red-500">*</span></label>
              <input 
                type="tel" 
                name="phone" 
                value={formData.phone} 
                onChange={handleChange} 
                className="w-full p-3 bg-gray-50 border border-gray-200 rounded-lg outline-none focus:ring-2 focus:ring-[#052379]/20 text-gray-900 placeholder:text-gray-500" 
              />
            </div>
            <div className="col-span-1 md:col-span-2 space-y-2">
              <label className="text-sm font-medium text-gray-900">Office Address</label>
              <input 
                type="text" 
                name="officeAddress" 
                value={formData.officeAddress} 
                onChange={handleChange} 
                className="w-full p-3 bg-gray-50 border border-gray-200 rounded-lg outline-none focus:ring-2 focus:ring-[#052379]/20 text-gray-900 placeholder:text-gray-500" 
              />
            </div>
          </div>
        );

      case 3: 
        return (
          <div className="grid grid-cols-1 gap-6">
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-900">Law School / University</label>
              <input 
                type="text" 
                name="lawSchool" 
                value={formData.lawSchool} 
                onChange={handleChange} 
                className="w-full p-3 bg-gray-50 border border-gray-200 rounded-lg outline-none text-gray-900 placeholder:text-gray-500" 
              />
            </div>
            <div className="grid grid-cols-2 gap-6">
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-900">Graduation Year</label>
                <input 
                  type="number" 
                  name="gradYear" 
                  value={formData.gradYear} 
                  onChange={handleChange} 
                  className="w-full p-3 bg-gray-50 border border-gray-200 rounded-lg outline-none text-gray-900 placeholder:text-gray-500" 
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-900">Degree Type</label>
                <select 
                  name="degreeType" 
                  value={formData.degreeType} 
                  onChange={handleChange} 
                  className="w-full p-3 bg-gray-50 border border-gray-200 rounded-lg outline-none text-gray-900"
                >
                  <option value="LLB">LLB</option>
                  <option value="LLM">LLM</option>
                  <option value="BarAtLaw">Bar-at-Law</option>
                </select>
              </div>
            </div>
          </div>
        );

      case 4: 
        return (
          <div className="space-y-6">
            <div className="p-4 bg-blue-50 border border-blue-100 rounded-lg text-sm text-blue-800">
              Please upload clear scans. These documents are required to verify your "Verified Lawyer" badge.
            </div>
            
            <div className="border-2 border-dashed border-gray-300 rounded-xl p-8 text-center hover:border-gray-400 transition-colors cursor-pointer relative">
              <input type="file" name="barLicenseFile" onChange={handleFileChange} className="absolute inset-0 opacity-0 cursor-pointer" accept=".pdf,.jpg,.png" />
              <div className="w-12 h-12 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-3">
                <UploadCloud className="w-6 h-6 text-gray-500" />
              </div>
              <p className="text-sm font-medium text-gray-900">Upload Bar Council License</p>
              <p className="text-xs text-gray-500 mt-1">{formData.barLicenseFile ? formData.barLicenseFile.name : "PDF, JPG or PNG (Max 5MB)"}</p>
            </div>

            <div className="border-2 border-dashed border-gray-300 rounded-xl p-8 text-center hover:border-gray-400 transition-colors cursor-pointer relative">
              <input type="file" name="cnicFile" onChange={handleFileChange} className="absolute inset-0 opacity-0 cursor-pointer" accept=".pdf,.jpg,.png" />
              <div className="w-12 h-12 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-3">
                <UploadCloud className="w-6 h-6 text-gray-500" />
              </div>
              <p className="text-sm font-medium text-gray-900">Upload CNIC Front/Back</p>
              <p className="text-xs text-gray-500 mt-1">{formData.cnicFile ? formData.cnicFile.name : "PDF, JPG or PNG (Max 5MB)"}</p>
            </div>
          </div>
        );

      case 5: 
        return (
          <div className="space-y-6">
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-900">Create Password</label>
              <input 
                type="password" 
                name="password" 
                value={formData.password} 
                onChange={handleChange} 
                className="w-full p-3 bg-gray-50 border border-gray-200 rounded-lg outline-none text-gray-900 placeholder:text-gray-500" 
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-900">Confirm Password</label>
              <input 
                type="password" 
                name="confirmPassword" 
                value={formData.confirmPassword} 
                onChange={handleChange} 
                className="w-full p-3 bg-gray-50 border border-gray-200 rounded-lg outline-none text-gray-900 placeholder:text-gray-500" 
              />
            </div>
          </div>
        );

      case 6: 
        return (
          <div className="space-y-6">
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-900">Short Bio</label>
              <textarea 
                name="bio" 
                rows="4" 
                value={formData.bio} 
                onChange={handleChange} 
                placeholder="Tell clients about your experience..." 
                className="w-full p-3 bg-gray-50 border border-gray-200 rounded-lg outline-none resize-none text-gray-900 placeholder:text-gray-500" 
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-900">Consultation Fee (PKR)</label>
              <input 
                type="number" 
                name="hourlyRate" 
                value={formData.hourlyRate} 
                onChange={handleChange} 
                placeholder="e.g. 5000" 
                className="w-full p-3 bg-gray-50 border border-gray-200 rounded-lg outline-none text-gray-900 placeholder:text-gray-500" 
              />
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div className="w-full min-h-screen bg-white flex flex-col items-center pt-16 pb-20">
      
      {/*  Header */}
      <div className="text-center mb-10 space-y-2">
        <div className="flex justify-center mb-4">
          <div className="w-12 h-12 bg-[#052379] rounded-xl flex items-center justify-center shadow-lg shadow-blue-900/20">
            <Briefcase className="w-6 h-6 text-white" />
          </div>
        </div>
        <h1 className="text-3xl font-medium text-gray-900">Lawyer Registration Portal</h1>
        <p className="text-gray-500">Complete your professional registration to join our legal network</p>
      </div>

      {/*  Main Card */}
      <div className="w-full max-w-4xl bg-white border border-gray-200 rounded-2xl shadow-xl overflow-hidden flex flex-col md:flex-row">
        
       
        <div className="w-full md:w-64 bg-gray-50 border-b md:border-b-0 md:border-r border-gray-200 p-6">
          <div className="space-y-1">
            {steps.map((step) => {
              const isActive = step.id === currentStep;
              const isCompleted = step.id < currentStep;
              
              return (
                <div key={step.id} className="flex items-center gap-3 py-3">
                  <div className={`
                    w-8 h-8 rounded-full flex items-center justify-center text-xs font-medium transition-colors
                    ${isActive ? 'bg-[#052379] text-white ring-4 ring-blue-100' : 
                      isCompleted ? 'bg-green-500 text-white' : 'bg-white border border-gray-300 text-gray-500'}
                  `}>
                    {isCompleted ? <Check className="w-4 h-4" /> : step.id}
                  </div>
                  <div className="hidden md:block">
                    <p className={`text-sm font-medium ${isActive ? 'text-[#052379]' : 'text-gray-500'}`}>
                      {step.title}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="flex-1 p-8 flex flex-col">
        
          <div className="md:hidden mb-6">
            <div className="h-2 w-full bg-gray-100 rounded-full overflow-hidden">
              <div 
                className="h-full bg-[#052379] transition-all duration-300"
                style={{ width: `${(currentStep / steps.length) * 100}%` }}
              />
            </div>
            <p className="text-xs text-gray-500 mt-2 text-right">Step {currentStep} of {steps.length}</p>
          </div>

          <div className="mb-6">
            <h2 className="text-xl font-semibold text-gray-900">{steps[currentStep-1].title} Information</h2>
            <p className="text-sm text-gray-500 mt-1">Please provide accurate details for verification.</p>
          </div>

          <div className="flex-1">
            {renderStepContent()}
          </div>

          {/* Footer Navigation */}
          <div className="flex items-center justify-between mt-10 pt-6 border-t border-gray-100">
            <button
              onClick={handleBack}
              disabled={currentStep === 1}
              className={`flex items-center gap-2 px-6 py-2.5 rounded-lg text-sm font-medium transition-colors
                ${currentStep === 1 
                  ? 'text-gray-300 cursor-not-allowed' 
                  : 'text-gray-700 hover:bg-gray-50 border border-gray-200'}`}
            >
              <ChevronLeft className="w-4 h-4" />
              Back
            </button>

            <button
              onClick={handleNext}
              disabled={loading}
              className="flex items-center gap-2 px-8 py-2.5 bg-[#052379] text-white rounded-lg text-sm font-medium hover:bg-[#041d5c] transition-colors shadow-sm disabled:bg-gray-400"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Processing...
                </>
              ) : (
                <>
                  {currentStep === steps.length ? 'Submit Application' : 'Next'}
                  {currentStep !== steps.length && <ChevronRight className="w-4 h-4" />}
                </>
              )}
            </button>
          </div>

        </div>
      </div>
    </div>
  );
}