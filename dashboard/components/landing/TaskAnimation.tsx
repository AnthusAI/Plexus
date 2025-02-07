"use client"

import React, { useEffect, useState } from 'react'
import { TaskDemo } from './TaskDemo'
import { cn } from '@/lib/utils'

interface DemoTaskState {
  id: string
  position: 'top' | 'bottom'
  shouldStart: boolean
  isExiting: boolean
  isSliding: boolean
}

const ANIMATION_DURATION = 500 // Duration of slide animation in ms
const PAUSE_BEFORE_EXIT = 3000 // Pause before task exits
const PAUSE_BEFORE_NEXT = 3000 // Pause before starting next task
const DEMO_DURATION = 20000 // Duration of each task demo

export const TaskAnimation = () => {
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
    setTimeout(() => {
      setTasks(prev => {
        const completedTask = prev.find(task => task.id === completedTaskId)
        const survivingTask = prev.find(task => task.id !== completedTaskId)
        if (!completedTask || !survivingTask) return prev

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

      setTimeout(() => {
        setTasks(prev => {
          const survivingTask = prev.find(task => !task.isExiting)
          if (!survivingTask) return prev

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
  )
} 