"use client";

import { createContext, useContext, useState, useEffect, useCallback } from "react";
import { en, ur } from "./translations";

const LanguageContext = createContext(null);

const STORAGE_KEY = "lawgic_lang";

function getNestedValue(obj, path) {
  return path.split(".").reduce((acc, key) => acc?.[key], obj);
}

export function LanguageProvider({ children }) {
  const [lang, setLang] = useState("en");

  useEffect(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "ur" || saved === "en") {
      setLang(saved);
    }
  }, []);

  useEffect(() => {
    document.documentElement.dir = lang === "ur" ? "rtl" : "ltr";
    document.documentElement.lang = lang === "ur" ? "ur" : "en";
  }, [lang]);

  const toggleLanguage = useCallback(() => {
    setLang((prev) => {
      const next = prev === "en" ? "ur" : "en";
      localStorage.setItem(STORAGE_KEY, next);
      return next;
    });
  }, []);

  const t = useCallback(
    (key, vars = {}) => {
      const dict = lang === "ur" ? ur : en;
      let str = getNestedValue(dict, key);
      if (str === undefined || str === null) return key;
      if (typeof str !== "string") return str;
      Object.entries(vars).forEach(([k, v]) => {
        str = str.replace(new RegExp(`\\{${k}\\}`, "g"), v);
      });
      return str;
    },
    [lang]
  );

  return (
    <LanguageContext.Provider value={{ lang, toggleLanguage, t }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  const ctx = useContext(LanguageContext);
  if (!ctx) throw new Error("useLanguage must be used inside LanguageProvider");
  return ctx;
}
