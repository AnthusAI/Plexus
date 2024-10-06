import { signOut } from '../actions'
import DashboardLayout from '@/components/dashboard-layout'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

export default function Items() {
  return (
    <DashboardLayout signOut={signOut}>
      <div className="space-y-4">
        <h1 className="text-3xl font-bold">Items</h1>
        <Card>
          <CardHeader>
            <CardTitle>Manage Your Items</CardTitle>
            <CardDescription>View and edit your item inventory.</CardDescription>
          </CardHeader>
          <CardContent>
            <p>Here you can manage all your items, add new ones, or remove existing ones.</p>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  )
}