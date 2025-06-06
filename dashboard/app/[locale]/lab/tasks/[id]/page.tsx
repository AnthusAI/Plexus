'use client'

import { useParams } from 'next/navigation'
import ActivityDashboard from '@/components/activity-dashboard'

export default function TaskDetailPage() {
  const params = useParams()
  const taskId = params.id as string
  
  return <ActivityDashboard initialSelectedTaskId={taskId} />
} 