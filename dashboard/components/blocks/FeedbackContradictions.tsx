import React from 'react';
import { generateClient } from 'aws-amplify/data';
import type { Schema } from '@/amplify/data/resource';
import ReportBlock, { ReportBlockProps } from './ReportBlock';
import { ChevronDown, ChevronUp, CheckCircle } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { LabelBadgeComparison } from '@/components/LabelBadgeComparison';
import { IdentifierDisplay } from '@/components/ui/identifier-display';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';

// ---- Types ----------------------------------------------------------------

interface Vote {
  model: 'sonnet' | 'gpt';
  result: boolean | null;  // null = call failed
  // Full vote details stored in newer reports
  reason?: string;
  category?: string;
  guideline_quote?: string;
  thinking?: string;
}

interface Exemplar {
  feedback_item_id: string;
  item_id?: string | null;
  item_identifiers?: string | null;
  item_external_id?: string | null;
  initial_value: string;
  final_value: string;
  score_result_explanation?: string | null;
  edit_comment: string;
  editor_name?: string | null;
  edited_at?: string | null;
  reason: string;
  guideline_quote?: string;
  is_invalid: boolean;
  confidence?: 'high' | 'medium' | 'low';
  voting?: Vote[] | null;
}

interface Topic {
  label: string;
  summary?: string;
  guideline_quote?: string;
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

function formatTimeAgo(isoString: string | null | undefined): string {
  if (!isoString) return '';
  const diff = Date.now() - new Date(isoString).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 30) return `${days}d ago`;
  const months = Math.floor(days / 30);
  if (months < 12) return `${months}mo ago`;
  return `${Math.floor(months / 12)}y ago`;
}

// ---- Voting badges ---------------------------------------------------------

function computeConfidence(votes: Vote[]): 'high' | 'medium' | 'low' {
  if (votes.length === 0) return 'low';
  const yes = votes.filter(v => v.result === true).length;
  const no = votes.filter(v => v.result === false).length;
  const majority = Math.max(yes, no);
  const ratio = majority / votes.length;
  if (ratio === 1) return 'high';
  if (ratio >= 0.8) return 'medium';
  return 'low';
}

const VotingBadges: React.FC<{ votes: Vote[]; confidence: 'high' | 'medium' | 'low' }> = ({ votes, confidence }) => {
  const confidenceClass =
    confidence === 'high'
      ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
      : confidence === 'medium'
        ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200'
        : 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200';

  return (
    <div className="flex items-center gap-1.5 shrink-0">
      {votes.map((v, i) => {
        const showSep = i === 3;
        const circleClass = v.result === null
          ? 'bg-muted text-muted-foreground'
          : v.result
            ? 'bg-green-200 text-green-900 dark:bg-green-800 dark:text-green-100'
            : 'bg-red-200 text-red-900 dark:bg-red-800 dark:text-red-100';
        const label = v.model === 'sonnet' ? 'S' : 'G';
        const title = `${v.model === 'sonnet' ? 'Sonnet' : 'GPT-5.4'}: ${v.result === null ? 'failed' : v.result ? 'yes' : 'no'}`;
        return (
          <React.Fragment key={i}>
            {showSep && <span className="text-muted-foreground/40 text-xs mx-0.5">|</span>}
            <span
              className={`w-5 h-5 rounded-full flex items-center justify-center font-bold text-xs ${circleClass}`}
              title={title}
            >
              {label}
            </span>
          </React.Fragment>
        );
      })}
      <span className={`ml-1.5 text-xs font-medium px-1.5 py-0.5 rounded ${confidenceClass}`}>
        Confidence: {confidence}
      </span>
    </div>
  );
};

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
  const timeAgo = formatTimeAgo(exemplar.edited_at);

  return (
    <div className={`space-y-2 py-3 transition-opacity ${invalidated ? 'opacity-40' : ''}`}>
      {/* Score value comparison + action + timestamp */}
      <div className="flex items-center justify-between gap-4">
        <LabelBadgeComparison
          predictedLabel={exemplar.initial_value || '—'}
          actualLabel={exemplar.final_value || '—'}
          isCorrect={isCorrect}
          showStatus={false}
        />
        <div className="flex items-center gap-2 shrink-0">
          {timeAgo && (
            <span className="text-xs text-muted-foreground">{timeAgo}</span>
          )}
          {invalidated ? (
            <span className="flex items-center gap-1 text-xs text-muted-foreground">
              <CheckCircle className="h-3 w-3" /> Marked invalid
            </span>
          ) : (
            <Button
              variant="secondary"
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

      {/* Original explanation */}
      {exemplar.score_result_explanation && (
        <div className="border-l-2 border-muted-foreground/30 pl-3">
          <p className="text-xs font-medium text-muted-foreground mb-1">Original explanation</p>
          <div className="text-sm text-muted-foreground prose prose-sm dark:prose-invert max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>
              {exemplar.score_result_explanation}
            </ReactMarkdown>
          </div>
        </div>
      )}

      {/* Reviewer comment */}
      {exemplar.edit_comment && (
        <div className="border-l-2 border-muted-foreground/30 pl-3">
          <p className="text-xs font-medium text-muted-foreground mb-1">Reviewer comment</p>
          <p className="text-sm text-muted-foreground">{exemplar.edit_comment}</p>
        </div>
      )}

      {/* Contradiction analysis */}
      <p className="text-sm">{exemplar.reason}</p>

      {/* Guideline quote */}
      {exemplar.guideline_quote && (
        <p className="text-sm text-muted-foreground">
          <span className="font-medium text-foreground">Guideline: </span>
          &ldquo;{exemplar.guideline_quote}&rdquo;
        </p>
      )}

      <div className="flex items-center justify-between gap-2">
        <IdentifierDisplay
          identifiers={exemplar.item_identifiers ?? undefined}
          externalId={exemplar.item_external_id ?? undefined}
        />
        {exemplar.voting && exemplar.voting.length > 0 && (
          <VotingBadges
            votes={exemplar.voting}
            confidence={exemplar.confidence ?? computeConfidence(exemplar.voting)}
          />
        )}
      </div>
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
          {(topic.summary || topic.guideline_quote) && (
            <div className="py-3 space-y-1.5">
              {topic.summary && (
                <p className="text-sm text-muted-foreground">{topic.summary}</p>
              )}
              {topic.guideline_quote && (
                <p className="text-sm text-muted-foreground">
                  <span className="font-medium text-foreground">Guideline: </span>
                  &ldquo;{topic.guideline_quote}&rdquo;
                </p>
              )}
            </div>
          )}
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
      try {
        // Strip leading comment lines (context header added by backend) before parsing
        const jsonText = props.output.split('\n').filter(l => !l.startsWith('#')).join('\n');
        parsedOutput = JSON.parse(jsonText);
      } catch { /* ignore */ }
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
        // Strip leading comment lines (context header added by backend)
        const jsonText = text.split('\n').filter(l => !l.startsWith('#')).join('\n');
        setLoadedOutput(JSON.parse(jsonText));
      } catch (e) {
        console.warn('FeedbackContradictions: failed to load output attachment', e);
      }
    })();
  }, [outputCompacted, outputAttachment, loadedOutput]);

  if (outputCompacted && !loadedOutput) {
    return <ReportBlock {...props}><p className="text-sm text-muted-foreground p-4">Loading contradiction analysis data…</p></ReportBlock>;
  }

  const output: FeedbackContradictionsData | null = loadedOutput ?? parsedOutput;

  if (!output) {
    return <ReportBlock {...props}><p className="text-muted-foreground text-sm">No contradiction analysis data available.</p></ReportBlock>;
  }

  if (output.error) {
    return (
      <ReportBlock {...props}>
        <div className="text-destructive text-sm">
          <p>Error generating FeedbackContradictions block:</p>
          <pre className="mt-1 text-xs whitespace-pre-wrap">{output.error}</pre>
        </div>
      </ReportBlock>
    );
  }

  const { score_name, total_items_analyzed, contradictions_found, topics = [] } = output;

  return (
    <ReportBlock {...props}>
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
    </ReportBlock>
  );
};

export default FeedbackContradictions;
