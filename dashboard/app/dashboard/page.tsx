"use client";

import { useAuthenticator, Authenticator } from '@aws-amplify/ui-react';
import SquareLogo, { LogoVariant } from '@/components/logo-square';

function AuthenticatedApp() {
  return (
    <div className="flex flex-col md:flex-row items-center justify-center min-h-screen gap-8 p-4 bg-[hsl(var(--light-blue-bg))]">
      <div className="w-full max-w-[300px]">
        <SquareLogo variant={LogoVariant.Square} className="w-full" />
      </div>
      <div className="w-full max-w-md">
        <Authenticator hideSignUp={true}>
        </Authenticator>
      </div>
    </div>
  );
}

export default AuthenticatedApp;
