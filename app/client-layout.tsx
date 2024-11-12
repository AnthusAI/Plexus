"use client";

import { ThemeProvider } from "@/components/theme-provider";
import { SidebarProvider } from "@/app/contexts/SidebarContext";
import { Authenticator } from '@aws-amplify/ui-react';
import '@aws-amplify/ui-react/styles.css';
import { Amplify } from "aws-amplify";
import outputs from "@/amplify_outputs.json";
import { useState, useEffect } from 'react';

Amplify.configure(outputs);

export default function ClientLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [mounted, setMounted] = useState(false);

  // Only render theme-dependent content when mounted
  useEffect(() => {
    setMounted(true);
  }, []);

  // Prevent theme flash by not rendering until mounted
  if (!mounted) {
    return (
      <Authenticator.Provider>
        <SidebarProvider>
          <div style={{ visibility: 'hidden' }}>{children}</div>
        </SidebarProvider>
      </Authenticator.Provider>
    );
  }

  return (
    <Authenticator.Provider>
      <SidebarProvider>
        <ThemeProvider
          attribute="class"
          defaultTheme="system"
          enableSystem
          disableTransitionOnChange
          forcedTheme={typeof window !== 'undefined' ? undefined : 'light'}
        >
          {children}
        </ThemeProvider>
      </SidebarProvider>
    </Authenticator.Provider>
  );
}
