import { signOut } from '../actions'
import DashboardLayout from '@/components/dashboard-layout'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

export default function Settings() {
  return (
    <DashboardLayout signOut={signOut}>
      <div className="space-y-4">
        <h1 className="text-3xl font-bold">Settings</h1>
        <Card>
          <CardHeader>
            <CardTitle>Settings Dashboard</CardTitle>
            <CardDescription>Manage your application settings here.</CardDescription>
          </CardHeader>
          <CardContent>
            <p>Your settings will be displayed here.</p>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  )
}