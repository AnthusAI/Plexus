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
    <div className="text-sm font-medium mb-1">{label}</div>
    <div className="h-[70px] w-[70px] sm:h-[80px] sm:w-[80px]">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={innerData}
            dataKey="value"
            nameKey="name"
            cx="50%"
            cy="50%"
            outerRadius={24}
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
            innerRadius={28}
            outerRadius={35}
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
    <div className="flex flex-col items-center w-full mt-4 xs:mt-0">
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
