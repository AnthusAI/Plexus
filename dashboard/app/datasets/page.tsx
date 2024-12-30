import { signOut } from '../actions'
import DashboardLayout from '@/components/dashboard-layout'
import DatasetsDashboard from '@/components/datasets-dashboard'

export default function DatasetsPage() {
  return (
    <DashboardLayout signOut={signOut}>
      <DatasetsDashboard />
    </DashboardLayout>
  )
}
