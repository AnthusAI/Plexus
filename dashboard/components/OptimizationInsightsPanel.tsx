import React, { useState } from 'react'
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'
import { AlertTriangle, ChevronDown, ChevronRight, ChevronUp } from 'lucide-react'

// --- Types ---

interface HypothesisTested {
  name: string
  description?: string
  fb_delta: number
  acc_delta: number
  succeeded: boolean
}

interface CycleInsight {
  cycle: number
  analysis: string
  hypotheses_tested?: HypothesisTested[]
}

interface OptimizationDiagnostic {
  text: string
  success_rate: number
  cycles: number
  accepted: number
  rejected: number
  skipped: number
}

// --- CollapsibleText ---

function CollapsibleText({ text, maxChars = 500 }: { text: string; maxChars?: number }) {
  const [expanded, setExpanded] = useState(false)
  if (!text || text.length <= maxChars) {
    return <p className="text-sm text-muted-foreground whitespace-pre-wrap break-words">{text}</p>
  }
  return (
    <div>
      <p className="text-sm text-muted-foreground whitespace-pre-wrap break-words">
        {expanded ? text : text.slice(0, maxChars) + '...'}
      </p>
      <button
        onClick={() => setExpanded(!expanded)}
        className="text-xs text-muted-foreground/70 hover:text-foreground mt-1 flex items-center gap-1"
      >
        {expanded ? (
          <><ChevronUp className="h-3 w-3" /> Show less</>
        ) : (
          <><ChevronDown className="h-3 w-3" /> Show more</>
        )}
      </button>
    </div>
  )
}

// --- Delta display helper ---

function DeltaValue({ value }: { value: number }) {
  if (value == null) return <span className="text-muted-foreground">—</span>
  const color = value >= 0 ? 'text-green-500' : 'text-red-500'
  return (
    <span className={`${color} tabular-nums`}>
      {value >= 0 ? '+' : ''}{value.toFixed(3)}
    </span>
  )
}

// --- HypothesisRow ---

function HypothesisRow({ hyp }: { hyp: HypothesisTested }) {
  const [expanded, setExpanded] = useState(false)
  const hasDescription = hyp.description && hyp.description.trim().length > 0

  return (
    <div className="border border-border/50 rounded px-2 py-1">
      <div
        className={`flex items-center gap-2 text-xs ${hasDescription ? 'cursor-pointer' : ''}`}
        onClick={() => hasDescription && setExpanded(!expanded)}
      >
        {hasDescription && (
          expanded
            ? <ChevronDown className="h-3 w-3 text-muted-foreground/60 flex-shrink-0" />
            : <ChevronRight className="h-3 w-3 text-muted-foreground/60 flex-shrink-0" />
        )}
        <span className="text-muted-foreground truncate flex-1" title={hyp.name}>
          {hyp.name}
        </span>
        {hyp.succeeded ? (
          <Badge className="text-xs px-1 py-0 flex-shrink-0">Pass</Badge>
        ) : (
          <Badge variant="secondary" className="text-xs px-1 py-0 flex-shrink-0">Fail</Badge>
        )}
        <span className="whitespace-nowrap flex-shrink-0">
          <span className="text-muted-foreground/60 mr-1">FB</span>
          <DeltaValue value={hyp.fb_delta} />
        </span>
        <span className="whitespace-nowrap flex-shrink-0">
          <span className="text-muted-foreground/60 mr-1">ACC</span>
          <DeltaValue value={hyp.acc_delta} />
        </span>
      </div>
      {expanded && hasDescription && (
        <div className="mt-1.5 ml-5">
          <CollapsibleText text={hyp.description!} maxChars={400} />
        </div>
      )}
    </div>
  )
}

// --- OptimizationDiagnosticBanner ---

export function OptimizationDiagnosticBanner({ diagnostic }: { diagnostic: OptimizationDiagnostic }) {
  if (!diagnostic || !diagnostic.text) return null

  return (
    <Alert variant="destructive" className="mb-4">
      <AlertTriangle className="h-4 w-4" />
      <AlertTitle className="flex items-center gap-2 flex-wrap">
        Optimization Diagnostic
        <div className="flex gap-1.5 flex-wrap">
          <Badge variant="outline" className="text-xs px-1.5 py-0 font-normal">
            {diagnostic.cycles} cycles
          </Badge>
          <Badge variant="outline" className="text-xs px-1.5 py-0 font-normal">
            {diagnostic.accepted} accepted
          </Badge>
          <Badge variant="outline" className="text-xs px-1.5 py-0 font-normal">
            {diagnostic.rejected} rejected
          </Badge>
          {diagnostic.skipped > 0 && (
            <Badge variant="outline" className="text-xs px-1.5 py-0 font-normal">
              {diagnostic.skipped} skipped
            </Badge>
          )}
          <Badge variant="outline" className="text-xs px-1.5 py-0 font-normal">
            {(diagnostic.success_rate * 100).toFixed(0)}% success
          </Badge>
        </div>
      </AlertTitle>
      <AlertDescription className="mt-2">
        <CollapsibleText text={diagnostic.text} maxChars={500} />
      </AlertDescription>
    </Alert>
  )
}

// --- CycleInsightsPanel ---

export function CycleInsightsPanel({ insights }: { insights: CycleInsight[] }) {
  if (!insights || insights.length === 0) return null

  // Reverse chronological — newest first
  const sorted = [...insights].sort((a, b) => b.cycle - a.cycle)

  return (
    <div className="mt-4">
      <h3 className="text-sm font-semibold text-muted-foreground mb-2">Cycle Insights</h3>
      <Accordion type="multiple" className="w-full">
        {sorted.map((insight) => {
          const hypotheses = insight.hypotheses_tested || []
          const succeeded = hypotheses.filter(h => h.succeeded).length
          const total = hypotheses.length

          return (
            <AccordionItem key={insight.cycle} value={`cycle-${insight.cycle}`} className="border-b-0">
              <AccordionTrigger className="hover:no-underline py-2 px-0 justify-start [&>svg]:hidden group">
                <div className="flex items-center gap-2 text-sm">
                  <span className="font-medium text-muted-foreground">Cycle {insight.cycle}</span>
                  {total > 0 && (
                    <Badge
                      variant={succeeded > 0 ? 'default' : 'secondary'}
                      className="text-xs px-1.5 py-0 font-normal"
                    >
                      {succeeded}/{total} succeeded
                    </Badge>
                  )}
                </div>
              </AccordionTrigger>
              <AccordionContent className="pt-0 pb-3">
                {/* Hypotheses */}
                {hypotheses.length > 0 && (
                  <div className="space-y-1.5 mb-2">
                    {hypotheses.map((hyp, i) => (
                      <HypothesisRow key={i} hyp={hyp} />
                    ))}
                  </div>
                )}

                {/* Synthesis analysis */}
                {insight.analysis && (
                  <CollapsibleText text={insight.analysis} maxChars={300} />
                )}
              </AccordionContent>
            </AccordionItem>
          )
        })}
      </Accordion>
    </div>
  )
}
