import { signOut } from '../actions'
import DashboardLayout from '@/components/dashboard-layout'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

export default function Reports() {
  return (
    <DashboardLayout signOut={signOut}>
      <div className="px-6 pt-0 pb-6 space-y-6">
        <div>
          <h1 className="text-3xl font-bold">Reports</h1>
          <p className="text-muted-foreground">
            Generate and view reports on your data and activities.
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Report Management</CardTitle>
            <CardDescription>Create, view, and export reports.</CardDescription>
          </CardHeader>
          <CardContent>
            <p>Access your existing reports or generate new ones based on various metrics and timeframes.</p>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  )
}