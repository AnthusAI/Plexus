'use client'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { LanguageSelector } from "@/components/ui/language-selector"
import { useTranslations } from '@/app/contexts/TranslationContext'
import Link from 'next/link'

export default function LabSettings() {
  const t = useTranslations('settings');
  const tCommon = useTranslations('common');

  return (
    <div className="px-6 pt-0 pb-6 space-y-6">
      <div>
        <h1 className="text-3xl font-bold">{t('title')}</h1>
        <p className="text-muted-foreground">
          {t('description')}
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t('user')}</CardTitle>
          <CardDescription>Customize your user preferences.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <LanguageSelector />
          <p>Update your profile, change notification preferences, and manage security settings.</p>
          <div className="mt-4">
            <Link href="/lab/settings/account" className="text-primary hover:underline">
              Manage Menu Visibility
            </Link>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('account.title')}</CardTitle>
          <CardDescription>{t('account.description')}</CardDescription>
        </CardHeader>
        <CardContent>
          <p>Configure default settings for your organization.</p>
          <div className="mt-4">
            <Link href="/lab/settings/account" className="text-primary hover:underline">
              {t('account.title')}
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  )
} 