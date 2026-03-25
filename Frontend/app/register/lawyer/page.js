"use client";

import { useState, useEffect } from 'react';
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
import { useRouter } from "next/navigation";
import { registerLawyer } from "../../lib/api";
import { useAuthStore } from "../../lib/authStore";
import { useLanguage } from "../../lib/LanguageContext";

export default function LawyerRegistration() {
  const router = useRouter();
  const { isLoggedIn, user } = useAuthStore();
  const { t } = useLanguage();

  useEffect(() => {
    if (isLoggedIn && user) {
      router.replace(user.role === 'lawyer' ? '/dashboard/lawyer' : '/dashboard/user');
    }
  }, [isLoggedIn, user, router]);

  const [currentStep, setCurrentStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

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
    { id: 1, titleKey: 'registerLawyer.steps.professional', icon: <Briefcase className="w-5 h-5" /> },
    { id: 2, titleKey: 'registerLawyer.steps.contact', icon: <Phone className="w-5 h-5" /> },
    { id: 3, titleKey: 'registerLawyer.steps.education', icon: <GraduationCap className="w-5 h-5" /> },
    { id: 4, titleKey: 'registerLawyer.steps.documents', icon: <FileText className="w-5 h-5" /> },
    { id: 5, titleKey: 'registerLawyer.steps.security', icon: <ShieldCheck className="w-5 h-5" /> },
    { id: 6, titleKey: 'registerLawyer.steps.additional', icon: <User className="w-5 h-5" /> },
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
    if (formData.password !== formData.confirmPassword) {
      setError(t("registerLawyer.errPasswordMatch"));
      setCurrentStep(5);
      return;
    }
    if (formData.password.length < 6) {
      setError(t("registerLawyer.errPasswordLength"));
      setCurrentStep(5);
      return;
    }
    setLoading(true);
    setError('');
    try {
      await registerLawyer(formData);
      router.push('/login');
    } catch (err) {
      setError(err.message || t("registerLawyer.errRegistrationFailed"));
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
              <label className="text-sm font-medium text-gray-900">{t("registerLawyer.fullLegalName")} <span className="text-red-500">*</span></label>
              <input type="text" name="fullName" value={formData.fullName} onChange={handleChange}
                placeholder="Advocate Name"
                className="w-full p-3 bg-gray-50 border border-gray-200 rounded-lg focus:ring-2 focus:ring-[#052379]/20 outline-none text-gray-900 placeholder:text-gray-500" />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-900">{t("registerLawyer.barAssocId")} <span className="text-red-500">*</span></label>
              <input type="text" name="barNumber" value={formData.barNumber} onChange={handleChange}
                placeholder="e.g., PK-BAR-2023"
                className="w-full p-3 bg-gray-50 border border-gray-200 rounded-lg focus:ring-2 focus:ring-[#052379]/20 outline-none text-gray-900 placeholder:text-gray-500" />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-900">{t("registerLawyer.jurisdiction")} <span className="text-red-500">*</span></label>
              <select name="jurisdiction" value={formData.jurisdiction} onChange={handleChange}
                className="w-full p-3 bg-gray-50 border border-gray-200 rounded-lg focus:ring-2 focus:ring-[#052379]/20 outline-none text-gray-900">
                <option value="">{t("registerLawyer.selectJurisdiction")}</option>
                <option value="lahore">Lahore High Court</option>
                <option value="karachi">Sindh High Court</option>
                <option value="islamabad">Islamabad High Court</option>
              </select>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-900">{t("registerLawyer.experienceYears")} <span className="text-red-500">*</span></label>
              <input type="number" name="experience" value={formData.experience} onChange={handleChange}
                placeholder="e.g. 5"
                className="w-full p-3 bg-gray-50 border border-gray-200 rounded-lg focus:ring-2 focus:ring-[#052379]/20 outline-none text-gray-900 placeholder:text-gray-500" />
            </div>
            <div className="col-span-1 md:col-span-2 space-y-2">
              <label className="text-sm font-medium text-gray-900">{t("registerLawyer.primarySpec")} <span className="text-red-500">*</span></label>
              <select name="specialization" value={formData.specialization} onChange={handleChange}
                className="w-full p-3 bg-gray-50 border border-gray-200 rounded-lg focus:ring-2 focus:ring-[#052379]/20 outline-none text-gray-900">
                <option value="">{t("registerLawyer.selectSpec")}</option>
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
              <label className="text-sm font-medium text-gray-900">{t("registerLawyer.emailLabel")} <span className="text-red-500">*</span></label>
              <input type="email" name="email" value={formData.email} onChange={handleChange}
                className="w-full p-3 bg-gray-50 border border-gray-200 rounded-lg outline-none focus:ring-2 focus:ring-[#052379]/20 text-gray-900 placeholder:text-gray-500" />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-900">{t("registerLawyer.phoneLabel")} <span className="text-red-500">*</span></label>
              <input type="tel" name="phone" value={formData.phone} onChange={handleChange}
                className="w-full p-3 bg-gray-50 border border-gray-200 rounded-lg outline-none focus:ring-2 focus:ring-[#052379]/20 text-gray-900 placeholder:text-gray-500" />
            </div>
            <div className="col-span-1 md:col-span-2 space-y-2">
              <label className="text-sm font-medium text-gray-900">{t("registerLawyer.officeAddress")}</label>
              <input type="text" name="officeAddress" value={formData.officeAddress} onChange={handleChange}
                className="w-full p-3 bg-gray-50 border border-gray-200 rounded-lg outline-none focus:ring-2 focus:ring-[#052379]/20 text-gray-900 placeholder:text-gray-500" />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-900">{t("registerLawyer.city")}</label>
              <input type="text" name="city" value={formData.city} onChange={handleChange}
                placeholder="e.g. Lahore"
                className="w-full p-3 bg-gray-50 border border-gray-200 rounded-lg outline-none focus:ring-2 focus:ring-[#052379]/20 text-gray-900 placeholder:text-gray-500" />
            </div>
          </div>
        );

      case 3:
        return (
          <div className="grid grid-cols-1 gap-6">
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-900">{t("registerLawyer.lawSchool")}</label>
              <input type="text" name="lawSchool" value={formData.lawSchool} onChange={handleChange}
                className="w-full p-3 bg-gray-50 border border-gray-200 rounded-lg outline-none text-gray-900 placeholder:text-gray-500" />
            </div>
            <div className="grid grid-cols-2 gap-6">
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-900">{t("registerLawyer.gradYear")}</label>
                <input type="number" name="gradYear" value={formData.gradYear} onChange={handleChange}
                  className="w-full p-3 bg-gray-50 border border-gray-200 rounded-lg outline-none text-gray-900 placeholder:text-gray-500" />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-900">{t("registerLawyer.degreeType")}</label>
                <select name="degreeType" value={formData.degreeType} onChange={handleChange}
                  className="w-full p-3 bg-gray-50 border border-gray-200 rounded-lg outline-none text-gray-900">
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
              {t("registerLawyer.uploadNote")}
            </div>

            <div className="border-2 border-dashed border-gray-300 rounded-xl p-8 text-center hover:border-gray-400 transition-colors cursor-pointer relative">
              <input type="file" name="barLicenseFile" onChange={handleFileChange} className="absolute inset-0 opacity-0 cursor-pointer" accept=".pdf,.jpg,.png" />
              <div className="w-12 h-12 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-3">
                <UploadCloud className="w-6 h-6 text-gray-500" />
              </div>
              <p className="text-sm font-medium text-gray-900">{t("registerLawyer.uploadBarLicense")}</p>
              <p className="text-xs text-gray-500 mt-1">{formData.barLicenseFile ? formData.barLicenseFile.name : t("registerLawyer.fileSizeNote")}</p>
            </div>

            <div className="border-2 border-dashed border-gray-300 rounded-xl p-8 text-center hover:border-gray-400 transition-colors cursor-pointer relative">
              <input type="file" name="cnicFile" onChange={handleFileChange} className="absolute inset-0 opacity-0 cursor-pointer" accept=".pdf,.jpg,.png" />
              <div className="w-12 h-12 bg-gray-100 rounded-full flex items-center justify-center mx-auto mb-3">
                <UploadCloud className="w-6 h-6 text-gray-500" />
              </div>
              <p className="text-sm font-medium text-gray-900">{t("registerLawyer.uploadCnic")}</p>
              <p className="text-xs text-gray-500 mt-1">{formData.cnicFile ? formData.cnicFile.name : t("registerLawyer.fileSizeNote")}</p>
            </div>
          </div>
        );

      case 5:
        return (
          <div className="space-y-6">
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-900">{t("registerLawyer.createPassword")}</label>
              <input type="password" name="password" value={formData.password} onChange={handleChange}
                className="w-full p-3 bg-gray-50 border border-gray-200 rounded-lg outline-none text-gray-900 placeholder:text-gray-500" />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-900">{t("registerLawyer.confirmPassword")}</label>
              <input type="password" name="confirmPassword" value={formData.confirmPassword} onChange={handleChange}
                className="w-full p-3 bg-gray-50 border border-gray-200 rounded-lg outline-none text-gray-900 placeholder:text-gray-500" />
            </div>
          </div>
        );

      case 6:
        return (
          <div className="space-y-6">
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-900">{t("registerLawyer.shortBio")}</label>
              <textarea name="bio" rows="4" value={formData.bio} onChange={handleChange}
                placeholder={t("registerLawyer.bioPlaceholder")}
                className="w-full p-3 bg-gray-50 border border-gray-200 rounded-lg outline-none resize-none text-gray-900 placeholder:text-gray-500" />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-900">{t("registerLawyer.consultationFee")}</label>
              <input type="number" name="hourlyRate" value={formData.hourlyRate} onChange={handleChange}
                placeholder="e.g. 5000"
                className="w-full p-3 bg-gray-50 border border-gray-200 rounded-lg outline-none text-gray-900 placeholder:text-gray-500" />
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div className="w-full min-h-screen bg-white flex flex-col items-center pt-16 pb-20">

      <div className="text-center mb-10 space-y-2">
        <div className="flex justify-center mb-4">
          <div className="w-12 h-12 bg-[#052379] rounded-xl flex items-center justify-center shadow-lg shadow-blue-900/20">
            <Briefcase className="w-6 h-6 text-white" />
          </div>
        </div>
        <h1 className="text-3xl font-medium text-gray-900">{t("registerLawyer.heading")}</h1>
        <p className="text-gray-500">{t("registerLawyer.subheading")}</p>
      </div>

      {error && (
        <div className="w-full max-w-4xl mb-4 px-4 py-3 bg-red-50 border border-red-200 text-red-700 rounded-xl text-sm">
          {error}
        </div>
      )}

      <div className="w-full max-w-4xl bg-white border border-gray-200 rounded-2xl shadow-xl overflow-hidden flex flex-col md:flex-row">

        <div className="w-full md:w-64 bg-gray-50 border-b md:border-b-0 md:border-e border-gray-200 p-6">
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
                      {t(step.titleKey)}
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
            <p className="text-xs text-gray-500 mt-2 text-end">
              {t("registerLawyer.stepOf", { n: currentStep, m: steps.length })}
            </p>
          </div>

          <div className="mb-6">
            <h2 className="text-xl font-semibold text-gray-900">
              {t(steps[currentStep - 1].titleKey)} {t("registerLawyer.information")}
            </h2>
            <p className="text-sm text-gray-500 mt-1">{t("registerLawyer.provideDetails")}</p>
          </div>

          <div className="flex-1">
            {renderStepContent()}
          </div>

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
              {t("registerLawyer.back")}
            </button>

            <button
              onClick={handleNext}
              disabled={loading}
              className="flex items-center gap-2 px-8 py-2.5 bg-[#052379] text-white rounded-lg text-sm font-medium hover:bg-[#041d5c] transition-colors shadow-sm disabled:bg-gray-400"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  {t("registerLawyer.processing")}
                </>
              ) : (
                <>
                  {currentStep === steps.length ? t("registerLawyer.submitApplication") : t("registerLawyer.next")}
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
