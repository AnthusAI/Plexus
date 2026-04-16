import React, { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'
import { AlertTriangle, ChevronDown, ChevronRight, ChevronUp, Stethoscope, ClipboardList } from 'lucide-react'

// --- Types ---

interface HypothesisTested {
  name: string
  description?: string
  fb_delta: number
  acc_delta: number
  succeeded: boolean
}

export interface CycleInsight {
  cycle: number
  analysis: string
  diagnosis_summary?: string
  prescription_summary?: string
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

function MarkdownText({ text }: { text: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      className="text-sm text-muted-foreground prose prose-sm prose-invert max-w-none
        prose-headings:text-foreground prose-headings:font-semibold
        prose-h2:text-base prose-h3:text-sm
        prose-strong:text-foreground
        prose-ul:my-1 prose-li:my-0
        prose-p:my-1"
    >
      {text}
    </ReactMarkdown>
  )
}

function CollapsibleText({ text, maxChars = 500 }: { text: string; maxChars?: number }) {
  const [expanded, setExpanded] = useState(false)
  if (!text || text.length <= maxChars) {
    return <MarkdownText text={text} />
  }
  return (
    <div>
      <MarkdownText text={expanded ? text : text.slice(0, maxChars) + '...'} />
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

// --- EndOfRunReport ---

interface EndOfRunReportSection {
  summary?: string
  detail?: string
  text?: string
}

interface EndOfRunReportData {
  diagnosis?: EndOfRunReportSection
  prescription?: EndOfRunReportSection
  run_summary?: {
    cycles?: number
    accepted?: number
    rejected?: number
    skipped?: number
    success_rate?: number
    baseline_fb_ac1?: number
    final_fb_ac1?: number
    total_fb_improvement?: number
    total_acc_improvement?: number
    stop_reason?: string
  }
}

export function ReportSection({
  icon,
  title,
  summary,
  detail,
}: {
  icon: React.ReactNode
  title: string
  summary?: string
  detail?: string
}) {
  const [detailOpen, setDetailOpen] = useState(false)
  const hasSummary = summary && summary.trim().length > 0
  const hasDetail = detail && detail.trim().length > 0
  const fallback = !hasSummary && !hasDetail

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-sm font-semibold text-muted-foreground">
        {icon}
        {title}
      </div>

      {fallback ? (
        <p className="text-xs text-muted-foreground/50 italic">Not available</p>
      ) : (
        <>
          {hasSummary && (
            <div className="prose prose-sm prose-invert max-w-none
              prose-headings:text-foreground prose-headings:font-semibold
              prose-h2:text-sm prose-h3:text-xs
              prose-strong:text-foreground
              prose-ul:my-1 prose-li:my-0.5
              prose-p:my-1 text-sm text-foreground/90">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{summary!}</ReactMarkdown>
            </div>
          )}

          {hasDetail && (
            <div>
              <button
                onClick={() => setDetailOpen(v => !v)}
                className="text-xs text-muted-foreground/60 hover:text-muted-foreground flex items-center gap-1 mt-1"
              >
                {detailOpen
                  ? <><ChevronUp className="h-3 w-3" /> Hide full analysis</>
                  : <><ChevronDown className="h-3 w-3" /> Show full analysis</>
                }
              </button>
              {detailOpen && (
                <div className="mt-2 pt-2 border-t border-border/30 prose prose-sm prose-invert max-w-none
                  prose-headings:text-foreground prose-headings:font-semibold
                  prose-h2:text-sm prose-h3:xs
                  prose-strong:text-foreground
                  prose-ul:my-1 prose-li:my-0.5
                  prose-p:my-1 text-xs text-muted-foreground">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{detail!}</ReactMarkdown>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}

// Parse a text field that uses ## SUMMARY / ## DETAIL section markers into
// separate summary and detail strings. This is more reliable than the auto-split
// `summary`/`detail` fields, which are sometimes cut mid-sentence or mid-heading.
function parseStructuredText(text: string): [string, string] | null {
  if (!text) return null
  const summaryMatch = text.match(/^##\s*SUMMARY\s*\n([\s\S]*?)(?=\n##\s*DETAIL|\s*$)/i)
  const detailMatch = text.match(/##\s*DETAIL\s*\n([\s\S]*)$/i)
  if (!summaryMatch && !detailMatch) return null
  return [
    summaryMatch ? summaryMatch[1].trim() : '',
    detailMatch ? detailMatch[1].trim() : '',
  ]
}

// Resolve summary/detail for a report section, preferring the structured `text`
// field when available (avoids mid-heading splits in the auto-split fields).
function resolveSummaryDetail(section: EndOfRunReportSection | undefined): [string, string] {
  if (!section) return ['', '']
  if (section.text) {
    const parsed = parseStructuredText(section.text)
    if (parsed) return parsed
  }
  return [section.summary || '', section.detail || section.text || '']
}

export function EndOfRunReport({ report }: { report: EndOfRunReportData }) {
  if (!report) return null
  const { diagnosis, prescription, run_summary } = report
  const hasDiagnosis = diagnosis && (diagnosis.summary || diagnosis.detail || diagnosis.text)
  const hasPrescription = prescription && (prescription.summary || prescription.detail || prescription.text)
  if (!hasDiagnosis && !hasPrescription) return null

  const [diagSummary, diagDetail] = resolveSummaryDetail(diagnosis)
  const [prescSummary, prescDetail] = resolveSummaryDetail(prescription)

  return (
    <div className="mt-6 space-y-4">
      <div className="flex items-center gap-2">
        <h3 className="text-sm font-semibold text-muted-foreground">End-of-Run Report</h3>
        {run_summary && (
          <div className="flex gap-1.5 flex-wrap">
            {run_summary.stop_reason && (
              <Badge variant="outline" className="text-xs px-1.5 py-0 font-normal capitalize">
                {run_summary.stop_reason.replace(/_/g, ' ')}
              </Badge>
            )}
            {run_summary.total_fb_improvement != null && (
              <Badge
                variant="outline"
                className={`text-xs px-1.5 py-0 font-normal ${run_summary.total_fb_improvement >= 0 ? 'text-green-500' : 'text-red-500'}`}
              >
                FB {run_summary.total_fb_improvement >= 0 ? '+' : ''}{run_summary.total_fb_improvement.toFixed(3)}
              </Badge>
            )}
            {run_summary.total_acc_improvement != null && (
              <Badge
                variant="outline"
                className={`text-xs px-1.5 py-0 font-normal ${run_summary.total_acc_improvement >= 0 ? 'text-green-500' : 'text-red-500'}`}
              >
                ACC {run_summary.total_acc_improvement >= 0 ? '+' : ''}{run_summary.total_acc_improvement.toFixed(3)}
              </Badge>
            )}
          </div>
        )}
      </div>

      <div className="@container">
      <div className="grid grid-cols-1 gap-4 @lg:grid-cols-2">
        {hasDiagnosis && (
          <div className="rounded-lg border border-border/50 bg-card p-4">
            <ReportSection
              icon={<Stethoscope className="h-4 w-4" />}
              title="Diagnosis"
              summary={diagSummary}
              detail={diagDetail}
            />
          </div>
        )}
        {hasPrescription && (
          <div className="rounded-lg border border-border/50 bg-card p-4">
            <ReportSection
              icon={<ClipboardList className="h-4 w-4" />}
              title="Prescription"
              summary={prescSummary}
              detail={prescDetail}
            />
          </div>
        )}
      </div>
      </div>
    </div>
  )
}
