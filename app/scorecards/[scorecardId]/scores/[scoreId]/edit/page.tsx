import ScoreEditComponent from '@/components/score-edit'
import DashboardLayout from '@/components/dashboard-layout'

export default function ScoreEditPage({ params }: { params: { scorecardId: string, scoreId: string } }) {
  return (
    <DashboardLayout>
      <ScoreEditComponent scorecardId={params.scorecardId} scoreId={params.scoreId} />
    </DashboardLayout>
  )
}
