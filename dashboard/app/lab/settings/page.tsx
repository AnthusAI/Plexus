'use client'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
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

      <Card>
        <CardHeader>
          <CardTitle>Account Settings</CardTitle>
          <CardDescription>Customize your account and preferences.</CardDescription>
        </CardHeader>
        <CardContent>
          <p>Update your profile, change notification preferences, and manage security settings.</p>
          <div className="mt-4">
            <Link href="/lab/settings/account" className="text-primary hover:underline">
              Manage Menu Visibility
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  )
} 