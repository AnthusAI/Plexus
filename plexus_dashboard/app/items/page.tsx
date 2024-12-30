"use client";

import { useAuthenticator } from '@aws-amplify/ui-react';
import DashboardLayout from '@/components/dashboard-layout';
import ItemsDashboard from '@/components/items-dashboard';
import { useRouter } from 'next/navigation';
import { useEffect } from 'react';

export default function ItemsPage() {
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
      <ItemsDashboard />
    </DashboardLayout>
  );
}