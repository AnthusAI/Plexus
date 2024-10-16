import { signOut } from '../actions'
import DashboardLayout from '@/components/dashboard-layout'
import AnalysisDashboard from '@/components/analysis-dashboard'

export default function Analysis() {
  return (
    <DashboardLayout signOut={signOut}>
      <AnalysisDashboard />
    </DashboardLayout>
  )
}
