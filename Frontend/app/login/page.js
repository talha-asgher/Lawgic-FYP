"use client";

import { useState, useEffect } from 'react';
import { Mail, Lock, Eye, EyeOff, Scale, Loader2, AlertCircle } from 'lucide-react';
import { useRouter } from "next/navigation";
import { loginUser } from "@/lib/api";
import { useAuthStore } from "../lib/authStore";
import { useLanguage } from "../lib/LanguageContext";

export default function LoginPage() {
  const router = useRouter();
  const loginStore = useAuthStore((state) => state.login);
  const { isLoggedIn, user } = useAuthStore();
  const { lang, toggleLanguage, t } = useLanguage();

  const [formData, setFormData] = useState({ email: '', password: '' });
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (isLoggedIn && user) {
      router.replace(user.role === 'lawyer' ? '/dashboard/lawyer' : '/dashboard/user');
    }
  }, [isLoggedIn, user, router]);

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');
    try {
      const data = await loginUser(formData.email, formData.password);
      loginStore(data.user, data.access_token);
      router.push(data.user.role === 'lawyer' ? '/dashboard/lawyer' : '/dashboard/user');
    } catch (err) {
      setError(err.message || t("login.loginFailed"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-white flex flex-col">
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

      <main className="flex-1 relative overflow-hidden" style={{ backgroundImage: "url('/scale.jpeg')", backgroundSize: 'cover', backgroundPosition: 'center' }}>
        <div className="absolute inset-0 bg-black/10" />
        <div className="relative flex items-center justify-center min-h-full py-16">
          <div className="w-full max-w-md mx-4 bg-white/95 backdrop-blur-sm rounded-2xl shadow-2xl p-6">
            <div className="flex justify-center mb-6">
              <div className="w-14 h-14 bg-[#052379] rounded-xl flex items-center justify-center">
                <Scale className="w-8 h-8 text-white" />
              </div>
            </div>
            <h1 className="text-3xl font-normal text-center text-black mb-4">Lawgic</h1>
            <p className="text-center text-[#4A5568] text-base mb-8">{t("login.subtitle")}</p>

            {error && (
              <div className="mb-6 p-3 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2 text-red-700 text-sm">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                <span>{error}</span>
              </div>
            )}

            <form onSubmit={handleLogin} className="space-y-5">
              <div>
                <label className="block text-sm text-black mb-2">{t("login.emailLabel")}</label>
                <div className="relative">
                  <Mail className={`absolute ${lang === 'ur' ? 'end-3' : 'start-3'} top-1/2 -translate-y-1/2 w-5 h-5 text-[#9CA3AF]`} />
                  <input type="email" required value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    placeholder={t("login.emailPlaceholder")}
                    className={`w-full ${lang === 'ur' ? 'pe-10 ps-3' : 'ps-10 pe-3'} py-2 bg-white text-black placeholder:text-[#9CA3AF] rounded-lg border border-[#D1D5DB] focus:border-[#4EB332] focus:outline-none text-sm shadow-sm`} />
                </div>
              </div>
              <div>
                <label className="block text-sm text-black mb-2">{t("login.passwordLabel")}</label>
                <div className="relative">
                  <Lock className={`absolute ${lang === 'ur' ? 'end-3' : 'start-3'} top-1/2 -translate-y-1/2 w-5 h-5 text-[#9CA3AF]`} />
                  <input type={showPassword ? "text" : "password"} required value={formData.password}
                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                    placeholder={t("login.passwordPlaceholder")}
                    className={`w-full ${lang === 'ur' ? 'pe-10 ps-10' : 'ps-10 pe-10'} py-2 bg-white text-black placeholder:text-[#9CA3AF] rounded-lg border border-[#D1D5DB] focus:border-[#4EB332] focus:outline-none text-sm shadow-sm`} />
                  <button type="button" onClick={() => setShowPassword(!showPassword)}
                    className={`absolute ${lang === 'ur' ? 'start-3' : 'end-3'} top-1/2 -translate-y-1/2 text-[#9CA3AF] hover:text-gray-700 focus:outline-none`}>
                    {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                  </button>
                </div>
              </div>
              <button type="submit" disabled={loading}
                className="w-full py-3 bg-[#052379] hover:bg-[#041d5e] disabled:bg-[#052379]/70 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition-colors shadow-md flex items-center justify-center gap-2">
                {loading ? <><Loader2 className="w-4 h-4 animate-spin" />{t("login.signingIn")}</> : t("login.signIn")}
              </button>
            </form>

            <div className="mt-6 pt-6 border-t border-[#E7ECF3]">
              <p className="text-center text-sm text-[#64748B] mb-3">{t("login.noAccount")}</p>
              <div className="flex gap-2">
                <button onClick={() => router.push('/register/user')}
                  className="flex-1 px-3 py-2 text-sm font-medium text-[#0E1726] bg-white hover:bg-[#F0F2F5] rounded-lg border border-[#E7ECF3] transition-all duration-200 shadow-sm hover:shadow-md">
                  {t("login.registerAsUser")}
                </button>
                <button onClick={() => router.push('/register/lawyer')}
                  className="flex-1 px-3 py-2 text-sm font-medium text-[#0E1726] bg-white hover:bg-[#F0F2F5] rounded-lg border border-[#E7ECF3] transition-all duration-200 shadow-sm hover:shadow-md">
                  {t("login.registerAsLawyer")}
                </button>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
