import { signOut } from '../actions'
import DashboardLayout from '@/components/dashboard-layout'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

export default function Experiments() {
  return (
    <DashboardLayout signOut={signOut}>
      <div className="space-y-4">
        <h1 className="text-3xl font-bold">Experiments</h1>
        <Card>
          <CardHeader>
            <CardTitle>Experiments Dashboard</CardTitle>
            <CardDescription>View and manage your experiments here.</CardDescription>
          </CardHeader>
          <CardContent>
            <p>Your experiments will be displayed here.</p>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  )
}