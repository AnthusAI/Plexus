import React, { useState } from 'react'
import { Badge } from '@/components/ui/badge'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'
import { CheckCircle2, XCircle, AlertTriangle, ExternalLink } from 'lucide-react'

// --- Types ---

type RecurrencePattern = 'PERSISTENT' | 'OSCILLATING' | 'FLIP_FLOP' | 'LATE_EMERGING'

interface RecurrenceCycleEntry {
  cycle: number
  segment: string    // "CORRECT" or error segment label
  rationale?: string
  evidence?: string
  hypothesis?: string
}

interface ProblemItem {
  first_cycle: number
  last_cycle: number
  wrong_count: number
  correct_count: number
  segment: string
  segment_stable: boolean
  feedback_label: string
  model_prediction: string
  pattern: RecurrencePattern
  per_cycle: RecurrenceCycleEntry[]
}

export interface NotableItemRecurrence {
  [itemId: string]: ProblemItem
}

// --- Pattern styling ---

const PATTERN_CONFIG: Record<
  RecurrencePattern,
  { label: string; labelClass: string; pillClass: string; description: string }
> = {
  PERSISTENT: {
    label: 'Persistent',
    labelClass: 'text-red-700 dark:text-red-400',
    pillClass: 'bg-red-500/15 text-red-700 dark:text-red-400',
    description: 'Wrong in the same confusion segment 3+ cycles, never corrected',
  },
  OSCILLATING: {
    label: 'Oscillating',
    labelClass: 'text-amber-700 dark:text-amber-400',
    pillClass: 'bg-amber-500/15 text-amber-700 dark:text-amber-400',
    description: 'Flips between correct and wrong — borderline or policy-unstable',
  },
  FLIP_FLOP: {
    label: 'Flip-flop',
    labelClass: 'text-orange-700 dark:text-orange-400',
    pillClass: 'bg-orange-500/15 text-orange-700 dark:text-orange-400',
    description: 'Wrong multiple cycles in different error directions',
  },
  LATE_EMERGING: {
    label: 'Late-emerging',
    labelClass: 'text-blue-700 dark:text-blue-400',
    pillClass: 'bg-blue-500/15 text-blue-700 dark:text-blue-400',
    description: 'Appeared correctly early, regressed in later cycles',
  },
}

function PatternBadge({ pattern }: { pattern: RecurrencePattern }) {
  const cfg = PATTERN_CONFIG[pattern]
  if (!cfg) return null
  return (
    <Badge variant="pill" className={`text-xs px-1.5 py-0 font-normal ${cfg.pillClass}`}>
      {cfg.label}
    </Badge>
  )
}

// --- Per-cycle history row ---

function CycleHistoryRow({ entry }: { entry: RecurrenceCycleEntry }) {
  const isCorrect = entry.segment === 'CORRECT'
  return (
    <div className="flex gap-2 text-xs py-0.5">
      <span className="text-muted-foreground/60 w-12 flex-shrink-0 tabular-nums">
        Cycle {entry.cycle}
      </span>
      <span className="flex-shrink-0 mt-0.5">
        {isCorrect
          ? <CheckCircle2 className="h-3 w-3 text-green-500" />
          : <XCircle className="h-3 w-3 text-red-400" />
        }
      </span>
      <div className="flex-1 min-w-0">
        {!isCorrect && (
          <span className="text-muted-foreground/70 mr-1">[{entry.segment}]</span>
        )}
        {entry.rationale && (
          <span className={isCorrect ? 'text-green-400/80' : 'text-muted-foreground'}>
            {entry.rationale}
          </span>
        )}
        {entry.evidence && (
          <span className="block text-muted-foreground/50 italic mt-0.5 truncate" title={entry.evidence}>
            "{entry.evidence}"
          </span>
        )}
      </div>
    </div>
  )
}

// --- Individual problem item card ---

function ProblemItemRow({ itemId, item }: { itemId: string; item: ProblemItem }) {
  const totalCycles = item.wrong_count + item.correct_count
  const cfg = PATTERN_CONFIG[item.pattern]
  const itemUrl = `/lab/items/${itemId}`

  return (
    <div className="border border-border/50 rounded-md overflow-hidden">
      <AccordionItem value={itemId} className="border-0">
        <AccordionTrigger className="hover:no-underline px-3 py-2 [&>svg]:hidden">
          <div className="flex items-center gap-2 flex-wrap text-xs min-w-0 w-full">
            {/* Item ID link */}
            <a
              href={itemUrl}
              className="font-mono text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1 flex-shrink-0"
              onClick={(e) => e.stopPropagation()}
              title={`Open item ${itemId}`}
            >
              {itemId.slice(0, 8)}…
              <ExternalLink className="h-2.5 w-2.5 opacity-50" />
            </a>

            <PatternBadge pattern={item.pattern} />

            <span className="text-muted-foreground/70">
              Wrong {item.wrong_count}×/{totalCycles} cycles
            </span>

            {/* Error segment */}
            <span className="text-muted-foreground/60 truncate" title={item.segment}>
              {item.segment}
            </span>

            {/* Label vs prediction */}
            <span className="ml-auto flex-shrink-0 text-muted-foreground/50">
              label <span className="text-foreground/70">{item.feedback_label}</span>
              {' → '}
              model <span className="text-foreground/70">{item.model_prediction}</span>
            </span>
          </div>
        </AccordionTrigger>
        <AccordionContent className="px-3 pb-3 pt-0">
          {cfg && (
            <p className="text-xs text-muted-foreground/60 italic mb-2">{cfg.description}</p>
          )}
          {item.per_cycle && item.per_cycle.length > 0 ? (
            <div className="space-y-0.5">
              {item.per_cycle.map((entry, i) => (
                <CycleHistoryRow key={i} entry={entry} />
              ))}
            </div>
          ) : (
            <p className="text-xs text-muted-foreground/40 italic">No cycle history available yet.</p>
          )}
        </AccordionContent>
      </AccordionItem>
    </div>
  )
}

// --- Pattern group section ---

function PatternGroup({
  pattern,
  items,
}: {
  pattern: RecurrencePattern
  items: Array<[string, ProblemItem]>
}) {
  const cfg = PATTERN_CONFIG[pattern]
  if (!cfg || items.length === 0) return null

  return (
    <div className="mb-4">
      <div className="flex items-center gap-2 mb-2">
        <span className={`text-xs font-semibold ${cfg.labelClass}`}>{cfg.label}</span>
        <Badge variant="pill" className="text-xs px-1.5 py-0 font-normal">
          {items.length}
        </Badge>
      </div>
      <Accordion type="multiple" className="space-y-1.5">
        {items.map(([itemId, item]) => (
          <ProblemItemRow key={itemId} itemId={itemId} item={item} />
        ))}
      </Accordion>
    </div>
  )
}

// --- Main panel ---

export function OptimizerProblemItemsPanel({
  notableItems,
}: {
  notableItems: NotableItemRecurrence
}) {
  const [visible, setVisible] = useState(true)

  if (!notableItems || Object.keys(notableItems).length === 0) return null

  // Group by pattern in display priority order.
  const patternOrder: RecurrencePattern[] = ['PERSISTENT', 'OSCILLATING', 'FLIP_FLOP', 'LATE_EMERGING']
  const grouped: Record<RecurrencePattern, Array<[string, ProblemItem]>> = {
    PERSISTENT: [], OSCILLATING: [], FLIP_FLOP: [], LATE_EMERGING: [],
  }
  for (const [itemId, item] of Object.entries(notableItems)) {
    if (item.pattern in grouped) {
      grouped[item.pattern as RecurrencePattern].push([itemId, item])
    }
  }
  // Sort each group by wrong_count descending.
  for (const group of Object.values(grouped)) {
    group.sort((a, b) => b[1].wrong_count - a[1].wrong_count)
  }

  const totalCount = Object.keys(notableItems).length
  const persistentCount = grouped.PERSISTENT.length
  const oscillatingCount = grouped.OSCILLATING.length

  return (
    <div className="mt-6">
      {/* Header */}
      <div className="flex items-center gap-3 mb-3">
        <div className="flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-muted-foreground" />
          <h3 className="text-sm font-semibold text-muted-foreground">Problem Item Tracker</h3>
        </div>
        <div className="flex gap-1.5 flex-wrap">
          <Badge variant="pill" className="text-xs px-1.5 py-0 font-normal">
            {totalCount} items
          </Badge>
          {persistentCount > 0 && (
            <Badge variant="pill" className="text-xs px-1.5 py-0 font-normal bg-red-500/15 text-red-700 dark:text-red-400">
              {persistentCount} persistent
            </Badge>
          )}
          {oscillatingCount > 0 && (
            <Badge variant="pill" className="text-xs px-1.5 py-0 font-normal bg-amber-500/15 text-amber-700 dark:text-amber-400">
              {oscillatingCount} oscillating
            </Badge>
          )}
        </div>
        <button
          onClick={() => setVisible(v => !v)}
          className="ml-auto text-xs text-muted-foreground/50 hover:text-muted-foreground"
        >
          {visible ? 'Hide' : 'Show'}
        </button>
      </div>

      {visible && (
        <div className="rounded-lg border border-border/50 bg-card p-4">
          <p className="text-xs text-muted-foreground/60 mb-4">
            Items that repeatedly appear in the same confusion cells across cycles.
            Persistent and oscillating items likely represent mislabels, ambiguous policy, or
            an inherent accuracy ceiling — not a prompt gap.
          </p>
          {patternOrder.map(pattern => (
            <PatternGroup key={pattern} pattern={pattern} items={grouped[pattern]} />
          ))}
        </div>
      )}
    </div>
  )
}
