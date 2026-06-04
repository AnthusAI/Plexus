const demoUser = {
  username: "demo@plexus.local",
  userId: "demo-user",
  signInDetails: {
    loginId: "demo@plexus.local",
  },
}

const demoAttributes = {
  sub: "demo-user",
  email: "demo@plexus.local",
  name: "Demo User",
  given_name: "Demo",
  family_name: "User",
}

const demoToken = {
  payload: {
    sub: "demo-user",
    email: "demo@plexus.local",
    name: "Demo User",
  },
  toString: () => "local-demo-token",
}

export async function getCurrentUser() {
  return demoUser
}

export async function fetchUserAttributes() {
  return demoAttributes
}

export async function fetchAuthSession() {
  return {
    tokens: {
      idToken: demoToken,
      accessToken: demoToken,
    },
    credentials: undefined,
    identityId: "local-demo-identity",
    userSub: "demo-user",
  }
}

export async function signOut() {
  return undefined
}

export async function signIn() {
  return { isSignedIn: true, nextStep: { signInStep: "DONE" } }
}
