"use client"

import React from 'react'
import TemplatesDashboard from '@/components/templates-dashboard'

interface TemplatePageProps {
  params: { id: string }
}

export default function TemplatePage({ params }: TemplatePageProps) {
  return <TemplatesDashboard initialSelectedTemplateId={params.id} />
}