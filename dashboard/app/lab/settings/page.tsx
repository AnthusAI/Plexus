'use client'

import Link from 'next/link'

export default function LabSettings() {
  return (
    <div className="px-6 pt-0 pb-6 space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Settings</h1>
        <p className="text-muted-foreground">
          Manage your account and application settings.
        </p>
      </div>

      <div className="bg-card p-6 space-y-6 rounded-lg">
        <div>
          <h2 className="text-xl font-semibold">Account Settings</h2>
          <p className="text-muted-foreground">Customize your account and preferences.</p>
        </div>
        <div>
          <p>Update your profile, change notification preferences, and manage security settings.</p>
          <div className="mt-4">
            <Link href="/lab/settings/account" className="text-primary hover:underline">
              Manage Menu Visibility
            </Link>
          </div>
        </div>
      </div>
    </div>
  )
} 