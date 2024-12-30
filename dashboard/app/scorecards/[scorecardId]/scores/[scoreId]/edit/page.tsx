import ScoreEditComponent from '@/components/score-edit'
import DashboardLayout from '@/components/dashboard-layout'
import { signOut } from '@/app/actions'

export default function ScoreEditPage({ params }: {
  params: { scorecardId: string, scoreId: string }
}) {
  return (
    <DashboardLayout signOut={signOut}>
      <ScoreEditComponent
        scorecardId={params.scorecardId}
        scoreId={params.scoreId}
      />
    </DashboardLayout>
  )
}
