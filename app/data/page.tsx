import { signOut } from '../actions'
import DashboardLayout from '@/components/dashboard-layout'
import DataDashboard from '@/components/data-dashboard'

export default function DataPage() {
  return (
    <DashboardLayout signOut={signOut}>
      <DataDashboard />
    </DashboardLayout>
  )
}
