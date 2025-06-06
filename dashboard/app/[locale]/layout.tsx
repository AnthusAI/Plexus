import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { Jersey_20 } from "next/font/google";
import "../globals.css";
import ClientLayout from "../client-layout";
import { HydrationOverlay } from "@builder.io/react-hydration-overlay";
import "@aws-amplify/ui-react/styles.css";
import { AccountProvider } from "../contexts/AccountContext"
import { SidebarProvider } from "../contexts/SidebarContext"
import { TranslationProvider } from "../contexts/TranslationContext"
import {notFound} from 'next/navigation';
import {locales} from '../../i18n';

const inter = Inter({ subsets: ["latin"] });
const jersey20 = Jersey_20({ 
  subsets: ["latin"],
  weight: "400",
  variable: "--font-jersey-20"
});

export const metadata: Metadata = {
  title: "Plexus - No-Code AI Agents at Scale",
  description: "Run AI agents over your data with no code. Plexus is a battle-tested platform for building agent-based AI workflows that analyze streams of content and take action.",
  openGraph: {
    title: "Plexus - No-Code AI Agents at Scale",
    description: "Run AI agents over your data with no code. Plexus is a battle-tested platform for building agent-based AI workflows that analyze streams of content and take action.",
    url: "https://plexus.anth.us",
    siteName: "Plexus",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "Plexus - No-Code AI Agents at Scale"
      }
    ],
    locale: "en_US",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Plexus - No-Code AI Agents at Scale",
    description: "Run AI agents over your data with no code. Plexus is a battle-tested platform for building agent-based AI workflows that analyze streams of content and take action.",
    creator: "@Anthus_AI",
    images: ["/og-image.png"],
  }
};

export default async function LocaleLayout({
  children,
  params: {locale}
}: {
  children: React.ReactNode;
  params: {locale: string};
}) {
  // Validate that the incoming `locale` parameter is valid
  if (!locales.includes(locale as any)) {
    notFound();
  }

  // Load messages for the locale synchronously
  const messages = locale === 'es' 
    ? (await import('../../messages/es.json')).default
    : (await import('../../messages/en.json')).default;

  return (
    <html lang={locale} suppressHydrationWarning>
      <head />
      <body className={`${inter.className} ${jersey20.variable}`}>
        <TranslationProvider messages={messages} locale={locale}>
          <AccountProvider>
            <SidebarProvider>
              <HydrationOverlay>
                <ClientLayout>{children}</ClientLayout>
              </HydrationOverlay>
            </SidebarProvider>
          </AccountProvider>
        </TranslationProvider>
      </body>
    </html>
  );
}