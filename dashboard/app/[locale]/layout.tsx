import type { Metadata, Viewport } from "next";
import { NextIntlClientProvider } from "next-intl";
import { getMessages, setRequestLocale } from "next-intl/server";
import { notFound } from "next/navigation";
import { hasLocale } from "next-intl";
import ClientLayout from "./client-layout";
import "@aws-amplify/ui-react/styles.css";
import { SidebarProvider } from "@/app/contexts/SidebarContext";
import { BrandProvider } from "@/app/contexts/BrandContext";
import { BrandedTitle } from "@/components/BrandedTitle";
import { LocaleHtmlLang } from "@/components/LocaleHtmlLang";
import { routing } from "@/i18n/routing";

export const metadata: Metadata = {
  title: "AI Agent Incubator",
  description:
    "Plexus gives your team a reliable way to evaluate, deploy, and improve AI agents through continuous learning and human feedback loops.",
  metadataBase: new URL(
    process.env.NEXT_PUBLIC_SITE_URL || "https://plexus.anth.us",
  ),
  openGraph: {
    title: "AI Agent Incubator",
    description:
      "Plexus gives your team a reliable way to evaluate, deploy, and improve AI agents through continuous learning and human feedback loops.",
    url: "https://plexus.anth.us",
    siteName: "Plexus",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "Plexus - AI Agent Incubator",
      },
    ],
    locale: "en_US",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "AI Agent Incubator",
    description:
      "Plexus gives your team a reliable way to evaluate, deploy, and improve AI agents through continuous learning and human feedback loops.",
    creator: "@Anthus_AI",
    images: ["/og-image.png"],
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
};

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

type Props = {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
};

export default async function LocaleLayout({ children, params }: Props) {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) {
    notFound();
  }
  setRequestLocale(locale);
  const messages = await getMessages();

  return (
    <NextIntlClientProvider messages={messages}>
      <LocaleHtmlLang />
      <BrandProvider>
        <BrandedTitle />
        <SidebarProvider>
          <ClientLayout>{children}</ClientLayout>
        </SidebarProvider>
      </BrandProvider>
    </NextIntlClientProvider>
  );
}
