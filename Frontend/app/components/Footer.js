"use client";

import { Scale } from "lucide-react";
import { useLanguage } from "../lib/LanguageContext";

export default function Footer() {
  const { t } = useLanguage();

  return (
    <footer className="bg-gray-50 border-t border-gray-200">
      <div className="max-w-7xl mx-auto px-6 lg:px-12 py-12">
        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-8 mb-8">
          <div className="lg:col-span-2">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 bg-[#052379] rounded-xl flex items-center justify-center">
                <Scale className="w-6 h-6 text-white" />
              </div>
              <span className="text-xl font-semibold text-gray-900">Lawgic</span>
            </div>
            <p className="text-gray-600 max-w-md">
              {t("footer.tagline")}
            </p>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 mb-4">{t("footer.aboutHeading")}</h4>
            <ul className="space-y-2">
              <li><a href="#" className="text-gray-600 hover:text-gray-900">{t("footer.aboutLink")}</a></li>
              <li><a href="#" className="text-gray-600 hover:text-gray-900">{t("footer.contactUs")}</a></li>
            </ul>
          </div>

          <div>
            <h4 className="font-medium text-gray-900 mb-4">{t("footer.legalHeading")}</h4>
            <ul className="space-y-2">
              <li><a href="#" className="text-gray-600 hover:text-gray-900">{t("footer.terms")}</a></li>
              <li><a href="#" className="text-gray-600 hover:text-gray-900">{t("footer.privacy")}</a></li>
            </ul>
          </div>
        </div>

        <div className="pt-8 border-t border-gray-200">
          <p className="text-sm text-gray-600 text-center">
            {t("footer.copyright")}
          </p>
        </div>
      </div>
    </footer>
  );
}
