import ReportClientLayout from './client-layout'

export const metadata = {
  title: 'Plexus - Shared Report',
  description: 'View a shared Plexus report.',
}

export default function ReportLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return <ReportClientLayout>{children}</ReportClientLayout>
} 