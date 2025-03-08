"use client";

import { ThemeProvider } from "@/components/theme-provider";
import { SidebarProvider } from "@/app/contexts/SidebarContext";
import { Authenticator, useAuthenticator } from '@aws-amplify/ui-react';
import '@aws-amplify/ui-react/styles.css';
import { Amplify } from "aws-amplify";
import { useState, useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { Toaster } from "sonner";

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
  
  // Allow unauthenticated access to marketing pages and solutions
  const publicPaths = [
    '/',
    '/dashboard',
    '/solutions',
    '/solutions/platform',
    '/solutions/optimizer-agents',
    '/solutions/call-center-qa',
    '/solutions/enterprise',
    '/solutions/resources',
    '/documentation',
    '/documentation/advanced/worker-nodes',
    '/documentation/advanced/cli',
    '/documentation/advanced/sdk',
    '/documentation/concepts',
    '/documentation/methods',
    '/documentation/concepts/sources',
    '/documentation/concepts/scores',
    '/documentation/concepts/scorecards',
    '/documentation/concepts/evaluations',
    '/documentation/concepts/tasks',
    '/documentation/concepts/items',
    '/documentation/methods/add-edit-source',
    '/documentation/methods/profile-source',
    '/documentation/methods/add-edit-scorecard',
    '/documentation/methods/add-edit-score',
    '/documentation/methods/evaluate-score',
    '/documentation/methods/monitor-tasks'
  ];
  
  // Only allow dynamic evaluation pages (with an ID) to be public
  const isPublicPath = publicPaths.includes(pathname) || 
    (pathname.startsWith('/evaluations/') && pathname.split('/').length === 3 && !pathname.startsWith('/evaluations/lab'));
  
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
      router.push('/lab/activity');
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
        >
          <Toaster 
            position="bottom-right"
            theme="system"
            closeButton
            expand={true}
            visibleToasts={6}
            className="toaster group"
            style={{
              '--toast-background': 'var(--card)',
              '--toast-color': 'var(--foreground)',
              '--toast-border': 'var(--border)',
              '--toast-success': 'var(--true)',
              '--toast-error': 'var(--false)',
              '--toast-info': 'var(--primary)'
            } as React.CSSProperties}
            toastOptions={{
              style: {
                background: 'var(--card)',
                color: 'var(--foreground)',
                border: '1px solid var(--border)',
                borderRadius: '0.5rem'
              },
              classNames: {
                toast: "group bg-card text-foreground hover:bg-accent",
                title: "text-foreground font-medium",
                description: "text-muted-foreground font-mono text-sm",
                actionButton: "bg-primary text-primary-foreground",
                cancelButton: "bg-muted text-muted-foreground"
              },
              duration: 8000
            }}
          />
          <AuthWrapper>{children}</AuthWrapper>
        </ThemeProvider>
      </SidebarProvider>
    </Authenticator.Provider>
  );
}
