"use client";

import { useState, useEffect } from 'react';
import { Mail, Lock, Eye, EyeOff, User, Phone, Scale, Loader2, AlertCircle } from 'lucide-react';
import { useRouter } from "next/navigation";
import { registerUser } from "@/lib/api";
import { useAuthStore } from "../../lib/authStore";
import { useLanguage } from "../../lib/LanguageContext";

export default function LawgicRegister() {
  const router = useRouter();
  const { isLoggedIn, user, authInitialized } = useAuthStore();
  const { lang, toggleLanguage, t } = useLanguage();

  useEffect(() => {
    if (!authInitialized) return;
    if (isLoggedIn && user) {
      router.replace(user.role === 'lawyer' ? '/dashboard/lawyer' : '/dashboard/user');
    }
  }, [authInitialized, isLoggedIn, user, router]);

  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [formData, setFormData] = useState({
    name: '', email: '', password: '', confirmPassword: '', phone: ''
  });

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
    if (error) setError('');
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    if (formData.password !== formData.confirmPassword) {
      setError(t("registerUser.errPasswordMatch"));
      return;
    }
    if (formData.password.length < 6) {
      setError(t("registerUser.errPasswordLength"));
      return;
    }
    if (!/\d/.test(formData.password)) {
      setError(t("registerUser.errPasswordNumber"));
      return;
    }
    if (formData.phone.length < 8) {
      setError(t("registerUser.errPhoneLength"));
      return;
    }
    if (formData.phone.length > 15) {
      setError(t("registerUser.errPhoneLength"));
      return;
    }
    if (
          !formData.email.includes("@") ||
          !formData.email.includes(".com") ||
          formData.email.startsWith("@") ||
          formData.email.endsWith("@") ||
          formData.email.indexOf("@") === formData.email.length - 1 ||
          formData.email.split("@")[0].length === 0 ||
          formData.email.split("@")[1].split(".com")[0].length === 0
        ) {
          setError(t("registerUser.errEmailInvalid"));
          return;
        }
    setLoading(true);
    setError('');
    try {
      await registerUser(formData);
      router.push('/login');
    } catch (err) {
      setError(err.message || t("registerUser.errRegistrationFailed"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-white">
      <header className="border-b border-black px-12 py-6">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-[#052379] rounded-xl flex items-center justify-center">
              <Scale className="w-6 h-6 text-white" />
            </div>
            <span className="text-xl font-semibold text-[#0E1726]">Lawgic</span>
          </div>
          <div className="flex items-center gap-4">
            <button
              onClick={toggleLanguage}
              className="px-4 py-2 text-sm font-medium text-[#0E1726] bg-white/90 hover:bg-gray-100 rounded-lg border border-[#7E7E7E] transition-colors"
            >
              {lang === "en" ? t("nav.langToggle") : t("nav.langToggleUrdu")}
            </button>
          </div>
        </div>
      </header>

      <main className="flex-1 relative flex justify-center">
        <div className="absolute inset-0 bg-cover bg-center" style={{ backgroundImage: "url('/scale.jpeg')" }} />
        <div className="absolute inset-0 bg-black/10" />

        <div className="relative z-10 w-full max-w-md mx-4 my-12 bg-white/95 backdrop-blur-sm rounded-2xl shadow-2xl p-6">
          <div className="text-center mb-8">
            <div className="flex justify-center mb-4">
              <div className="w-14 h-14 bg-[#052379] rounded-lg flex items-center justify-center">
                <Scale className="w-8 h-8 text-white" />
              </div>
            </div>
            <h1 className="text-3xl font-normal text-black mb-3">Lawgic</h1>
            <p className="text-base text-[#717182]">{t("registerUser.subtitle")}</p>
          </div>

          {error && (
            <div className="mb-6 p-3 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2 text-red-700 text-sm">
              <AlertCircle className="w-4 h-4" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleRegister} className="space-y-5">
            <div className="space-y-2">
              <label className="text-sm text-black">{t("registerUser.nameLabel")}</label>
              <div className="relative">
                <User className={`absolute ${lang === 'ur' ? 'end-3' : 'start-3'} top-1/2 -translate-y-1/2 w-5 h-5 text-[#9CA3AF]`} />
                <input type="text" name="name" required value={formData.name} onChange={handleChange}
                  placeholder={t("registerUser.namePlaceholder")}
                  className={`w-full h-9 ${lang === 'ur' ? 'pe-10 ps-3' : 'ps-10 pe-3'} text-sm text-black bg-white border border-[#D1D5DB] rounded-lg outline-none focus:border-[#4EB332]`} />
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm text-black">{t("registerUser.emailLabel")}</label>
              <div className="relative">
                <Mail className={`absolute ${lang === 'ur' ? 'end-3' : 'start-3'} top-1/2 -translate-y-1/2 w-5 h-5 text-[#9CA3AF]`} />
                <input type="email" name="email" required value={formData.email} onChange={handleChange}
                  placeholder={t("registerUser.emailPlaceholder")}
                  className={`w-full h-9 ${lang === 'ur' ? 'pe-10 ps-3' : 'ps-10 pe-3'} text-sm text-black bg-white border border-[#D1D5DB] rounded-lg outline-none focus:border-[#4EB332]`} />
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm text-black">{t("registerUser.passwordLabel")}</label>
              <div className="relative">
                <Lock className={`absolute ${lang === 'ur' ? 'end-10' : 'start-3'} top-1/2 -translate-y-1/2 w-5 h-5 text-[#9CA3AF]`} />
                <input type={showPassword ? "text" : "password"} name="password" required
                  value={formData.password} onChange={handleChange} placeholder={t("registerUser.passwordPlaceholder")}
                  className={`w-full h-9 ${lang === 'ur' ? 'pe-10 ps-10' : 'ps-10 pe-10'} text-sm text-black bg-white border border-[#D1D5DB] rounded-lg outline-none focus:border-[#4EB332]`} />
                <button type="button" onClick={() => setShowPassword(!showPassword)}
                  className={`absolute ${lang === 'ur' ? 'start-3' : 'end-3'} top-1/2 -translate-y-1/2 text-[#9CA3AF] hover:text-gray-600 focus:outline-none`}>
                  {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm text-black">{t("registerUser.confirmPasswordLabel")}</label>
              <div className="relative">
                <Lock className={`absolute ${lang === 'ur' ? 'end-10' : 'start-3'} top-1/2 -translate-y-1/2 w-5 h-5 text-[#9CA3AF]`} />
                <input type={showConfirmPassword ? "text" : "password"} name="confirmPassword" required
                  value={formData.confirmPassword} onChange={handleChange} placeholder={t("registerUser.confirmPasswordPlaceholder")}
                  className={`w-full h-9 ${lang === 'ur' ? 'pe-10 ps-10' : 'ps-10 pe-10'} text-sm text-black bg-white border border-[#D1D5DB] rounded-lg outline-none focus:border-[#4EB332]`} />
                <button type="button" onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  className={`absolute ${lang === 'ur' ? 'start-3' : 'end-3'} top-1/2 -translate-y-1/2 text-[#9CA3AF] hover:text-gray-600 focus:outline-none`}>
                  {showConfirmPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm text-black">{t("registerUser.contactLabel")}</label>
              <div className="relative">
                <Phone className={`absolute ${lang === 'ur' ? 'end-3' : 'start-3'} top-1/2 -translate-y-1/2 w-5 h-5 text-[#9CA3AF]`} />
                <input type="tel" name="phone" value={formData.phone} onChange={handleChange}
                  placeholder="+923001234567"
                  className={`w-full h-9 ${lang === 'ur' ? 'pe-10 ps-3' : 'ps-10 pe-3'} text-sm text-black bg-white border border-[#D1D5DB] rounded-lg outline-none focus:border-[#4EB332]`} />
              </div>
            </div>

            <button type="submit" disabled={loading}
              className="w-full py-3 text-sm font-medium text-white bg-[#052379] rounded-lg hover:bg-[#041d5e] transition-colors disabled:bg-[#052379]/70 disabled:cursor-not-allowed flex items-center justify-center gap-2">
              {loading ? <><Loader2 className="w-4 h-4 animate-spin" />{t("registerUser.creatingAccount")}</> : t("registerUser.register")}
            </button>

            <p className="text-center text-sm text-black mt-2">
              {t("registerUser.haveAccount")}{" "}
              <span onClick={() => router.push("/login")}
                className="text-[#1A2B3C] hover:underline cursor-pointer">{t("registerUser.login")}</span>
            </p>
          </form>

          <div className="mt-6 pt-6 border-t border-[#E7ECF3]">
            <p className="text-center text-sm text-[#64748B] mb-3">{t("registerUser.orRegisterAs")}</p>
            <div className="flex gap-2">
              <button onClick={() => router.push("/register/lawyer")}
                className="flex-1 px-3 py-2 text-sm font-medium text-[#0E1726] bg-white hover:bg-[#F0F2F5] rounded-lg border border-[#E7ECF3] transition-all duration-200 shadow-sm hover:shadow-md">
                {t("registerUser.lawyer")}
              </button>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
