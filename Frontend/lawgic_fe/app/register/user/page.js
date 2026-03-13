"use client";

import { useState, useEffect } from 'react';
import { Mail, Lock, Eye, EyeOff, User, Phone, Scale, Loader2, AlertCircle } from 'lucide-react';
import { registerUser, isLoggedIn, getUser } from '@/lib/api';

export default function LawgicRegister() {
  useEffect(() => {
    if (isLoggedIn()) {
      const u = getUser();
      window.location.replace(u?.role === 'lawyer' ? '/dashboard/lawyer' : '/dashboard/user');
    }
  }, []);

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
      setError("Passwords do not match.");
      return;
    }
    if (formData.password.length < 6) {
      setError("Password must be at least 6 characters.");
      return;
    }
    if (!/\d/.test(formData.password)) {
      setError("Password must contain at least one number.");
      return;
    }
    setLoading(true);
    setError('');
    try {
      await registerUser(formData.name, formData.email, formData.password, formData.phone, 'client');
      window.location.href = '/login';
    } catch (err) {
      setError(err.message || "Registration failed. Please try again.");
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
            <button className="px-4 py-2 text-sm font-medium text-[#0E1726] bg-white/90 hover:bg-gray-100 rounded-lg border border-[#7E7E7E] transition-colors">
              EN &#8596; اردو
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
            <p className="text-base text-[#717182]">Fill in the details below to register your account</p>
          </div>

          {error && (
            <div className="mb-6 p-3 bg-red-50 border border-red-200 rounded-lg flex items-center gap-2 text-red-700 text-sm">
              <AlertCircle className="w-4 h-4" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleRegister} className="space-y-5">
            <div className="space-y-2">
              <label className="text-sm text-black">Name</label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-[#9CA3AF]" />
                <input type="text" name="name" required value={formData.name} onChange={handleChange}
                  placeholder="Full Name"
                  className="w-full h-9 pl-10 pr-3 text-sm text-black bg-white border border-[#D1D5DB] rounded-lg outline-none focus:border-[#4EB332]" />
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm text-black">Email Address</label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-[#9CA3AF]" />
                <input type="email" name="email" required value={formData.email} onChange={handleChange}
                  placeholder="you@example.com"
                  className="w-full h-9 pl-10 pr-3 text-sm text-black bg-white border border-[#D1D5DB] rounded-lg outline-none focus:border-[#4EB332]" />
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm text-black">Password</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-[#9CA3AF]" />
                <input type={showPassword ? "text" : "password"} name="password" required
                  value={formData.password} onChange={handleChange} placeholder="Enter your password"
                  className="w-full h-9 pl-10 pr-10 text-sm text-black bg-white border border-[#D1D5DB] rounded-lg outline-none focus:border-[#4EB332]" />
                <button type="button" onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[#9CA3AF] hover:text-gray-600 focus:outline-none">
                  {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm text-black">Confirm Password</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-[#9CA3AF]" />
                <input type={showConfirmPassword ? "text" : "password"} name="confirmPassword" required
                  value={formData.confirmPassword} onChange={handleChange} placeholder="Confirm password"
                  className="w-full h-9 pl-10 pr-10 text-sm text-black bg-white border border-[#D1D5DB] rounded-lg outline-none focus:border-[#4EB332]" />
                <button type="button" onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[#9CA3AF] hover:text-gray-600 focus:outline-none">
                  {showConfirmPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                </button>
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm text-black">Contact Number</label>
              <div className="relative">
                <Phone className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-[#9CA3AF]" />
                <input type="tel" name="phone" value={formData.phone} onChange={handleChange}
                  placeholder="+923001234567"
                  className="w-full h-9 pl-10 pr-3 text-sm text-black bg-white border border-[#D1D5DB] rounded-lg outline-none focus:border-[#4EB332]" />
              </div>
            </div>

            <button type="submit" disabled={loading}
              className="w-full py-3 text-sm font-medium text-white bg-[#052379] rounded-lg hover:bg-[#041d5e] transition-colors disabled:bg-[#052379]/70 disabled:cursor-not-allowed flex items-center justify-center gap-2">
              {loading ? <><Loader2 className="w-4 h-4 animate-spin" />Creating Account...</> : "Register"}
            </button>

            <p className="text-center text-sm text-black mt-2">
              Already have an account?{" "}
              <span onClick={() => { window.location.href = "/login"; }}
                className="text-[#1A2B3C] hover:underline cursor-pointer">Login</span>
            </p>
          </form>

          <div className="mt-6 pt-6 border-t border-[#E7ECF3]">
            <p className="text-center text-sm text-[#64748B] mb-3">Or register as:</p>
            <div className="flex gap-2">
              <button onClick={() => { window.location.href = "/register/lawyer"; }}
                className="flex-1 px-3 py-2 text-sm font-medium text-[#0E1726] bg-white hover:bg-[#F0F2F5] rounded-lg border border-[#E7ECF3] transition-all duration-200 shadow-sm hover:shadow-md">
                Lawyer
              </button>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
