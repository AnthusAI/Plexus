"use client";

import { ThemeProvider } from "@/components/theme-provider";
import { SidebarProvider } from "@/app/contexts/SidebarContext";
import { Authenticator, useAuthenticator } from '@aws-amplify/ui-react';
import '@aws-amplify/ui-react/styles.css';
import { Amplify } from "aws-amplify";
import { useState, useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';

// Only configure Amplify if we're not in a CI environment
if (process.env.NODE_ENV !== 'test') {
  try {
    const outputs = require('@/amplify_outputs.json');
    Amplify.configure(outputs);
  } catch (error) {
    console.warn('Amplify outputs not found - skipping configuration');
  }
}

function AuthWrapper({ children }: { children: React.ReactNode }) {
  const { authStatus, user } = useAuthenticator(context => [context.authStatus]);
  const router = useRouter();
  const pathname = usePathname();
  
  useEffect(() => {
    if (!authStatus) {
      return;  // Don't redirect while auth is still loading
    }
    
    if (authStatus === 'unauthenticated' && pathname !== '/') {
      router.push('/');
    }
  }, [authStatus, router, pathname]);

  // If we're on the login page, show the page content
  if (pathname === '/') {
    return children;
  }

  // For other pages, require authentication
  if (!authStatus) {
    return null;  // Or return a loading spinner
  }

  if (authStatus !== 'authenticated') {
    router.push('/');
    return null;
  }

  return children;
}

export default function ClientLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [isAmplifyConfigured, setIsAmplifyConfigured] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    if (process.env.NODE_ENV !== 'test' && !isAmplifyConfigured) {
      try {
        const outputs = require('@/amplify_outputs.json');
        Amplify.configure(outputs);
        setIsAmplifyConfigured(true);
      } catch (error) {
        console.warn('Amplify outputs not found - skipping configuration');
        setIsAmplifyConfigured(true);  // Continue anyway if config fails
      }
    }
    setMounted(true);
  }, [isAmplifyConfigured]);

  if (!mounted || !isAmplifyConfigured) {
    return null;
  }

  return (
    <Authenticator.Provider>
      <SidebarProvider>
        <ThemeProvider
          attribute="class"
          defaultTheme="system"
          enableSystem
          disableTransitionOnChange
        >
          <AuthWrapper>{children}</AuthWrapper>
        </ThemeProvider>
      </SidebarProvider>
    </Authenticator.Provider>
  );
}
