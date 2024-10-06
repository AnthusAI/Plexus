import { signOut } from '../actions'
import DashboardLayout from '@/components/dashboard-layout'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

export default function Reports() {
  return (
    <DashboardLayout signOut={signOut}>
      <div className="space-y-4">
        <h1 className="text-3xl font-bold">Reports</h1>
        <Card>
          <CardHeader>
            <CardTitle>Reports Dashboard</CardTitle>
            <CardDescription>View and manage your reports here.</CardDescription>
          </CardHeader>
          <CardContent>
            <p>Your reports will be displayed here.</p>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  )
}