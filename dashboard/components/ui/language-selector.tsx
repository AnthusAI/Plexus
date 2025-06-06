"use client";

import * as React from "react";
import { useRouter, usePathname } from "next/navigation";
import { useLocale, useTranslations } from "@/app/contexts/TranslationContext";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { locales } from "@/i18n";

interface LanguageSelectorProps {
  variant?: "compact" | "full";
}

const languageNames = {
  en: "English",
  es: "Español",
} as const;

export function LanguageSelector({ variant = "full" }: LanguageSelectorProps) {
  const t = useTranslations("languages");
  const locale = useLocale();
  const router = useRouter();
  const pathname = usePathname();

  const handleLanguageChange = (newLocale: string) => {
    // Remove the current locale from the pathname
    const pathWithoutLocale = pathname.replace(`/${locale}`, "");
    // Navigate to the new locale
    router.push(`/${newLocale}${pathWithoutLocale}`);
  };

  if (variant === "compact") {
    return (
      <Select value={locale} onValueChange={handleLanguageChange}>
        <SelectTrigger className="w-[100px]">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {locales.map((loc) => (
            <SelectItem key={loc} value={loc}>
              {languageNames[loc]}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    );
  }

  return (
    <div className="space-y-2">
      <label className="text-sm font-medium">
        {t ? t("language") : "Language"}
      </label>
      <Select value={locale} onValueChange={handleLanguageChange}>
        <SelectTrigger>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {locales.map((loc) => (
            <SelectItem key={loc} value={loc}>
              {languageNames[loc]}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}