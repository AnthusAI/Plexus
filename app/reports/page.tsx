import DashboardLayout from "@/components/dashboard-layout"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

export default function Reports() {
  return (
    <DashboardLayout>
      <div className="space-y-4">
        <h1 className="text-3xl font-bold">Reports</h1>
        <Card>
          <CardHeader>
            <CardTitle>Access and Generate Reports</CardTitle>
            <CardDescription>View and create various reports for your business.</CardDescription>
          </CardHeader>
          <CardContent>
            <p>Here you can access existing reports or generate new ones based on your data.</p>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  )
}