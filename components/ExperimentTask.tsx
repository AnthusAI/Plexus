import React from "react"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { TaskProgress, TaskProps } from "@/components/TaskProgress"
import { FlaskConical } from "lucide-react"
import { cn } from "@/lib/utils"
import { Gauge } from "@/components/gauge"

export interface ExperimentTaskProps extends TaskProps {}

export default function ExperimentTask({ 
  variant = "grid",
  task,
  onClick,
  controlButtons
}: ExperimentTaskProps) {
  const { data } = task

  if (!data) return null

  const progress = data.processedItems && data.totalItems 
    ? (data.processedItems / data.totalItems) * 100 
    : 0

  return (
    <Card 
      className={cn(
        "relative overflow-hidden transition-all",
        variant === "detail" ? "h-full" : "h-[280px]",
        onClick && "cursor-pointer hover:border-border"
      )}
      onClick={onClick}
    >
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <div className="flex items-center space-x-2">
          <FlaskConical className="h-6 w-6" />
          <div>
            <div className="font-semibold">{task.type}</div>
            <div className="text-sm text-muted-foreground">{task.scorecard}</div>
          </div>
        </div>
        {controlButtons}
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {data.accuracy !== undefined && (
            <div className="flex justify-center">
              <Gauge value={data.accuracy} />
            </div>
          )}
          
          <div>
            <div className="mb-1 text-sm font-medium">{task.score}</div>
            <TaskProgress 
              progress={progress}
              elapsedTime={data.elapsedTime}
              processedItems={data.processedItems}
              totalItems={data.totalItems}
              estimatedTimeRemaining={data.estimatedTimeRemaining}
            />
          </div>

          {task.summary && (
            <div className="text-sm text-muted-foreground">
              {task.summary}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
