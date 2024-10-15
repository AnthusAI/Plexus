import { signOut } from '../actions'
import DashboardLayout from '@/components/dashboard-layout'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

export default function Analysis() {
  return (
    <DashboardLayout signOut={signOut}>
      <div className="px-6 pt-0 pb-6 space-y-6">
        <div>
          <h1 className="text-3xl font-bold">Analysis</h1>
          <p className="text-muted-foreground">
            View and manage your analysis processes.
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Analysis Center</CardTitle>
            <CardDescription>Track and control your analysis efforts.</CardDescription>
          </CardHeader>
          <CardContent>
            <p>Monitor ongoing analyses, start new processes, and review completed analyses.</p>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  )
}
