import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import ClientLayout from "./client-layout";
import { HydrationOverlay } from "@builder.io/react-hydration-overlay";
import { AccountProvider } from "./contexts/AccountContext"
import { ThemeProvider } from "./contexts/ThemeContext"
import { SidebarProvider } from "./contexts/SidebarContext"

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Plexus",
  description: "AI scoring at scale",
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
        <ThemeProvider
          attribute="class"
          defaultTheme="system"
          enableSystem
          disableTransitionOnChange
        >
          <AccountProvider>
            <SidebarProvider>
              <HydrationOverlay>
                <ClientLayout>{children}</ClientLayout>
              </HydrationOverlay>
            </SidebarProvider>
          </AccountProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
