"use client"

import { ReactNode } from "react"
import { useRouter } from "next/navigation"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"

interface DataPageShellProps {
  activeTab: "datasets" | "sources"
  children: ReactNode
}

export default function DataPageShell({ activeTab, children }: DataPageShellProps) {
  const router = useRouter()

  return (
    <div className="flex h-full min-h-0 flex-col px-6 pb-6 pt-0">
      <div className="mb-4">
        <h1 className="text-3xl font-bold">Data</h1>
        <p className="text-muted-foreground">Browse datasets and sources in dedicated views.</p>
      </div>

      <Tabs
        value={activeTab}
        onValueChange={(value) => {
          if (value === "datasets") {
            router.push("/lab/datasets")
            return
          }
          router.push("/lab/data/sources")
        }}
        className="flex min-h-0 flex-1 flex-col"
      >
        <TabsList className="mb-3 grid w-full max-w-[320px] grid-cols-2">
          <TabsTrigger value="datasets">Datasets</TabsTrigger>
          <TabsTrigger value="sources">Sources</TabsTrigger>
        </TabsList>

        <div className="min-h-0 flex-1 overflow-hidden">{children}</div>
      </Tabs>
    </div>
  )
}
