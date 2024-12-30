import { signOut } from '../actions'
import DashboardLayout from '@/components/dashboard-layout'
import EvaluationsDashboard from '@/components/evaluations-dashboard'

export default function Evaluations() {
  return (
    <DashboardLayout signOut={signOut}>
      <EvaluationsDashboard />
    </DashboardLayout>
  )
}
