import { signOut } from '../actions'
import DashboardLayout from '@/components/dashboard-layout'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

export default function Alerts() {
  return (
    <DashboardLayout signOut={signOut}>
      <div className="space-y-4">
        <h1 className="text-3xl font-bold">Alerts</h1>
        <Card>
          <CardHeader>
            <CardTitle>Alerts Dashboard</CardTitle>
            <CardDescription>View and manage your alerts here.</CardDescription>
          </CardHeader>
          <CardContent>
            <p>Your alerts will be displayed here.</p>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  )
}