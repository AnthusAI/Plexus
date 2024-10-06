import { signOut } from '../actions'
import DashboardLayout from '@/components/dashboard-layout'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

export default function Scorecards() {
  return (
    <DashboardLayout signOut={signOut}>
      <div className="space-y-4">
        <h1 className="text-3xl font-bold">Scorecards</h1>
        <Card>
          <CardHeader>
            <CardTitle>Scorecards Dashboard</CardTitle>
            <CardDescription>View and manage your scorecards here.</CardDescription>
          </CardHeader>
          <CardContent>
            <p>Your scorecards will be displayed here.</p>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  )
}