import DashboardLayout from "@/components/dashboard-layout"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

export default function Alerts() {
  return (
    <DashboardLayout>
      <div className="space-y-4">
        <h1 className="text-3xl font-bold">Alerts</h1>
        <Card>
          <CardHeader>
            <CardTitle>View and Manage Alerts</CardTitle>
            <CardDescription>Stay informed about important events.</CardDescription>
          </CardHeader>
          <CardContent>
            <p>Here you can view and manage all your alerts and notifications.</p>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  )
}