'use client'

import * as React from 'react'
import Link from 'next/link'
import { Check, Copy, ExternalLink } from 'lucide-react'
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import { Spinner } from '@/components/ui/spinner'
import { useCurrentUserProfile } from '@/hooks/use-current-user-profile'

export default function LabSettings() {
  const { profile, isLoading } = useCurrentUserProfile()
  const displayName = profile?.displayName || profile?.email || 'User'
  const [copiedUserId, setCopiedUserId] = React.useState(false)

  const handleCopyUserId = React.useCallback(async () => {
    if (!profile?.id) return
    try {
      await navigator.clipboard.writeText(profile.id)
      setCopiedUserId(true)
      window.setTimeout(() => setCopiedUserId(false), 1500)
    } catch (error) {
      console.error('Failed to copy user ID:', error)
    }
  }, [profile?.id])

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
            <Button asChild type="button" variant="secondary" size="default">
              <a
                href="https://gravatar.com/profile/avatars"
                target="_blank"
                rel="noopener noreferrer"
              >
                Manage Gravatar
                <ExternalLink className="ml-2 h-4 w-4" />
              </a>
            </Button>
            <div className="space-y-2 pt-1">
              <p className="text-sm font-medium">User ID (Cognito sub)</p>
              <div className="flex items-center gap-2 w-fit max-w-full">
                <code className="text-xs bg-muted px-2 py-1 rounded-sm whitespace-nowrap">
                  {isLoading ? 'Loading user ID...' : profile?.id || 'Unavailable'}
                </code>
                <Button
                  type="button"
                  variant="secondary"
                  size="icon"
                  onClick={handleCopyUserId}
                  disabled={!profile?.id}
                  aria-label={copiedUserId ? 'User ID copied' : 'Copy user ID'}
                  title={copiedUserId ? 'Copied' : 'Copy user ID'}
                >
                  {copiedUserId ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                Local dev: set <code>PLEXUS_ACTOR_USER_ID</code> to this value in your <code>.env</code>.
              </p>
            </div>
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
