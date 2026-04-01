import React from 'react';
import { generateClient } from 'aws-amplify/data';
import type { Schema } from '@/amplify/data/resource';
import { ReportBlockProps } from './ReportBlock';
import { ChevronDown, ChevronUp, AlertTriangle, CheckCircle } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';

// ---- Types ----------------------------------------------------------------

interface Exemplar {
  feedback_item_id: string;
  item_id?: string | null;
  initial_value: string;
  final_value: string;
  edit_comment: string;
  editor_name?: string | null;
  edited_at?: string | null;
  reason: string;
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

  return (
    <div
      className={`border rounded-lg p-3 space-y-2 text-sm transition-opacity ${
        invalidated ? 'opacity-40' : ''
      }`}
    >
      {/* Value change badges */}
      <div className="flex items-center gap-2 flex-wrap">
        <Badge variant="outline" className="font-mono text-xs">
          {exemplar.initial_value || '—'}
        </Badge>
        <span className="text-muted-foreground">→</span>
        <Badge variant="outline" className="font-mono text-xs">
          {exemplar.final_value || '—'}
        </Badge>
        {exemplar.editor_name && (
          <span className="text-muted-foreground text-xs ml-auto">
            {exemplar.editor_name}
          </span>
        )}
      </div>

      {/* Edit comment */}
      {exemplar.edit_comment && (
        <p className="text-muted-foreground italic">
          &ldquo;{exemplar.edit_comment}&rdquo;
        </p>
      )}

      {/* Contradiction reason */}
      <p className="text-foreground">{exemplar.reason}</p>

      {/* Mark invalid button */}
      <div className="flex items-center justify-between">
        <span className="text-xs text-muted-foreground font-mono break-all">
          {exemplar.feedback_item_id}
        </span>
        {invalidated ? (
          <span className="flex items-center gap-1 text-xs text-muted-foreground">
            <CheckCircle className="h-3 w-3" /> Marked invalid
          </span>
        ) : (
          <Button
            variant="outline"
            size="sm"
            className="text-xs h-6"
            disabled={loading}
            onClick={handleMarkInvalid}
          >
            {loading ? 'Saving…' : 'Mark Invalid'}
          </Button>
        )}
      </div>
    </div>
  );
};

// ---- Topic section ---------------------------------------------------------

const TopicSection: React.FC<{ topic: Topic }> = ({ topic }) => {
  const [open, setOpen] = React.useState(false);

  return (
    <div className="border rounded-lg overflow-hidden">
      <button
        className="w-full flex items-center justify-between px-4 py-3 bg-muted/30 hover:bg-muted/50 transition-colors text-left"
        onClick={() => setOpen((v) => !v)}
      >
        <span className="font-medium text-sm flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-amber-500 shrink-0" />
          {topic.label}
        </span>
        <span className="flex items-center gap-2 text-sm text-muted-foreground shrink-0 ml-4">
          <Badge variant="secondary">{topic.count}</Badge>
          {open ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        </span>
      </button>

      {open && (
        <div className="p-4 space-y-3">
          {topic.exemplars.map((ex) => (
            <ExemplarRow key={ex.feedback_item_id} exemplar={ex} />
          ))}
          {topic.count > topic.exemplars.length && (
            <p className="text-xs text-muted-foreground text-center">
              Showing {topic.exemplars.length} of {topic.count} contradictions in this cluster.
            </p>
          )}
        </div>
      )}
    </div>
  );
};

// ---- Main block component --------------------------------------------------

const FeedbackContradictions: React.FC<ReportBlockProps> = (props) => {
  const [loadedOutput, setLoadedOutput] = React.useState<FeedbackContradictionsData | null>(null);

  // Parse inline output
  let parsedOutput: FeedbackContradictionsData | null = null;
  if (props.output) {
    if (typeof props.output === 'string') {
      try { parsedOutput = JSON.parse(props.output); } catch { /* ignore */ }
    } else {
      parsedOutput = props.output as FeedbackContradictionsData;
    }
  }

  // Load compacted output from S3 attachment if needed
  const outputAttachment = (parsedOutput as any)?.output_attachment ?? null;
  const outputCompacted = (parsedOutput as any)?.output_compacted ?? false;
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

  // Show loading state while fetching compacted output
  if (outputCompacted && !loadedOutput) {
    return <p className="text-sm text-muted-foreground p-4">Loading contradiction analysis data…</p>;
  }

  const output = loadedOutput ?? parsedOutput;

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
    <div className="space-y-4">
      {/* Summary header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h3 className="text-base font-semibold">{score_name}</h3>
          <p className="text-sm text-muted-foreground mt-0.5">
            {contradictions_found} contradiction{contradictions_found !== 1 ? 's' : ''} found
            across {total_items_analyzed} feedback item{total_items_analyzed !== 1 ? 's' : ''}
          </p>
        </div>
        <Badge
          variant={contradictions_found > 0 ? 'destructive' : 'secondary'}
          className="shrink-0"
        >
          {contradictions_found > 0
            ? `${Math.round((contradictions_found / Math.max(total_items_analyzed, 1)) * 100)}% contradiction rate`
            : 'No contradictions'}
        </Badge>
      </div>

      {/* Topic sections */}
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
