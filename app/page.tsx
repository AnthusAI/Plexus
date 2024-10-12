"use client";

import { useEffect } from "react";
import { useAuthenticator, Authenticator } from '@aws-amplify/ui-react';
import { useRouter } from 'next/navigation';
import SquareLogo, { LogoVariant } from '../components/logo-square';

function AuthenticatedApp() {
  const { authStatus } = useAuthenticator(context => [context.authStatus]);
  const router = useRouter();

  useEffect(() => {
    if (authStatus === 'authenticated') {
      router.push('/activity');
    }
  }, [authStatus, router]);

  if (authStatus !== 'authenticated') {
    return (
      <div className="flex flex-col md:flex-row items-center justify-center min-h-screen gap-4 bg-[hsl(var(--light-blue-bg))]">
        <div className="w-full max-w-md">
          <SquareLogo variant={LogoVariant.Square} />
        </div>
        <div className="w-full max-w-md">
          <Authenticator>
            {({ signOut, user }) => (
              <div>
                <h1>Welcome, {user?.username}!</h1>
                <button onClick={signOut}>Sign out</button>
              </div>
            )}
          </Authenticator>
        </div>
      </div>
    );
  }

  return null; // The user will be redirected, so we don't need to render anything here
}

export default AuthenticatedApp;
