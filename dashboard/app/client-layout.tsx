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
  const { authStatus } = useAuthenticator(context => [context.authStatus]);
  const router = useRouter();
  const pathname = usePathname();
  
  // Allow unauthenticated access to /, /dashboard, /call-center-qa, /optimizer-agents, and /platform
  const publicPaths = ['/', '/dashboard', '/call-center-qa', '/optimizer-agents', '/platform'];
  const isPublicPath = publicPaths.includes(pathname);
  
  useEffect(() => {
    if (!authStatus) {
      return;  // Don't redirect while auth is still loading
    }
    
    // Only redirect in two specific cases:
    // 1. User is not authenticated and tries to access a protected page
    // 2. User is authenticated and is on the root page
    if (authStatus === 'unauthenticated' && !isPublicPath) {
      router.push('/');
    } else if (authStatus === 'authenticated' && pathname === '/') {
      router.push('/activity');
    }
  }, [authStatus, router, pathname]);

  // While auth is loading, render nothing
  if (!authStatus) {
    return null;
  }

  // For public paths
  if (isPublicPath) {
    return children;
  }

  // For all other pages, show content only if authenticated
  return authStatus === 'authenticated' ? children : null;
}

export default function ClientLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

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
          <AuthWrapper>{children}</AuthWrapper>
        </ThemeProvider>
      </SidebarProvider>
    </Authenticator.Provider>
  );
}
