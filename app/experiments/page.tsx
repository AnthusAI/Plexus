import { signOut } from '../actions'
import DashboardLayout from '@/components/dashboard-layout'
import ExperimentsDashboard from '@/components/experiments-dashboard'

export default function Experiments() {
  return (
    <DashboardLayout signOut={signOut}>
      <ExperimentsDashboard />
    </DashboardLayout>
  )
}
