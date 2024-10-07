import { signOut } from '../actions'
import DashboardLayout from '@/components/dashboard-layout'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"

export default function Items() {
  return (
    <DashboardLayout signOut={signOut}>
      <div className="px-6 pt-0 pb-6 space-y-6">
        <div>
          <h1 className="text-3xl font-bold">Items</h1>
          <p className="text-muted-foreground">
            View and edit your item inventory.
          </p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Manage Your Items</CardTitle>
            <CardDescription>Add new items or remove existing ones.</CardDescription>
          </CardHeader>
          <CardContent>
            <p>Here you can manage all your items, add new ones, or remove existing ones.</p>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  )
}