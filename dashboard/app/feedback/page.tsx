"use client";

import { useAuthenticator } from '@aws-amplify/ui-react';
import DashboardLayout from '@/components/dashboard-layout';
import FeedbackDashboard from '@/components/feedback-dashboard';
import { useRouter } from 'next/navigation';
import { signOut as amplifySignOut } from 'aws-amplify/auth';
import { Suspense } from 'react';

export default function FeedbackPage() {
  const router = useRouter();

  const handleSignOut = async () => {
    try {
      await amplifySignOut();
      router.push('/');
    } catch (error) {
      console.error('Error signing out:', error);
    }
  };

  return (
    <DashboardLayout signOut={handleSignOut}>
      <Suspense fallback={<div>Loading...</div>}>
        <FeedbackDashboard />
      </Suspense>
    </DashboardLayout>
  );
}
