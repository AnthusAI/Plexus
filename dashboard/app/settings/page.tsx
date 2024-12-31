import { signOut } from '../actions'
import DashboardLayout from '@/components/dashboard-layout'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

export default function Settings() {
  return (
    <DashboardLayout signOut={signOut}>
      <div className="px-6 pt-0 pb-6 space-y-6">
        <div>
          <h1 className="text-3xl font-bold">Settings</h1>
          <p className="text-muted-foreground">
            Manage your account and application settings.
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Account Settings</CardTitle>
            <CardDescription>Customize your account and preferences.</CardDescription>
          </CardHeader>
          <CardContent>
            <p>Update your profile, change notification preferences, and manage security settings.</p>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  )
}