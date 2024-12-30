'use server'

import { signOut as amplifySignOut } from 'aws-amplify/auth'

export async function signOut() {
  try {
    await amplifySignOut()
  } catch (error) {
    console.error('Error signing out:', error)
  }
}