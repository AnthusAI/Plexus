'use client'

import * as React from 'react'
import Link from 'next/link'
import { ExternalLink } from 'lucide-react'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import { Spinner } from '@/components/ui/spinner'
import { useCurrentUserProfile } from '@/hooks/use-current-user-profile'

export default function LabSettings() {
  const { profile, isLoading } = useCurrentUserProfile()
  const displayName = profile?.displayName || profile?.email || 'User'
  const handleManageGravatar = () => {
    window.open('https://gravatar.com/profile/avatars', '_blank', 'noopener,noreferrer')
  }

  return (
    <div className="px-6 pt-0 pb-6 space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Settings</h1>
        <p className="text-muted-foreground">
          Manage your account and application settings.
        </p>
      </div>

      <div className="bg-card p-6 space-y-6 rounded-lg">
        <div className="flex items-start gap-4">
          <Avatar className="h-14 w-14">
            {profile?.gravatarUrl && (
              <AvatarImage src={profile.gravatarUrl} alt={`${displayName} avatar`} />
            )}
            <AvatarFallback className="bg-background dark:bg-border">
              {isLoading ? <Spinner className="h-5 w-5" /> : profile?.initials || 'U'}
            </AvatarFallback>
          </Avatar>
          <div className="min-w-0 flex-1 space-y-2">
            <div>
              <h2 className="text-xl font-semibold">User Profile</h2>
              <p className="text-muted-foreground truncate">
                {isLoading ? 'Loading profile...' : profile?.email || 'No email available'}
              </p>
            </div>
            <Button
              type="button"
              variant="secondary"
              size="default"
              className="border-0 shadow-none focus-visible:ring-0 focus-visible:ring-offset-0"
              onClick={handleManageGravatar}
            >
              Manage Gravatar
              <ExternalLink className="ml-2 h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>

      <div className="bg-card p-6 space-y-6 rounded-lg">
        <div>
          <h2 className="text-xl font-semibold">Account Settings</h2>
          <p className="text-muted-foreground">Customize your account and preferences.</p>
        </div>
        <div>
          <p>Update your profile, change notification preferences, and manage security settings.</p>
          <div className="mt-4">
            <Button
              asChild
              variant="secondary"
              size="default"
              className="border-0 shadow-none focus-visible:ring-0 focus-visible:ring-offset-0"
            >
              <Link href="/lab/settings/account">
                Manage Menu Visibility
              </Link>
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
} 
