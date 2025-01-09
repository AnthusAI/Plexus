"use client";

import { useAuthenticator } from '@aws-amplify/ui-react';
import DashboardLayout from '@/components/dashboard-layout';
import ScoreEditComponent from '@/components/score-edit';
import { useRouter } from 'next/navigation';
import { useEffect } from 'react';
import { signOut as amplifySignOut } from 'aws-amplify/auth';

export default function ScoreEditPage({ params }: {
  params: { scorecardId: string, scoreId: string }
}) {
  const { authStatus } = useAuthenticator((context) => [context.authStatus]);
  const router = useRouter();

  useEffect(() => {
    if (authStatus !== 'authenticated') {
      router.push('/');
    }
  }, [authStatus, router]);

  const handleSignOut = async () => {
    try {
      await amplifySignOut();
      router.push('/');
    } catch (error) {
      console.error('Error signing out:', error);
    }
  };

  if (authStatus !== 'authenticated') {
    return null; // or a loading spinner
  }

  return (
    <DashboardLayout signOut={handleSignOut}>
      <ScoreEditComponent
        scorecardId={params.scorecardId}
        scoreId={params.scoreId}
      />
    </DashboardLayout>
  );
}
