import { signOut } from '../actions'
import DashboardLayout from '@/components/dashboard-layout'
import AlertsDashboard from '@/components/alerts-dashboard'

export default function Alerts() {
  return (
    <DashboardLayout signOut={signOut}>
      <AlertsDashboard />
    </DashboardLayout>
  )
}
