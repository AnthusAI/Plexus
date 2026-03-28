import ConsoleDashboard from '@/components/console-dashboard'

interface ConsoleSessionPageProps {
  params: {
    sessionId: string
  }
}

export default function LabConsoleSessionPage({ params }: ConsoleSessionPageProps) {
  return <ConsoleDashboard routeSessionId={params.sessionId} />
}
