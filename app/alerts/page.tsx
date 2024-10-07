import { signOut } from '../actions'
import DashboardLayout from '@/components/dashboard-layout'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

export default function Alerts() {
  return (
    <DashboardLayout signOut={signOut}>
      <div className="px-6 pt-0 pb-6 space-y-6">
        <div>
          <h1 className="text-3xl font-bold">Alerts</h1>
          <p className="text-muted-foreground">
            View and manage your alerts and notifications.
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Manage Alerts</CardTitle>
            <CardDescription>Configure and review your alert settings.</CardDescription>
          </CardHeader>
          <CardContent>
            <p>Here you can view active alerts, set up new ones, or modify existing alert configurations.</p>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  )
}