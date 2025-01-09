"use client";

import { useAuthenticator } from '@aws-amplify/ui-react';
import DashboardLayout from '@/components/dashboard-layout';
import ItemsDashboard from '@/components/items-dashboard';
import { useRouter } from 'next/navigation';
import { signOut as amplifySignOut } from 'aws-amplify/auth';

export default function ItemsPage() {
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
      <ItemsDashboard />
    </DashboardLayout>
  );
}