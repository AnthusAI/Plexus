"use client"

import React, { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { generateClient } from "aws-amplify/data"
import type { Schema } from "@/amplify/data/resource"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { 
  Activity,
  MoreHorizontal,
  PlayCircle,
  StopCircle,
  AlertCircle
} from "lucide-react"
import { CardButton } from "@/components/CardButton"
import { format, formatDistanceToNow } from "date-fns"

const ACCOUNT_KEY = 'call-criteria'
const client = generateClient<Schema>()

export default function BatchesDashboard() {
  const [batchJobs, setBatchJobs] = useState<Schema['BatchJob']['type'][]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [accountId, setAccountId] = useState<string | null>(null)
  const [error, setError] = useState<Error | null>(null)

  useEffect(() => {
    let subscription: { unsubscribe: () => void } | null = null

    async function setupRealTimeSync() {
      try {
        const [accountResult, initialBatchJobs] = await Promise.all([
          client.models.Account.list({
            filter: { key: { eq: ACCOUNT_KEY } }
          }),
          client.models.BatchJob.list()
        ])

        if (accountResult.data.length > 0) {
          const foundAccountId = accountResult.data[0].id
          setAccountId(foundAccountId)
          
          setBatchJobs(initialBatchJobs.data.filter(b => 
            b.accountId === foundAccountId
          ))
          setIsLoading(false)

          subscription = client.models.BatchJob.observeQuery({
            filter: { accountId: { eq: foundAccountId } }
          }).subscribe({
            next: ({ items }) => {
              setBatchJobs(items.filter(item => 
                item && item.accountId === foundAccountId
              ))
            },
            error: (error: Error) => {
              console.error('Subscription error:', error)
              setError(error)
            }
          })
        } else {
          setIsLoading(false)
        }
      } catch (error) {
        console.error('Error setting up real-time sync:', error)
        setError(error as Error)
        setIsLoading(false)
      }
    }

    setupRealTimeSync()

    return () => {
      if (subscription) {
        subscription.unsubscribe()
      }
    }
  }, [])

  const getStatusIcon = (status: string) => {
    switch (status.toLowerCase()) {
      case 'running':
        return <PlayCircle className="h-4 w-4 text-green-500" />
      case 'failed':
        return <AlertCircle className="h-4 w-4 text-red-500" />
      case 'stopped':
        return <StopCircle className="h-4 w-4 text-yellow-500" />
      default:
        return null
    }
  }

  const getProgressPercentage = (job: Schema['BatchJob']['type']) => {
    if (!job.totalRequests) return 0
    return Math.round((job.completedRequests || 0) / job.totalRequests * 100)
  }

  if (isLoading) {
    return <div>Loading batch jobs...</div>
  }

  if (error) {
    return (
      <div className="p-4 text-red-500">
        Error loading batch jobs: {error.message}
      </div>
    )
  }

  return (
    <div className="space-y-4 h-full flex flex-col">
      <div className="flex-grow overflow-hidden pb-2">
        <div className="@container overflow-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[40%]">Batch Job</TableHead>
                <TableHead className="w-[20%] @[630px]:table-cell hidden">
                  Status
                </TableHead>
                <TableHead className="w-[30%] @[630px]:table-cell hidden">
                  Progress
                </TableHead>
                <TableHead className="w-[10%] @[630px]:table-cell hidden text-right">
                  Actions
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {batchJobs.map((job) => (
                <TableRow 
                  key={job.id}
                  className="transition-colors duration-200 hover:bg-muted"
                >
                  <TableCell>
                    <div>
                      {/* Narrow variant - visible below 630px */}
                      <div className="block @[630px]:hidden">
                        <div className="flex justify-between items-start mb-2">
                          <div>
                            <div className="font-medium flex items-center gap-2">
                              {getStatusIcon(job.status)}
                              {job.type}
                            </div>
                            <div className="text-sm text-muted-foreground">
                              Batch ID: {job.batchId}
                            </div>
                            <div className="text-sm text-muted-foreground">
                              {job.completedRequests || 0} / {job.totalRequests || 0} 
                              completed
                            </div>
                          </div>
                          <DropdownMenu>
                            <DropdownMenuTrigger asChild>
                              <CardButton 
                                icon={MoreHorizontal}
                                onClick={() => {}}
                              />
                            </DropdownMenuTrigger>
                            <DropdownMenuContent align="end">
                              <DropdownMenuItem>
                                <Activity className="h-4 w-4 mr-2" /> View Details
                              </DropdownMenuItem>
                            </DropdownMenuContent>
                          </DropdownMenu>
                        </div>
                      </div>
                      {/* Wide variant - visible at 630px and above */}
                      <div className="hidden @[630px]:block">
                        <div className="font-medium">{job.type}</div>
                        <div className="text-sm text-muted-foreground">
                          Batch ID: {job.batchId}
                        </div>
                      </div>
                    </div>
                  </TableCell>
                  <TableCell className="hidden @[630px]:table-cell">
                    <div className="flex items-center gap-2">
                      {getStatusIcon(job.status)}
                      <span className="capitalize">{job.status}</span>
                    </div>
                  </TableCell>
                  <TableCell className="hidden @[630px]:table-cell">
                    <div className="space-y-1">
                      <div className="text-sm">
                        {job.completedRequests || 0} / {job.totalRequests || 0} completed
                      </div>
                      <div className="h-2 w-full bg-muted rounded-full overflow-hidden">
                        <div 
                          className="h-full bg-primary rounded-full transition-all"
                          style={{ width: `${getProgressPercentage(job)}%` }}
                        />
                      </div>
                      {job.startedAt && (
                        <div className="text-xs text-muted-foreground">
                          Started {formatDistanceToNow(new Date(job.startedAt), { 
                            addSuffix: true 
                          })}
                        </div>
                      )}
                    </div>
                  </TableCell>
                  <TableCell className="hidden @[630px]:table-cell text-right">
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button 
                          variant="ghost" 
                          size="icon"
                          className="h-8 w-8 p-0"
                        >
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem>
                          <Activity className="h-4 w-4 mr-2" /> View Details
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </div>
    </div>
  )
} 