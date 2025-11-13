import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import ClientLayout from "./client-layout";
import { HydrationOverlay } from "@builder.io/react-hydration-overlay";
import "@aws-amplify/ui-react/styles.css";
import { SidebarProvider } from "./contexts/SidebarContext"
import { BrandProvider } from "./contexts/BrandContext"
import { BrandedTitle } from "@/components/BrandedTitle"

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Agent Operating System",
  description: "Plexus is a battle-tested platform for building AI workflows that analyze streams of content and take action.",
  viewport: {
    width: 'device-width',
    initialScale: 1,
    maximumScale: 1,
    userScalable: false,
  },
  openGraph: {
    title: "Agent Operating System",
    description: "Plexus is a battle-tested platform for building AI workflows that analyze streams of content and take action.",
    url: "https://plexus.anth.us",
    siteName: "Plexus",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "Plexus - Agent Operating System"
      }
    ],
    locale: "en_US",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Agent Operating System",
    description: "Plexus is a battle-tested platform for building AI workflows that analyze streams of content and take action.",
    creator: "@Anthus_AI",
    images: ["/og-image.png"],
  }
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <link
          rel="preconnect"
          href="https://fonts.googleapis.com"
        />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Jersey+20&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className={inter.className}>
        <BrandProvider>
          <BrandedTitle />
          <SidebarProvider>
            <HydrationOverlay>
              <ClientLayout>{children}</ClientLayout>
            </HydrationOverlay>
          </SidebarProvider>
        </BrandProvider>
      </body>
    </html>
  );
}
