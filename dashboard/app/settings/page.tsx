"use client";

import { useAuthenticator } from '@aws-amplify/ui-react';
import DashboardLayout from '@/components/dashboard-layout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useRouter } from 'next/navigation';
import { useEffect } from 'react';
import { signOut as amplifySignOut } from 'aws-amplify/auth';
import Link from 'next/link';

export default function Settings() {
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
      <div className="px-6 pt-0 pb-6 space-y-6">
        <div>
          <h1 className="text-3xl font-bold">Settings</h1>
          <p className="text-muted-foreground">
            Manage your account and application settings.
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Account Settings</CardTitle>
            <CardDescription>Customize your account and preferences.</CardDescription>
          </CardHeader>
          <CardContent>
            <p>Update your profile, change notification preferences, and manage security settings.</p>
            <div className="mt-4">
              <Link href="/settings/account" className="text-primary hover:underline">
                Manage Menu Visibility
              </Link>
            </div>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}