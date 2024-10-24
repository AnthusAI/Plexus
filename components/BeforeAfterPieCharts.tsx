import React from 'react'
import { PieChart, Pie, ResponsiveContainer } from 'recharts'

interface PieChartData {
  innerRing: Array<{ value: number }>
}

interface BeforeAfterPieChartsProps {
  before: PieChartData
  after: PieChartData
}

const PieChartComponent: React.FC<{
  innerData: Array<{ name: string; value: number; fill: string }>
  outerData: Array<{ name: string; value: number; fill: string }>
  label: string
}> = React.memo(({ innerData, outerData, label }) => (
  <div className="text-center">
    <div className="text-sm font-medium">{label}</div>
    <div className="h-[90px] w-[90px] sm:h-[100px] sm:w-[100px]">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={innerData}
            dataKey="value"
            nameKey="name"
            cx="50%"
            cy="50%"
            outerRadius={34}
            fill="#8884d8"
            strokeWidth={0}
            paddingAngle={0}
          />
          <Pie
            data={outerData}
            dataKey="value"
            nameKey="name"
            cx="50%"
            cy="50%"
            innerRadius={40}
            outerRadius={50}
            fill="#82ca9d"
            strokeWidth={0}
            paddingAngle={0}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  </div>
))

const BeforeAfterPieCharts: React.FC<BeforeAfterPieChartsProps> = ({ before, after }) => {
  const createPieData = (data: PieChartData) => [
    { name: 'Positive', value: data.innerRing[0]?.value || 0, fill: 'var(--true)' },
    { name: 'Negative', value: 100 - (data.innerRing[0]?.value || 0), fill: 'var(--false)' }
  ]

  const outerPieData = [
    { name: 'Positive', value: 50, fill: 'var(--true)' },
    { name: 'Negative', value: 50, fill: 'var(--false)' }
  ]

  return (
    <div data-testid="before-after-charts" className="flex justify-between">
      <div className="flex space-x-4">
        <PieChartComponent
          innerData={createPieData(before)}
          outerData={outerPieData}
          label="Before"
        />
        <PieChartComponent
          innerData={createPieData(after)}
          outerData={outerPieData}
          label="After"
        />
      </div>
    </div>
  )
}

export default BeforeAfterPieCharts
