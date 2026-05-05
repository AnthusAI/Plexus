"use client";

import React from "react";
import { downloadData } from "aws-amplify/storage";
import { DiffEditor, type Monaco } from "@monaco-editor/react";
import Link from "next/link";
import { ChevronDown, ChevronRight, Link as LinkIcon } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkBreaks from "remark-breaks";
import remarkGfm from "remark-gfm";
import type { PluggableList } from "unified";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { parseOutputString } from "@/lib/utils";
import {
  applyMonacoTheme,
  configureYamlLanguage,
  defineCustomMonacoThemes,
  getCommonMonacoOptions,
  setupMonacoThemeWatcher,
} from "@/lib/monaco-theme";

import ReportBlock, { ReportBlockProps, type BlockComponent } from "./ReportBlock";

const markdownPlugins: PluggableList = [remarkGfm, remarkBreaks];

interface ScorecardHistoryDiff {
  original_version_id?: string | null;
  modified_version_id?: string | null;
  original_label?: string | null;
  modified_label?: string | null;
  original?: string | null;
  modified?: string | null;
  unified_diff?: string | null;
  has_changes?: boolean;
}

interface ChampionPromotion {
  entered_at?: string | null;
  exited_at?: string | null;
  previous_champion_version_id?: string | null;
  next_champion_version_id?: string | null;
  transition_id?: string | null;
}

interface ScorecardHistoryVersion {
  version_id: string;
  score_id?: string | null;
  note?: string | null;
  branch?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  parent_version_id?: string | null;
  champion_status?: {
    is_current_champion?: boolean;
    is_champion_related?: boolean;
    promotions_in_window?: ChampionPromotion[];
  };
  diffs?: {
    code?: ScorecardHistoryDiff | null;
    guidelines?: ScorecardHistoryDiff | null;
  };
}

interface ScorecardHistoryScore {
  score_id: string;
  score_name: string;
  summary?: string | null;
  featured_version_count?: number;
  champion_version_count?: number;
  versions?: ScorecardHistoryVersion[];
}

interface ScorecardHistoryData {
  report_type?: string;
  block_title?: string;
  block_description?: string;
  scope?: "single_score" | "scorecard_all_scores";
  scorecard_id?: string | null;
  scorecard_name?: string | null;
  score_id?: string | null;
  score_name?: string | null;
  date_range?: {
    start: string;
    end: string;
  };
  summary?: {
    text?: string | null;
    champion_coverage?: "all" | "none" | "some" | string;
    featured_version_count?: number;
    champion_version_count?: number;
    scores_changed_count?: number;
  };
  scores?: ScorecardHistoryScore[];
  message?: string;
  warning?: string;
  error?: string;
  output_compacted?: boolean;
  output_attachment?: string;
}

const shortId = (value?: string | null): string => {
  if (!value) return "N/A";
  return value.length > 12 ? value.slice(0, 8) : value;
};

const formatInteger = (value: number | null | undefined): string => {
  if (value === null || value === undefined || Number.isNaN(value)) return "0";
  return Math.round(value).toLocaleString();
};

const formatDateTime = (value?: string | null): string => {
  if (!value) return "N/A";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
};

const scoreHref = (scorecardId?: string | null, scoreId?: string | null): string | null => {
  if (!scorecardId || !scoreId) return null;
  return `/lab/scorecards/${encodeURIComponent(scorecardId)}/scores/${encodeURIComponent(scoreId)}`;
};

const scoreVersionHref = (
  scorecardId?: string | null,
  scoreId?: string | null,
  scoreVersionId?: string | null
): string | null => {
  if (!scorecardId || !scoreId || !scoreVersionId) return null;
  return `${scoreHref(scorecardId, scoreId)}/versions/${encodeURIComponent(scoreVersionId)}`;
};

const RecordLink: React.FC<{ href?: string | null; label: string }> = ({ href, label }) => {
  if (!href) return null;
  return (
    <Link
      href={href}
      aria-label={label}
      title={label}
      className="inline-flex shrink-0 rounded-sm text-foreground transition-colors hover:bg-card"
      onClick={(event) => event.stopPropagation()}
    >
      <LinkIcon className="h-3.5 w-3.5" />
    </Link>
  );
};

const LinkedShortId: React.FC<{
  id?: string | null;
  href?: string | null;
  label: string;
}> = ({ id, href, label }) => (
  <span className="inline-flex min-w-0 items-center gap-1.5">
    <span className="truncate font-mono">{shortId(id)}</span>
    {id ? <RecordLink href={href} label={label} /> : null}
  </span>
);

const MarkdownText: React.FC<{ children?: string | null; testId?: string }> = ({ children, testId }) => {
  const text = children?.trim();
  if (!text) return null;
  return (
    <div className="prose prose-sm max-w-none text-foreground dark:prose-invert" data-testid={testId}>
      <ReactMarkdown remarkPlugins={markdownPlugins}>{text}</ReactMarkdown>
    </div>
  );
};

const handleDiffEditorMount = (_editor: unknown, monaco: Monaco) => {
  defineCustomMonacoThemes(monaco);
  applyMonacoTheme(monaco);
  setupMonacoThemeWatcher(monaco);
  configureYamlLanguage(monaco);
};

const coverageLabel = (value?: string | null): string => {
  if (value === "all") return "All promoted";
  if (value === "some") return "Some promoted";
  if (value === "none") return "None promoted";
  return value || "N/A";
};

const ChampionBadges: React.FC<{ version: ScorecardHistoryVersion }> = ({ version }) => {
  const status = version.champion_status || {};
  const promotionCount = status.promotions_in_window?.length || 0;

  return (
    <div className="flex flex-wrap gap-1.5">
      <Badge variant="secondary" className="border-0 bg-card">
        Starred
      </Badge>
      {status.is_current_champion ? (
        <Badge variant="secondary" className="border-0 bg-green-500/15 text-green-700 dark:text-green-400">
          Current Champion
        </Badge>
      ) : null}
      {promotionCount > 0 ? (
        <Badge variant="secondary" className="border-0 bg-blue-500/15 text-blue-700 dark:text-blue-400">
          Promoted {promotionCount}x
        </Badge>
      ) : null}
    </div>
  );
};

const DiffViewer: React.FC<{
  diff?: ScorecardHistoryDiff | null;
  language: "yaml" | "markdown";
  label: string;
  testId: string;
}> = ({ diff, language, label, testId }) => {
  const [isOpen, setIsOpen] = React.useState(false);
  const original = diff?.original || "";
  const modified = diff?.modified || "";
  const hasText = Boolean(original || modified);

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <CollapsibleTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          className="h-auto w-full justify-between rounded-lg bg-card px-3 py-2 text-left"
          aria-expanded={isOpen}
        >
          <span className="flex min-w-0 items-center gap-2">
            {isOpen ? (
              <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
            ) : (
              <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
            )}
            <span className="truncate text-sm font-medium">{label}</span>
          </span>
          <span className="ml-3 shrink-0 text-xs text-muted-foreground">
            {diff?.has_changes ? "Changed" : "No changes"}
          </span>
        </Button>
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div className="mt-2 rounded-lg bg-background p-2" data-testid={testId}>
          <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <span>{diff?.original_label || "Parent"}</span>
            <LinkedShortId id={diff?.original_version_id} label="Open original score version" />
            <span>to</span>
            <span>{diff?.modified_label || "Version"}</span>
            <LinkedShortId id={diff?.modified_version_id} label="Open modified score version" />
          </div>
          {isOpen && hasText ? (
            <div className="h-[420px] overflow-hidden rounded-lg bg-background">
              <DiffEditor
                height="100%"
                language={language}
                original={original}
                modified={modified}
                onMount={handleDiffEditorMount}
                options={{
                  ...getCommonMonacoOptions(),
                  readOnly: true,
                  renderSideBySide: true,
                  automaticLayout: true,
                  minimap: { enabled: false },
                  scrollBeyondLastLine: false,
                }}
              />
            </div>
          ) : (
            <pre className="max-h-80 overflow-auto whitespace-pre-wrap rounded-lg bg-card p-3 text-xs text-foreground">
              {diff?.unified_diff || "No diff content available."}
            </pre>
          )}
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
};

const VersionDetails: React.FC<{
  version: ScorecardHistoryVersion;
  scorecardId?: string | null;
  scoreId?: string | null;
}> = ({ version, scorecardId, scoreId }) => {
  const [isOpen, setIsOpen] = React.useState(false);
  const promotions = version.champion_status?.promotions_in_window || [];
  const versionLink = scoreVersionHref(scorecardId, scoreId, version.version_id);
  const parentLink = scoreVersionHref(scorecardId, scoreId, version.parent_version_id);

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <div className="rounded-lg bg-background">
        <CollapsibleTrigger asChild>
          <button
            type="button"
            className="flex w-full items-start justify-between gap-3 rounded-lg px-3 py-3 text-left transition-colors hover:bg-card"
            aria-expanded={isOpen}
            data-testid={`version-trigger-${version.version_id}`}
          >
            <div className="min-w-0 space-y-1">
              <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1">
                {isOpen ? (
                  <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
                ) : (
                  <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
                )}
                <span className="font-mono text-xs text-muted-foreground">{shortId(version.version_id)}</span>
                <span className="text-sm font-medium">{formatDateTime(version.created_at)}</span>
              </div>
              {version.note ? (
                <div className="line-clamp-2 text-sm text-foreground">{version.note}</div>
              ) : null}
            </div>
            <ChampionBadges version={version} />
          </button>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <div className="space-y-3 px-3 pb-3" data-testid={`version-details-${version.version_id}`}>
            <div className="grid gap-2 text-xs text-muted-foreground sm:grid-cols-2 lg:grid-cols-4">
              <div>
                <div className="font-medium text-foreground">Version</div>
                <LinkedShortId id={version.version_id} href={versionLink} label="Open score version" />
              </div>
              <div>
                <div className="font-medium text-foreground">Parent</div>
                <LinkedShortId id={version.parent_version_id} href={parentLink} label="Open parent score version" />
              </div>
              <div>
                <div className="font-medium text-foreground">Created</div>
                <div>{formatDateTime(version.created_at)}</div>
              </div>
              <div>
                <div className="font-medium text-foreground">Branch</div>
                <div>{version.branch || "N/A"}</div>
              </div>
            </div>

            {version.note ? (
              <div className="rounded-lg bg-card p-3">
                <div className="mb-1 text-xs font-medium text-muted-foreground">Version Note</div>
                <MarkdownText>{version.note}</MarkdownText>
              </div>
            ) : null}

            {promotions.length > 0 ? (
              <div className="rounded-lg bg-card p-3">
                <div className="mb-2 text-xs font-medium text-muted-foreground">Champion Promotions In Window</div>
                <div className="space-y-1 text-xs text-foreground">
                  {promotions.map((promotion, index) => (
                    <div
                      key={`${version.version_id}-${promotion.entered_at || index}`}
                      className="grid gap-1 rounded bg-background px-2 py-1 sm:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_minmax(0,1fr)]"
                    >
                      <div>{formatDateTime(promotion.entered_at)}</div>
                      <div>Previous: {shortId(promotion.previous_champion_version_id)}</div>
                      <div>Next: {shortId(promotion.next_champion_version_id)}</div>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            <div className="space-y-2">
              <DiffViewer
                diff={version.diffs?.code}
                language="yaml"
                label="Code Diff"
                testId={`code-diff-${version.version_id}`}
              />
              <DiffViewer
                diff={version.diffs?.guidelines}
                language="markdown"
                label="Guidelines Diff"
                testId={`guidelines-diff-${version.version_id}`}
              />
            </div>
          </div>
        </CollapsibleContent>
      </div>
    </Collapsible>
  );
};

const ScoreHistorySection: React.FC<{
  score: ScorecardHistoryScore;
  scorecardId?: string | null;
}> = ({ score, scorecardId }) => {
  const [versionsOpen, setVersionsOpen] = React.useState(false);
  const versions = Array.isArray(score.versions) ? score.versions : [];

  return (
    <section className="rounded-lg bg-muted px-3 py-4" data-testid={`score-history-${score.score_id}`}>
      <div className="space-y-2">
        <div className="flex min-w-0 items-start justify-between gap-3">
          <div className="min-w-0">
            <div role="heading" aria-level={3} className="text-lg font-semibold leading-none">
              {score.score_name}
            </div>
            <div className="mt-1 text-xs text-muted-foreground">
              {formatInteger(score.featured_version_count)} starred version
              {score.featured_version_count === 1 ? "" : "s"}
              {" | "}
              {formatInteger(score.champion_version_count)} champion-related
            </div>
          </div>
          <LinkedShortId id={score.score_id} href={scoreHref(scorecardId, score.score_id)} label="Open score" />
        </div>
        <MarkdownText testId={`score-summary-${score.score_id}`}>
          {score.summary || "No summary returned for this score."}
        </MarkdownText>
      </div>

      <Collapsible open={versionsOpen} onOpenChange={setVersionsOpen}>
        <CollapsibleTrigger asChild>
          <Button
            type="button"
            variant="ghost"
            className="mt-3 h-auto w-full justify-between rounded-lg bg-card px-3 py-2 text-left"
            aria-expanded={versionsOpen}
          >
            <span className="flex items-center gap-2">
              {versionsOpen ? (
                <ChevronDown className="h-4 w-4 text-muted-foreground" />
              ) : (
                <ChevronRight className="h-4 w-4 text-muted-foreground" />
              )}
              <span className="text-sm font-medium">Score Versions</span>
            </span>
            <span className="text-xs text-muted-foreground">{formatInteger(versions.length)}</span>
          </Button>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <div className="mt-2 space-y-2" data-testid={`version-list-${score.score_id}`}>
            {versions.map((version) => (
              <VersionDetails
                key={version.version_id}
                version={version}
                scorecardId={scorecardId}
                scoreId={score.score_id}
              />
            ))}
          </div>
        </CollapsibleContent>
      </Collapsible>
    </section>
  );
};

const ScorecardHistory: React.FC<ReportBlockProps> = (props) => {
  const [loadedOutput, setLoadedOutput] = React.useState<ScorecardHistoryData | null>(null);
  const [attachmentLoadError, setAttachmentLoadError] = React.useState<string | null>(null);
  const isProcessing = Boolean((props.config as any)?.isProcessing);

  let parsedOutput: ScorecardHistoryData = {};
  try {
    parsedOutput =
      typeof props.output === "string"
        ? (parseOutputString(props.output) as ScorecardHistoryData)
        : ((props.output || {}) as ScorecardHistoryData);
  } catch {
    parsedOutput = {};
  }

  React.useEffect(() => {
    if (!parsedOutput.output_compacted || !parsedOutput.output_attachment || loadedOutput) return;

    let cancelled = false;
    setAttachmentLoadError(null);

    (async () => {
      try {
        const result = await downloadData({
          path: parsedOutput.output_attachment!,
          options: { bucket: "reportBlockDetails" as any },
        }).result;
        const text = await result.body.text();
        if (!cancelled) setLoadedOutput(parseOutputString(text) as ScorecardHistoryData);
      } catch (error) {
        if (!cancelled) {
          setAttachmentLoadError(
            error instanceof Error ? error.message : "Failed to load compacted output attachment."
          );
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [loadedOutput, parsedOutput.output_attachment, parsedOutput.output_compacted]);

  const output = loadedOutput ?? parsedOutput;
  const scores = React.useMemo(
    () => (Array.isArray(output.scores) ? output.scores : []),
    [output.scores]
  );
  const isLoadingCompactedOutput =
    Boolean(parsedOutput.output_compacted) && !loadedOutput && !attachmentLoadError;
  const hasResolvedData =
    scores.length > 0 ||
    Boolean(output.summary) ||
    Boolean(output.message) ||
    Boolean(output.error) ||
    Boolean(output.warning);
  const title =
    props.name && !props.name.startsWith("block_")
      ? props.name
      : output.block_title || "Scorecard History";
  const subtitle = output.score_name
    ? `${output.scorecard_name || "Scorecard"} / ${output.score_name}`
    : output.scorecard_name || output.block_description;

  if ((isProcessing || isLoadingCompactedOutput) && !hasResolvedData) {
    return (
      <ReportBlock
        {...props}
        output={output as any}
        title={title}
        subtitle={subtitle}
        subtitleClassName="mt-1 text-lg font-semibold text-foreground"
        error={attachmentLoadError || output.error}
        warning={output.warning}
        dateRange={output.date_range}
      >
        <div className="rounded-lg bg-card p-4 text-sm text-foreground">
          Report block is processing. Scorecard history will appear when computation completes.
        </div>
      </ReportBlock>
    );
  }

  return (
    <ReportBlock
      {...props}
      output={output as any}
      title={title}
      subtitle={subtitle}
      subtitleClassName="mt-1 text-lg font-semibold text-foreground"
      error={attachmentLoadError || output.error}
      warning={output.warning}
      dateRange={output.date_range}
    >
      <div className="space-y-4">
        <div className="rounded-lg bg-card p-4">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <div className="text-sm font-semibold">History Summary</div>
            <Badge variant="secondary" className="border-0 bg-background">
              {coverageLabel(output.summary?.champion_coverage)}
            </Badge>
          </div>
          <MarkdownText testId="scorecard-history-summary">
            {output.summary?.text || output.message || "No featured score versions were created in the requested time window."}
          </MarkdownText>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-lg bg-card p-3">
            <div className="text-xs text-muted-foreground">Scores Changed</div>
            <div className="text-xl font-semibold">
              {formatInteger(output.summary?.scores_changed_count ?? scores.length)}
            </div>
          </div>
          <div className="rounded-lg bg-card p-3">
            <div className="text-xs text-muted-foreground">Starred Versions</div>
            <div className="text-xl font-semibold">{formatInteger(output.summary?.featured_version_count)}</div>
          </div>
          <div className="rounded-lg bg-card p-3">
            <div className="text-xs text-muted-foreground">Champion Related</div>
            <div className="text-xl font-semibold">{formatInteger(output.summary?.champion_version_count)}</div>
          </div>
          <div className="rounded-lg bg-card p-3">
            <div className="text-xs text-muted-foreground">Champion Coverage</div>
            <div className="text-xl font-semibold">{coverageLabel(output.summary?.champion_coverage)}</div>
          </div>
        </div>

        {scores.length > 0 ? (
          <div className="space-y-4">
            {scores.map((score) => (
              <ScoreHistorySection key={score.score_id} score={score} scorecardId={output.scorecard_id} />
            ))}
          </div>
        ) : (
          <div className="rounded-lg bg-card p-4 text-sm text-foreground">
            {output.message || "No featured score versions found in the requested time window."}
          </div>
        )}
      </div>
    </ReportBlock>
  );
};

(ScorecardHistory as BlockComponent).blockClass = "ScorecardHistory";

export default ScorecardHistory;
