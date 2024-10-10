import ColorPalette from './ColorPalette'
import DashboardLayout from '@/components/dashboard-layout'
import { Button } from '@/components/ui/button'
export default function ColorsPage() {
  return (
    <DashboardLayout>
      <div className="container mx-auto px-4 py-8">
        <h1 className="text-2xl font-bold mb-4">Colors Page</h1>
        <ColorPalette />
      </div>
    </DashboardLayout>
  )
}