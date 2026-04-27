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
import type { PluggableList } from 'unified';

const markdownPlugins: PluggableList = [remarkGfm, remarkBreaks];

// ---- Types ----------------------------------------------------------------

interface Vote {
  model: 'haiku' | 'gpt';
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
  verdict?: 'contradiction' | 'aligned' | string;
  associated_dataset_eligible?: boolean;
}

interface Topic {
  label: string;
  summary?: string;
  guideline_quote?: string;
  count: number;
  exemplars: Exemplar[];
}

interface FeedbackContradictionsData {
  mode?: 'contradictions' | 'aligned' | string;
  score_name: string;
  total_items_analyzed: number;
  items_vetted?: number;
  contradictions_found: number;
  aligned_found?: number;
  selected_items_count?: number;
  topics: Topic[];
  eligible_associated_feedback_item_ids?: string[];
  eligible_count?: number;
  eligibility_rule?: string;
  source_report_block_id?: string | null;
  block_configuration?: {
    scorecard?: string;
    score?: string;
    mode?: string;
  };
  guidelines?: string | null;
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

const VotingBadges: React.FC<{ votes: Vote[]; confidence: 'high' | 'medium' | 'low'; isAlignedMode: boolean }> = ({
  votes,
  confidence,
  isAlignedMode,
}) => {
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
        const isAgreement = v.result !== null && (isAlignedMode ? v.result === false : v.result === true);
        const circleClass = v.result === null
          ? 'bg-muted text-muted-foreground'
          : isAgreement
            ? 'bg-green-200 text-green-900 dark:bg-green-800 dark:text-green-100'
            : 'bg-red-200 text-red-900 dark:bg-red-800 dark:text-red-100';
        const label = v.result === null ? '×' : (v.model === 'haiku' ? 'H' : 'G');
        const modelName = v.model === 'haiku' ? 'Haiku 4.5' : 'GPT-5.4';
        const title = v.result === null
          ? `${modelName}: call failed — no response received`
          : isAlignedMode
            ? `${modelName}: ${v.result ? 'disagree — contradiction' : 'agree — aligned'}`
            : `${modelName}: ${v.result ? 'agree — contradiction' : 'disagree — not a contradiction'}`;
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

const ExemplarRow: React.FC<{ exemplar: Exemplar; allowInvalidation: boolean; isAlignedMode: boolean }> = ({
  exemplar,
  allowInvalidation,
  isAlignedMode,
}) => {
  const [invalidated, setInvalidated] = React.useState(exemplar.is_invalid);
  const [loading, setLoading] = React.useState(false);

  const handleMarkInvalid = async () => {
    if (invalidated || loading) return;
    setLoading(true);
    try {
      const client = generateClient<Schema>();
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      await (client.models.FeedbackItem.update as any)({
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
          {allowInvalidation && (
            invalidated ? (
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
            )
          )}
        </div>
      </div>

      {/* Original explanation */}
      {exemplar.score_result_explanation && (
        <div>
          <h5 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">Original explanation</h5>
          <div className="border-l-2 border-muted-foreground/30 pl-3 text-sm text-muted-foreground prose prose-sm dark:prose-invert max-w-none">
            <ReactMarkdown remarkPlugins={markdownPlugins}>
              {exemplar.score_result_explanation}
            </ReactMarkdown>
          </div>
        </div>
      )}

      {/* Editor comment */}
      {exemplar.edit_comment && (
        <div>
          <h5 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-1">Editor comment</h5>
          <div className="border-l-2 border-muted-foreground/30 pl-3">
            <p className="text-sm text-muted-foreground">{exemplar.edit_comment}</p>
          </div>
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
            isAlignedMode={isAlignedMode}
          />
        )}
      </div>
    </div>
  );
};

// ---- Topic section ---------------------------------------------------------

const TopicSection: React.FC<{ topic: Topic; allowInvalidation: boolean; isAlignedMode: boolean }> = ({
  topic,
  allowInvalidation,
  isAlignedMode,
}) => {
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
            <ExemplarRow
              key={ex.feedback_item_id}
              exemplar={ex}
              allowInvalidation={allowInvalidation}
              isAlignedMode={isAlignedMode}
            />
          ))}
        </div>
      )}
    </div>
  );
};

// ---- Guidelines section ----------------------------------------------------

const GuidelinesSection: React.FC<{ guidelines: string }> = ({ guidelines }) => {
  const [open, setOpen] = React.useState(false);

  return (
    <div className="mb-2">
      <div className="flex items-center justify-between py-2">
        <span className="font-medium text-sm">Guidelines</span>
      </div>
      <div className="flex flex-col items-center">
        <div className="w-full h-px bg-border mb-1" />
        <button
          onClick={() => setOpen((v) => !v)}
          className="flex items-center justify-center rounded-full hover:bg-muted/50 transition-colors p-0.5"
          aria-label={open ? 'Collapse guidelines' : 'Expand guidelines'}
        >
          {open
            ? <ChevronUp className="h-3 w-3 text-muted-foreground" />
            : <ChevronDown className="h-3 w-3 text-muted-foreground" />}
        </button>
      </div>
      {open && (
        <div className="py-4 prose prose-sm dark:prose-invert max-w-none
          prose-headings:mt-4 prose-headings:mb-1
          prose-h1:text-base prose-h2:text-sm prose-h3:text-sm
          prose-p:my-1 prose-ul:my-1 prose-li:my-0">
          <ReactMarkdown remarkPlugins={markdownPlugins}>{guidelines}</ReactMarkdown>
        </div>
      )}
    </div>
  );
};

// ---- Main block component --------------------------------------------------

const CONTEXT_HEADER = `# Feedback Guideline-Vetting Report Output
#
# This report evaluates feedback items against score guidelines using shared
# multi-model voting (Haiku 4.5 + GPT-5.4 with optional tiebreakers).
#
# Structure:
#   mode: contradictions | aligned
#   score_name: The score being analyzed
#   total_items_analyzed: Number of feedback items evaluated
#   contradictions_found: Number of items flagged as contradictions or policy gaps
#   aligned_found: Number of items that were non-contradicting
#   topics: Clustered groups for the selected mode
#     Each exemplar includes:
#       - voting: Per-model votes with reasoning traces
#       - confidence: high/medium/low based on vote agreement
#       - verdict: contradiction | aligned
#       - score_result_explanation: Original AI score explanation
#       - edit_comment: Human reviewer's correction comment

`;

const FeedbackContradictions: React.FC<ReportBlockProps> = (props) => {
  const [loadedOutput, setLoadedOutput] = React.useState<FeedbackContradictionsData | null>(null);
  const [rawOutputString, setRawOutputString] = React.useState<string | null>(null);

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
        const parsed = JSON.parse(jsonText);
        setLoadedOutput(parsed);
        // Build full raw output string for code view
        setRawOutputString(CONTEXT_HEADER + JSON.stringify(parsed, null, 2));
      } catch (e) {
        console.warn('FeedbackContradictions: failed to load output attachment', e);
      }
    })();
  }, [outputCompacted, outputAttachment, loadedOutput]);

  // Pass full loaded output to ReportBlock for code view.
  // Use only rawOutput — omit compact stub fields (status, preview, output_compacted, etc.)
  // so ReportBlock's config YAML section shows block_configuration from the real output.
  const reportBlockOutput = rawOutputString
    ? { rawOutput: rawOutputString }
    : props.output;

  if (outputCompacted && !loadedOutput) {
    return <ReportBlock {...props} output={reportBlockOutput}><p className="text-sm text-muted-foreground p-4">Loading guideline-vetting data…</p></ReportBlock>;
  }

  const output: FeedbackContradictionsData | null = loadedOutput ?? parsedOutput;

  if (!output || (output as any).status === 'pending') {
    return <ReportBlock {...props} output={reportBlockOutput}><p className="text-sm text-muted-foreground p-4">Generating guideline-vetting analysis…</p></ReportBlock>;
  }

  if (output.error) {
    return (
      <ReportBlock {...props} output={reportBlockOutput}>
        <div className="text-destructive text-sm">
          <p>Error generating FeedbackContradictions block:</p>
          <pre className="mt-1 text-xs whitespace-pre-wrap">{output.error}</pre>
        </div>
      </ReportBlock>
    );
  }

  const {
    mode = 'contradictions',
    score_name,
    total_items_analyzed,
    contradictions_found,
    aligned_found = 0,
    selected_items_count = contradictions_found,
    topics = [],
    eligible_count = 0,
    guidelines,
  } = output;
  const isAlignedMode = mode === 'aligned';
  const isReadOnly = props.isReadOnly ?? false;
  const contradictionRate = Math.round((contradictions_found / Math.max(total_items_analyzed, 1)) * 100);
  const alignedRate = Math.round((aligned_found / Math.max(total_items_analyzed, 1)) * 100);

  return (
    <ReportBlock {...props} output={reportBlockOutput}>
      <div className="space-y-1">
        {/* Summary header */}
        <div className="flex items-start justify-between gap-4 flex-wrap pb-2">
          <div>
            <h3 className="text-base font-semibold">{score_name}</h3>
            <p className="text-sm text-muted-foreground mt-0.5">
              {isAlignedMode
                ? `${aligned_found} aligned item${aligned_found !== 1 ? 's' : ''} across ${total_items_analyzed} feedback item${total_items_analyzed !== 1 ? 's' : ''}`
                : `${contradictions_found} contradiction${contradictions_found !== 1 ? 's' : ''} found across ${total_items_analyzed} feedback item${total_items_analyzed !== 1 ? 's' : ''}`
              }
            </p>
            {!isAlignedMode && (
              <p className="text-xs text-muted-foreground mt-1">
                Identifies feedback edits that appear to contradict the current score guidelines — so that either the feedback can be marked invalid, or the guidelines can be updated to reflect the correct policy.
              </p>
            )}
          </div>
          <Badge
            variant={isAlignedMode ? 'secondary' : (contradictions_found > 0 ? 'destructive' : 'secondary')}
            className="shrink-0"
          >
            {isAlignedMode ? `${alignedRate}% aligned` : (contradictions_found > 0 ? `${contradictionRate}% contradiction rate` : 'No contradictions')}
          </Badge>
        </div>

        {topics.length === 0 && selected_items_count === 0 && (
          <p className="text-sm text-muted-foreground">
            {isAlignedMode
              ? 'No aligned vetted items found in this run.'
              : 'All feedback items appear consistent with the score guidelines.'}
          </p>
        )}

        {guidelines && <GuidelinesSection guidelines={guidelines} />}

        {topics.map((topic) => (
          <TopicSection
            key={topic.label}
            topic={topic}
            allowInvalidation={!isAlignedMode && !isReadOnly}
            isAlignedMode={isAlignedMode}
          />
        ))}
      </div>
    </ReportBlock>
  );
};

export default FeedbackContradictions;
