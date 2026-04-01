import type { Metadata, Viewport } from "next";
import { Inter, Jersey_20 } from "next/font/google";
import "./globals.css";
import ClientLayout from "./client-layout";
import "@aws-amplify/ui-react/styles.css";
import { SidebarProvider } from "./contexts/SidebarContext"
import { BrandProvider } from "./contexts/BrandContext"
import { BrandedTitle } from "@/components/BrandedTitle"

const inter = Inter({ subsets: ["latin"] });
const jersey20 = Jersey_20({ subsets: ["latin"], weight: "400", variable: "--font-jersey-20" });

export const metadata: Metadata = {
  title: "AI Agent Incubator",
  description: "Plexus gives your team a reliable way to evaluate, deploy, and improve AI agents through continuous learning and human feedback loops.",
  metadataBase: new URL("https://plexus.anth.us"),
  openGraph: {
    title: "AI Agent Incubator",
    description: "Plexus gives your team a reliable way to evaluate, deploy, and improve AI agents through continuous learning and human feedback loops.",
    url: "https://plexus.anth.us",
    siteName: "Plexus",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "Plexus - AI Agent Incubator"
      }
    ],
    locale: "en_US",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "AI Agent Incubator",
    description: "Plexus gives your team a reliable way to evaluate, deploy, and improve AI agents through continuous learning and human feedback loops.",
    creator: "@Anthus_AI",
    images: ["/og-image.png"],
  }
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${inter.className} ${jersey20.variable}`}>
        <BrandProvider>
          <BrandedTitle />
        <SidebarProvider>
          <ClientLayout>{children}</ClientLayout>
        </SidebarProvider>
        </BrandProvider>
      </body>
    </html>
  );
}
