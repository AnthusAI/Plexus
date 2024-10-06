import DashboardLayout from "@/components/dashboard-layout"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

export default function Experiments() {
  return (
    <DashboardLayout>
      <div className="space-y-4">
        <h1 className="text-3xl font-bold">Experiments</h1>
        <Card>
          <CardHeader>
            <CardTitle>Conduct and Track Experiments</CardTitle>
            <CardDescription>Set up and monitor A/B tests and other experiments.</CardDescription>
          </CardHeader>
          <CardContent>
            <p>Here you can create new experiments, track ongoing ones, and analyze results.</p>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  )
}