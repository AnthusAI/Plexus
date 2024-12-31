import React from 'react'
import { PieChart, Pie, ResponsiveContainer } from 'recharts'

interface StackedPieChartProps {
  accuracy: number
}

const StackedPieChart: React.FC<StackedPieChartProps> = ({ accuracy }) => {
  const innerPieData = [
    { name: 'Positive', value: accuracy, fill: 'var(--true)' },
    { name: 'Negative', value: 100 - accuracy, fill: 'var(--false)' }
  ]

  const outerPieData = [
    { name: 'Positive', value: 50, fill: 'var(--true)' },
    { name: 'Negative', value: 50, fill: 'var(--false)' }
  ]

  return (
    <div className="h-[120px] w-[120px]">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={innerPieData}
            dataKey="value"
            nameKey="name"
            cx="50%"
            cy="50%"
            outerRadius={40}
            fill="#8884d8"
            strokeWidth={0}
          />
          <Pie
            data={outerPieData}
            dataKey="value"
            nameKey="name"
            cx="50%"
            cy="50%"
            innerRadius={47}
            outerRadius={60}
            fill="#82ca9d"
            strokeWidth={0}
          />
        </PieChart>
      </ResponsiveContainer>
    </div>
  )
}

export default StackedPieChart
