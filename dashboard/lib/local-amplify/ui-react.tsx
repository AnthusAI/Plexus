import React from "react"

const demoUser = {
  username: "demo@plexus.local",
  userId: "demo-user",
  signInDetails: {
    loginId: "demo@plexus.local",
  },
}

function Provider({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}

function AuthenticatorComponent({ children }: { children?: React.ReactNode | ((props: any) => React.ReactNode) }) {
  if (typeof children === "function") {
    return <>{children({ user: demoUser, signOut: async () => undefined })}</>
  }
  return <>{children}</>
}

export const Authenticator = Object.assign(AuthenticatorComponent, { Provider })

export function useAuthenticator() {
  return {
    authStatus: "authenticated",
    user: demoUser,
    signOut: async () => undefined,
  }
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  return <>{children}</>
}
