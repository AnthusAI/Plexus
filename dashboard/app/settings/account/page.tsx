"use client"

import { redirect } from 'next/navigation'

export default function AccountSettings() {
  // Redirect to the lab version
  redirect('/lab/settings/account')
} 