"use client"

import { useAuthenticator } from '@aws-amplify/ui-react';
import DashboardLayout from '@/components/dashboard-layout';
import ScorecardsComponent from '@/components/scorecards-dashboard';
import { useRouter } from 'next/navigation';
import { useEffect } from 'react';

export default function ScorecardsPage() {
  const { signOut, authStatus } = useAuthenticator((context) => [context.signOut, context.authStatus]);
  const router = useRouter();

  useEffect(() => {
    if (authStatus !== 'authenticated') {
      router.push('/');
    }
  }, [authStatus, router]);

  const handleSignOut = async () => {
    await signOut();
    router.push('/');
  };

  if (authStatus !== 'authenticated') {
    return null; // or a loading spinner
  }

  return (
    <DashboardLayout signOut={handleSignOut}>
      <ScorecardsComponent />
    </DashboardLayout>
  );
}
