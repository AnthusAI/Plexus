import React from 'react';
import { generateClient } from 'aws-amplify/data';
import type { Schema } from '@/amplify/data/resource';
import { ReportBlockProps } from './ReportBlock';
import { ChevronDown, ChevronUp, CheckCircle } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { LabelBadgeComparison } from '@/components/LabelBadgeComparison';
import { IdentifierDisplay } from '@/components/ui/identifier-display';

// ---- Types ----------------------------------------------------------------

interface Exemplar {
  feedback_item_id: string;
  item_id?: string | null;
  item_identifiers?: string | null;
  item_external_id?: string | null;
  initial_value: string;
  final_value: string;
  edit_comment: string;
  editor_name?: string | null;
  edited_at?: string | null;
  reason: string;
  guideline_quote?: string;
  is_invalid: boolean;
}

interface Topic {
  label: string;
  count: number;
  exemplars: Exemplar[];
}

interface FeedbackContradictionsData {
  score_name: string;
  total_items_analyzed: number;
  contradictions_found: number;
  topics: Topic[];
  error?: string;
}

// ---- Exemplar row ----------------------------------------------------------

const ExemplarRow: React.FC<{ exemplar: Exemplar }> = ({ exemplar }) => {
  const [invalidated, setInvalidated] = React.useState(exemplar.is_invalid);
  const [loading, setLoading] = React.useState(false);

  const handleMarkInvalid = async () => {
    if (invalidated || loading) return;
    setLoading(true);
    try {
      const client = generateClient<Schema>();
      await client.models.FeedbackItem.update({
        id: exemplar.feedback_item_id,
        isInvalid: true,
      });
      setInvalidated(true);
    } catch (err) {
      console.error('Failed to mark feedback item invalid:', err);
    } finally {
      setLoading(false);
    }
  };

  const isCorrect = exemplar.initial_value === exemplar.final_value;

  return (
    <div className={`space-y-2 py-3 transition-opacity ${invalidated ? 'opacity-40' : ''}`}>
      {/* Score value comparison + action */}
      <div className="flex items-center justify-between gap-4">
        <LabelBadgeComparison
          predictedLabel={exemplar.initial_value || '—'}
          actualLabel={exemplar.final_value || '—'}
          isCorrect={isCorrect}
          showStatus={false}
        />
        {invalidated ? (
          <span className="flex items-center gap-1 text-xs text-muted-foreground shrink-0">
            <CheckCircle className="h-3 w-3" /> Marked invalid
          </span>
        ) : (
          <Button
            variant="secondary"
            size="sm"
            className="text-xs h-6 shrink-0"
            disabled={loading}
            onClick={handleMarkInvalid}
          >
            {loading ? 'Saving…' : 'Mark Invalid'}
          </Button>
        )}
      </div>

      {/* Reviewer comment */}
      {exemplar.edit_comment && (
        <p className="text-sm text-muted-foreground italic">
          &ldquo;{exemplar.edit_comment}&rdquo;
        </p>
      )}

      {/* Contradiction reason */}
      <p className="text-sm">{exemplar.reason}</p>

      {/* Guideline quote */}
      {exemplar.guideline_quote && (
        <p className="text-sm text-muted-foreground">
          <span className="font-medium text-foreground">Guideline: </span>
          &ldquo;{exemplar.guideline_quote}&rdquo;
        </p>
      )}

      <IdentifierDisplay
        identifiers={exemplar.item_identifiers ?? undefined}
        externalId={exemplar.item_external_id ?? undefined}
      />
    </div>
  );
};

// ---- Topic section ---------------------------------------------------------

const TopicSection: React.FC<{ topic: Topic }> = ({ topic }) => {
  const [open, setOpen] = React.useState(false);

  return (
    <div>
      {/* Header row */}
      <div className="flex items-center justify-between py-2">
        <span className="font-medium text-sm">{topic.label}</span>
        <Badge variant="secondary" className="shrink-0 ml-4">{topic.count}</Badge>
      </div>

      {/* Hrule + caret expand control */}
      <div className="flex flex-col items-center">
        <div className="w-full h-px bg-border mb-1" />
        <button
          onClick={() => setOpen((v) => !v)}
          className="flex items-center justify-center rounded-full hover:bg-muted/50 transition-colors p-0.5"
          aria-label={open ? 'Collapse' : 'Expand'}
        >
          {open
            ? <ChevronUp className="h-3 w-3 text-muted-foreground" />
            : <ChevronDown className="h-3 w-3 text-muted-foreground" />}
        </button>
      </div>

      {open && (
        <div className="divide-y">
          {topic.exemplars.map((ex) => (
            <ExemplarRow key={ex.feedback_item_id} exemplar={ex} />
          ))}
        </div>
      )}
    </div>
  );
};

// ---- Main block component --------------------------------------------------

const FeedbackContradictions: React.FC<ReportBlockProps> = (props) => {
  const [loadedOutput, setLoadedOutput] = React.useState<FeedbackContradictionsData | null>(null);

  let parsedOutput: any = null;
  if (props.output) {
    if (typeof props.output === 'string') {
      try { parsedOutput = JSON.parse(props.output); } catch { /* ignore */ }
    } else {
      parsedOutput = props.output;
    }
  }

  const outputAttachment = parsedOutput?.output_attachment ?? null;
  const outputCompacted = parsedOutput?.output_compacted ?? false;
  React.useEffect(() => {
    if (!outputCompacted || !outputAttachment || loadedOutput) return;
    (async () => {
      try {
        const { downloadData } = await import('aws-amplify/storage');
        const result = await downloadData({
          path: outputAttachment,
          options: { bucket: 'reportBlockDetails' as any },
        }).result;
        const text = await result.body.text();
        setLoadedOutput(JSON.parse(text));
      } catch (e) {
        console.warn('FeedbackContradictions: failed to load output attachment', e);
      }
    })();
  }, [outputCompacted, outputAttachment, loadedOutput]);

  if (outputCompacted && !loadedOutput) {
    return <p className="text-sm text-muted-foreground p-4">Loading contradiction analysis data…</p>;
  }

  const output: FeedbackContradictionsData | null = loadedOutput ?? parsedOutput;

  if (!output) {
    return <p className="text-muted-foreground text-sm">No contradiction analysis data available.</p>;
  }

  if (output.error) {
    return (
      <div className="text-destructive text-sm">
        <p>Error generating FeedbackContradictions block:</p>
        <pre className="mt-1 text-xs whitespace-pre-wrap">{output.error}</pre>
      </div>
    );
  }

  const { score_name, total_items_analyzed, contradictions_found, topics = [] } = output;

  return (
    <div className="space-y-1">
      {/* Summary header */}
      <div className="flex items-start justify-between gap-4 flex-wrap pb-2">
        <div>
          <h3 className="text-base font-semibold">{score_name}</h3>
          <p className="text-sm text-muted-foreground mt-0.5">
            {contradictions_found} contradiction{contradictions_found !== 1 ? 's' : ''} found
            {' '}across {total_items_analyzed} feedback item{total_items_analyzed !== 1 ? 's' : ''}
          </p>
        </div>
        <Badge variant={contradictions_found > 0 ? 'destructive' : 'secondary'} className="shrink-0">
          {contradictions_found > 0
            ? `${Math.round((contradictions_found / Math.max(total_items_analyzed, 1)) * 100)}% contradiction rate`
            : 'No contradictions'}
        </Badge>
      </div>

      {topics.length === 0 && contradictions_found === 0 && (
        <p className="text-sm text-muted-foreground">
          All feedback items appear consistent with the score guidelines.
        </p>
      )}

      {topics.map((topic) => (
        <TopicSection key={topic.label} topic={topic} />
      ))}
    </div>
  );
};

export default FeedbackContradictions;
