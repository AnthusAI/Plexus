import { Authenticator } from '@aws-amplify/ui-react';
import AnimatedLogo from '@/components/Logo';

export default function LoginPage() {
  return (
    <div className="flex flex-col md:flex-row items-center justify-center min-h-screen bg-gray-100">
      <div className="w-full md:w-1/2 flex justify-center p-8 border border-red-500">
        <AnimatedLogo />
        <p className="absolute top-0 left-0 text-red-500">Logo should be here</p>
      </div>
      <div className="w-full md:w-1/2 p-8">
        <Authenticator>
          {({ signOut, user }) => (
            <div>
              <h1>Welcome {user?.username}</h1>
              <button onClick={signOut}>Sign out</button>
            </div>
          )}
        </Authenticator>
      </div>
    </div>
  );
}