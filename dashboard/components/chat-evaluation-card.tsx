import { FlaskConical, Clock } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { PieChart, Pie, ResponsiveContainer } from "recharts"
import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart"

interface ChatEvaluationCardProps {
  evaluationId: string
  status: "running" | "completed" | "failed"
  progress?: number
  accuracy?: number
  elapsedTime?: string
  estimatedTimeRemaining?: string
  scorecard: string
  score: string
}

const chartConfig = {
  positive: { label: "Positive", color: "var(--true)" },
  negative: { label: "Negative", color: "var(--false)" },
}

function MiniStackedPieChart({ accuracy }: { accuracy: number }) {
  const data = {
    outerRing: [
      { category: "Positive", value: 50, fill: "var(--true)" },
      { category: "Negative", value: 50, fill: "var(--false)" },
    ],
    innerRing: [
      { category: "Positive", value: accuracy, fill: "var(--true)" },
      { category: "Negative", value: 100 - accuracy, fill: "var(--false)" },
    ],
  }

  return (
    <ChartContainer config={chartConfig} className="h-[60px] w-[60px]">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <ChartTooltip content={<ChartTooltipContent />} />
          <Pie
            data={data.innerRing}
            dataKey="value"
            nameKey="category"
            outerRadius={20}
            fill="var(--true)"
            isAnimationActive={false}
          />
          <Pie
            data={data.outerRing}
            dataKey="value"
            nameKey="category"
            innerRadius={22}
            outerRadius={27}
            fill="var(--chart-2)"
            isAnimationActive={false}
          />
        </PieChart>
      </ResponsiveContainer>
    </ChartContainer>
  )
}

export function ChatEvaluationCard({ 
  evaluationId, 
  status, 
  progress, 
  accuracy, 
  elapsedTime, 
  estimatedTimeRemaining,
  scorecard,
  score,
}: ChatEvaluationCardProps) {
  return (
    <Card className="w-full">
      <CardContent className="p-4">
        <div className="flex items-center mb-1">
          <div className="mr-2">
            <FlaskConical className="h-4 w-4 text-foreground" />
          </div>
          <h4 className="text-sm font-semibold flex-grow">{evaluationId}</h4>
        </div>
        <div className="text-xs text-muted-foreground mb-2">
          {scorecard} - {score}
        </div>
        {status === "completed" && accuracy !== undefined && (
          <div className="mt-2 flex items-center justify-between">
            <div>
              <div className="text-lg font-bold">{accuracy.toFixed(0)}% / 100</div>
              <div className="text-xs text-muted-foreground">Accuracy</div>
            </div>
            <MiniStackedPieChart accuracy={accuracy} />
          </div>
        )}
        {status === "running" && progress !== undefined && (
          <div className="mt-2">
            <div className="flex items-center justify-between text-xs text-muted-foreground mb-1">
              <span>{accuracy !== undefined ? `Accuracy: ${accuracy.toFixed(2)}%` : 'Accuracy: N/A'}</span>
              <span>{progress.toFixed(0)}% complete</span>
            </div>
            <div className="w-full bg-muted rounded-full h-1.5 mb-1">
              <div
                className="bg-primary h-1.5 rounded-full"
                style={{ width: `${progress}%` }}
              ></div>
            </div>
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span className="flex items-center">
                <Clock className="h-3 w-3 mr-1" />
                {elapsedTime}
              </span>
              <span>ETA: {estimatedTimeRemaining}</span>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}