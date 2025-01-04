import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import ClientLayout from "./client-layout";
import { HydrationOverlay } from "@builder.io/react-hydration-overlay";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Plexus",
  description: "AI scoring at scale",
  icons: {
    icon: '/favicon.ico'
  }
};

export const viewport = {
  themeColor: 'white',
  width: 'device-width',
  initialScale: 1
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link href="https://fonts.googleapis.com/css2?family=Jersey+20&display=swap" rel="stylesheet" />
      </head>
      <body suppressHydrationWarning className={inter.className}>
        <HydrationOverlay>
          <ClientLayout>{children}</ClientLayout>
        </HydrationOverlay>
      </body>
    </html>
  );
}
