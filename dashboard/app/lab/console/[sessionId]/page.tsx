import ConsoleDashboard from '@/components/console-dashboard'

interface ConsoleSessionPageProps {
  params: Promise<{
    sessionId: string
  }>
}

export default async function LabConsoleSessionPage({ params }: ConsoleSessionPageProps) {
  const { sessionId } = await params
  return <ConsoleDashboard routeSessionId={sessionId} />
}
