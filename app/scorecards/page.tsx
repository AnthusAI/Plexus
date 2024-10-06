import DashboardLayout from "@/components/dashboard-layout"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

export default function Scorecards() {
  return (
    <DashboardLayout>
      <div className="space-y-4">
        <h1 className="text-3xl font-bold">Scorecards</h1>
        <Card>
          <CardHeader>
            <CardTitle>View and Manage Scorecards</CardTitle>
            <CardDescription>Track performance metrics and KPIs.</CardDescription>
          </CardHeader>
          <CardContent>
            <p>Here you can view, create, and manage scorecards to monitor your business performance.</p>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  )
}