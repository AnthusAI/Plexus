import { signOut } from '../actions'
import DashboardLayout from '@/components/dashboard-layout'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

export default function Experiments() {
  return (
    <DashboardLayout signOut={signOut}>
      <div className="px-6 pt-0 pb-6 space-y-6">
        <div>
          <h1 className="text-3xl font-bold">Experiments</h1>
          <p className="text-muted-foreground">
            Manage and track your ongoing experiments.
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Experiment Dashboard</CardTitle>
            <CardDescription>Overview of active and completed experiments.</CardDescription>
          </CardHeader>
          <CardContent>
            <p>Monitor the progress of your experiments, analyze results, and set up new trials.</p>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  )
}