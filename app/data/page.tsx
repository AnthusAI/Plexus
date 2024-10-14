import { signOut } from '../actions'
import DashboardLayout from '@/components/dashboard-layout'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

export default function DataProfiling() {
  return (
    <DashboardLayout signOut={signOut}>
      <div className="px-6 pt-0 pb-6 space-y-6">
        <div>
          <h1 className="text-3xl font-bold">Data</h1>
          <p className="text-muted-foreground">
            Analyze and understand your data characteristics.
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Data Dashboard</CardTitle>
            <CardDescription>
              Overview of data quality, statistics, and patterns.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <p>
              Explore data distributions, identify anomalies, and 
              gain insights into your datasets.
            </p>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  )
}