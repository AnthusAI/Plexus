import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import ClientLayout from "./client-layout";
import { HydrationOverlay } from "@builder.io/react-hydration-overlay";
import "@aws-amplify/ui-react/styles.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Plexus - AI Agents at Scale",
  description: "Run AI agents over your data with no code. Plexus is a battle-tested platform for building agent-based AI workflows that analyze streams of content and take action.",
  openGraph: {
    title: "Plexus - AI Agents at Scale",
    description: "Run AI agents over your data with no code. Plexus is a battle-tested platform for building agent-based AI workflows that analyze streams of content and take action.",
    url: "https://plexus.anth.us",
    siteName: "Plexus",
    images: [
      {
        url: "/og-image.png",
        width: 1200,
        height: 630,
        alt: "Plexus - AI Agents at Scale"
      }
    ],
    locale: "en_US",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Plexus - AI Agents at Scale",
    description: "Run AI agents over your data with no code. Plexus is a battle-tested platform for building agent-based AI workflows that analyze streams of content and take action.",
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
        <script
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                function getTheme() {
                  try {
                    const theme = localStorage.getItem('theme');
                    if (theme === 'dark' || theme === 'light') return theme;
                    if (theme === 'system' || !theme) {
                      return window.matchMedia('(prefers-color-scheme: dark)').matches
                        ? 'dark'
                        : 'light';
                    }
                    return 'light'; // fallback
                  } catch (e) {
                    return 'light'; // fallback if localStorage is not available
                  }
                }
                const theme = getTheme();
                document.documentElement.classList.add(theme);
                document.documentElement.style.colorScheme = theme;
              })();
            `,
          }}
        />
      </head>
      <body className={inter.className}>
        <HydrationOverlay>
          <ClientLayout>{children}</ClientLayout>
        </HydrationOverlay>
      </body>
    </html>
  );
}
