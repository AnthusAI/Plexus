"use client";

import { ThemeProvider } from "@/components/theme-provider";
import { SidebarProvider } from "@/app/contexts/SidebarContext";
import { AccountProvider } from "@/app/contexts/AccountContext";
import { Authenticator, useAuthenticator } from '@aws-amplify/ui-react';
import '@aws-amplify/ui-react/styles.css';
import { Amplify } from "aws-amplify";
import { useState, useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { Toaster } from "sonner";

function inferRegionFromGraphqlUrl(url: string): string | null {
  try {
    const hostname = new URL(url).hostname
    const match = hostname.match(/appsync-api\.([a-z0-9-]+)\.amazonaws\.com$/i)
    return match?.[1] ?? null
  } catch {
    return null
  }
}

function loadLocalAmplifyOutputs(): Record<string, any> | null {
  try {
    return require('../amplify_outputs.json')
  } catch {
    return null
  }
}

function resolveAmplifyOutputs(): Record<string, any> | null {
  const outputs = loadLocalAmplifyOutputs()
  const endpointOverride = process.env.NEXT_PUBLIC_PLEXUS_API_URL?.trim()
  const apiKeyOverride = process.env.NEXT_PUBLIC_PLEXUS_API_KEY?.trim()
  const regionOverride = process.env.NEXT_PUBLIC_PLEXUS_API_REGION?.trim()

  if (!endpointOverride && !apiKeyOverride) {
    return outputs
  }

  if (!endpointOverride || !apiKeyOverride) {
    throw new Error(
      'Partial Amplify data override detected. Both NEXT_PUBLIC_PLEXUS_API_URL and NEXT_PUBLIC_PLEXUS_API_KEY are required.',
    )
  }

  const resolvedRegion = regionOverride || inferRegionFromGraphqlUrl(endpointOverride) || outputs?.data?.aws_region
  if (!resolvedRegion) {
    throw new Error(
      'Unable to determine Amplify GraphQL region. Set NEXT_PUBLIC_PLEXUS_API_REGION or provide a standard AppSync URL.',
    )
  }

  const configuredData = outputs?.data || {}
  const configuredDefaultAuth = configuredData.default_authorization_type
  const configuredAuthTypes = Array.isArray(configuredData.authorization_types)
    ? configuredData.authorization_types
    : null

  return {
    ...(outputs || {}),
    data: {
      ...configuredData,
      url: endpointOverride,
      api_key: apiKeyOverride,
      aws_region: resolvedRegion,
      default_authorization_type: configuredDefaultAuth || "API_KEY",
      authorization_types: configuredAuthTypes?.length ? configuredAuthTypes : ["API_KEY"],
    },
  }
}

// Only configure Amplify if we're not in a CI environment
if (process.env.NODE_ENV !== 'test') {
  try {
    const outputs = resolveAmplifyOutputs()
    if (!outputs) {
      throw new Error(
        'Amplify outputs not found. Provide dashboard/amplify_outputs.json or set NEXT_PUBLIC_PLEXUS_API_URL and NEXT_PUBLIC_PLEXUS_API_KEY.',
      )
    }
    Amplify.configure(outputs);
  } catch (error) {
    console.error('Amplify configuration failed:', error);
  }
}

function AuthWrapper({ children }: { children: React.ReactNode }) {
  const { authStatus } = useAuthenticator(context => [context.authStatus]);
  const router = useRouter();
  const pathname = usePathname();
  
  // Helper functions to check path types
  const isPublicReport = (path: string) => 
    path.startsWith('/reports/') && 
    path.split('/').length === 3 && 
    !path.startsWith('/reports/lab');

  const isPublicEvaluation = (path: string) => 
    path.startsWith('/evaluations/') && 
    !path.startsWith('/evaluations/lab');
    
  const isDocumentation = (path: string) =>
    path.startsWith('/documentation');
  
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
    '/documentation/concepts/score-results',
    '/documentation/concepts/reports',
    '/documentation/evaluation-metrics',
    '/documentation/evaluation-metrics/gauges-with-context',
    '/documentation/evaluation-metrics/gauges/agreement',
    '/documentation/evaluation-metrics/gauges/accuracy',
    '/documentation/evaluation-metrics/gauges/precision',
    '/documentation/evaluation-metrics/gauges/recall',
    '/documentation/evaluation-metrics/gauges/class-number',
    '/documentation/evaluation-metrics/gauges/class-imbalance',
    '/documentation/evaluation-metrics/examples',
    '/documentation/methods/add-edit-source',
    '/documentation/methods/profile-source',
    '/documentation/methods/add-edit-scorecard',
    '/documentation/methods/add-edit-score',
    '/documentation/methods/evaluate-score',
    '/documentation/methods/monitor-tasks',
    '/documentation/advanced',
    '/documentation/advanced/cli',
    '/documentation/advanced/worker-nodes',
    '/documentation/advanced/sdk',
    '/documentation/advanced/universal-code',
    '/documentation/advanced/mcp-server',
    '/documentation/report-blocks',
    '/documentation/report-blocks/feedback-alignment',
    '/documentation/report-blocks/topic-analysis',
    '/login',
    '/signup',
  ];
  
  // Check if we should direct users straight to login
  const directToLogin = process.env.NEXT_PUBLIC_MINIMAL_BRANDING === 'true';
  
  // Only allow dynamic evaluation and report pages (with an ID) to be public
  const isPublicPath = publicPaths.includes(pathname) || 
    isPublicEvaluation(pathname) ||
    isPublicReport(pathname) ||
    isDocumentation(pathname);
    
  // Allow public reports, evaluations, and documentation even in minimal branding mode
  const isAccessiblePublicPath = directToLogin 
    ? pathname === '/dashboard' || 
      isPublicEvaluation(pathname) || 
      isPublicReport(pathname) || 
      isDocumentation(pathname)
    : isPublicPath;
  
  useEffect(() => {
    if (!authStatus) {
      return;  // Don't redirect while auth is still loading
    }
    
    // Redirect logic based on authentication status and directToLogin setting
    if (authStatus === 'unauthenticated') {
      if (directToLogin && pathname !== '/dashboard' && !isAccessiblePublicPath) {
        // When directToLogin is true, redirect all unauthenticated traffic to login page
        // except for paths explicitly allowed in isAccessiblePublicPath
        router.push('/dashboard');
      } else if (!isPublicPath) {
        // Normal behavior: redirect to home if trying to access protected page
        router.push('/');
      }
    } else if (authStatus === 'authenticated' && pathname === '/') {
      // Redirect authenticated users from home to lab/items
      router.push('/lab/items');
    }
  }, [authStatus, router, pathname, directToLogin, isPublicPath, isAccessiblePublicPath]);

  // While auth is loading, render nothing
  if (!authStatus) {
    return null;
  }

  // For public paths
  if (isAccessiblePublicPath) {
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
          <AccountProvider>
            <div style={{ visibility: 'hidden' }}>{children}</div>
          </AccountProvider>
        </SidebarProvider>
      </Authenticator.Provider>
    );
  }

  return (
    <Authenticator.Provider>
      <SidebarProvider>
        <AccountProvider>
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
        </AccountProvider>
      </SidebarProvider>
    </Authenticator.Provider>
  );
}
