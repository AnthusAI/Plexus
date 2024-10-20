import React, { useRef, useState, useEffect } from 'react'
import { Task, TaskHeader, TaskContent, TaskComponentProps } from './Task'
import { FlaskConical } from 'lucide-react'
import StackedPieChart from './StackedPieChart'
import TaskProgress from './TaskProgress'
import NivoWaffle from './NivoWaffle'

interface ExperimentTaskData {
  accuracy?: number
  progress?: number
  elapsedTime?: string
  processedItems: number
  totalItems: number
  estimatedTimeRemaining: string
}

// Export this interface
export interface ExperimentTaskProps extends Omit<TaskComponentProps, 'renderHeader' | 'renderContent'> {
  task: {
    id: number;
    type: string;
    scorecard: string;
    score: string;
    time: string;
    summary: string;
    description?: string;
    data?: ExperimentTaskData;
  };
}

const ExperimentTask: React.FC<ExperimentTaskProps> = ({
  variant,
  task,
  onClick,
  controlButtons,
}) => {
  const data = task.data as ExperimentTaskData
  const waffleContainerRef = useRef<HTMLDivElement>(null)
  const [waffleHeight, setWaffleHeight] = useState(20)

  useEffect(() => {
    const updateWaffleHeight = () => {
      if (waffleContainerRef.current) {
        const width = waffleContainerRef.current.offsetWidth
        setWaffleHeight(width / 4)
      }
    }

    updateWaffleHeight()
    window.addEventListener('resize', updateWaffleHeight)

    return () => window.removeEventListener('resize', updateWaffleHeight)
  }, [])

  console.log('ExperimentTask data:', data);

  const visualization = (
    <StackedPieChart accuracy={data?.accuracy || 0} />
  )

  return (
    <Task 
      variant={variant} 
      task={task} 
      onClick={onClick} 
      controlButtons={controlButtons}
      renderHeader={(props) => (
        <TaskHeader {...props}>
          <div className="flex justify-end w-full">
            <FlaskConical className="h-6 w-6" />
          </div>
        </TaskHeader>
      )}
      renderContent={(props) => (
        <TaskContent {...props} visualization={visualization}>
          {data && (
            <>
              <TaskProgress 
                progress={data.progress ?? 0}
                elapsedTime={data.elapsedTime ?? ''}
                processedItems={data.processedItems ?? 0}
                totalItems={data.totalItems ?? 0}
                estimatedTimeRemaining={data.estimatedTimeRemaining ?? ''}
              />
              {variant === 'detail' && (
                <div 
                  ref={waffleContainerRef} 
                  className="mt-4 w-full"
                  style={{ height: `${waffleHeight}px` }}
                >
                  <NivoWaffle 
                    processedItems={data.processedItems ?? 0}
                    totalItems={data.totalItems ?? 1}
                    accuracy={data.accuracy ?? 0}
                  />
                </div>
              )}
            </>
          )}
        </TaskContent>
      )}
    />
  )
}

export default ExperimentTask
