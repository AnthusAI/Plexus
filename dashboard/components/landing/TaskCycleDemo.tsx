"use client"

import React, { useEffect, useState } from 'react'
import { TaskDemo } from './TaskDemo'
import { FrameSection } from './FrameSection'
import { cn } from '@/lib/utils'

interface DemoTaskState {
  id: string
  position: 'top' | 'bottom'
  shouldStart: boolean
  isExiting: boolean
  isSliding: boolean
}

const TASK_HEIGHT = 280 // Approximate height of a task in pixels
const TASK_SPACING = 24 // Spacing between tasks
const ANIMATION_DURATION = 500 // Duration of slide animation in ms
const PAUSE_BEFORE_EXIT = 3000 // Pause before task exits
const PAUSE_BEFORE_NEXT = 3000 // Pause before starting next task
const DEMO_DURATION = 20000 // Duration of each task demo

export const TaskCycleDemo = () => {
  const [tasks, setTasks] = useState<DemoTaskState[]>([
    {
      id: 'task-1',
      position: 'top',
      shouldStart: true,
      isExiting: false,
      isSliding: false
    },
    {
      id: 'task-2',
      position: 'bottom',
      shouldStart: false,
      isExiting: false,
      isSliding: false
    }
  ])

  const [nextTaskId, setNextTaskId] = useState(3)

  // Start the second task after half the duration of the first task
  useEffect(() => {
    const startSecondTask = setTimeout(() => {
      setTasks(prev =>
        prev.map(task =>
          task.position === 'bottom' ? { ...task, shouldStart: true } : task
        )
      )
    }, DEMO_DURATION / 2)

    return () => clearTimeout(startSecondTask)
  }, [])

  const handleTaskComplete = (completedTaskId: string) => {
    // Wait for a moment before starting the exit animation
    setTimeout(() => {
      // Start the exit and slide animations
      setTasks(prev => {
        const completedTask = prev.find(task => task.id === completedTaskId)
        const survivingTask = prev.find(task => task.id !== completedTaskId)
        if (!completedTask || !survivingTask) return prev

        // Mark both tasks for animation
        if (completedTask.position === 'top') {
          return [
            { ...completedTask, isExiting: true },
            { ...survivingTask, isSliding: true }
          ]
        }

        return [
          { ...survivingTask, isSliding: true },
          { ...completedTask, isExiting: true }
        ]
      })

      // After the animation, update the task arrangement
      setTimeout(() => {
        setTasks(prev => {
          const survivingTask = prev.find(task => !task.isExiting)
          if (!survivingTask) return prev

          // Create new task for bottom slot
          const newTask: DemoTaskState = {
            id: `task-${nextTaskId}`,
            position: 'bottom',
            shouldStart: false,
            isExiting: false,
            isSliding: false
          }

          return [
            { ...survivingTask, position: 'top', isSliding: false },
            newTask
          ]
        })
        setNextTaskId(prev => prev + 1)

        // Start the new bottom task after a pause
        setTimeout(() => {
          setTasks(prev =>
            prev.map(task =>
              task.position === 'bottom' ? { ...task, shouldStart: true } : task
            )
          )
        }, PAUSE_BEFORE_NEXT)
      }, ANIMATION_DURATION)
    }, PAUSE_BEFORE_EXIT)
  }

  return (
    <FrameSection
      headline="Distributed AI Computing"
      headlinePosition="top"
      layout="twoColumn"
      leftContent={
        <div className="space-y-6 max-w-2xl">
          <p className="text-lg text-muted-foreground leading-relaxed">
            Transform any computer into a worker node in your distributed network. From cloud instances to local machines, Plexus seamlessly orchestrates your computational resources.
          </p>
          <div className="space-y-4 text-muted-foreground leading-relaxed">
            <p>
              Deploy tasks to AWS EC2, Azure VMs, or your local gaming rig with a unified control interface. Harness idle computing power for ML training, data processing, and custom workloads.
            </p>
            <p>
              Monitor task progress, aggregate results, and manage your distributed infrastructure in real-time through a central dashboard.
            </p>
          </div>
        </div>
      }
      rightContent={
        <div className="w-full relative h-[584px]">
          {tasks.map(task => (
            <TaskDemo
              key={task.id}
              taskId={task.id}
              shouldStart={task.shouldStart}
              onComplete={() => handleTaskComplete(task.id)}
              className={cn(
                'absolute w-full transition-all duration-500 ease-in-out',
                task.position === 'top' && !task.isSliding && 'translate-y-0',
                task.position === 'bottom' && !task.isSliding && 'translate-y-[304px]',
                task.isExiting && 'opacity-0 -translate-y-full',
                task.isSliding && 'translate-y-0'
              )}
            />
          ))}
        </div>
      }
    />
  )
} 