import Link from "next/link"
import { Metadata } from "next"

export const metadata: Metadata = {
  title: "Deterministic Associated Datasets - Plexus Documentation",
  description: "How deterministic score-associated datasets work and how to use them in evaluation workflows."
}

export default function AssociatedDatasetsPage() {
  return (
    <div className="max-w-4xl mx-auto py-8 px-6 space-y-8">
      <div>
        <h1 className="text-4xl font-bold mb-4">Deterministic Associated Datasets</h1>
        <p className="text-lg text-muted-foreground">
          Deterministic associated datasets are single-score DataSet artifacts used for repeatable
          regression checks and reliable score-optimization decisions.
        </p>
      </div>

      <section className="space-y-3">
        <h2 className="text-2xl font-semibold">Quickstart</h2>
        <p className="text-muted-foreground">
          Canonical two-step flow: build an associated dataset, then evaluate against the latest one.
        </p>
        <pre className="bg-muted p-4 rounded-lg overflow-x-auto">
          <code>{`# 1) Build associated dataset from recent feedback
plexus score dataset-curate \\
  --scorecard "CMG EDU" \\
  --score "Identify Objections" \\
  --max-items 100 \\
  --days 180

# 2) Evaluate against latest associated dataset for that score
plexus evaluate accuracy \\
  --scorecard "CMG EDU" \\
  --score "Identify Objections" \\
  --use-score-associated-dataset

# Optional machine-friendly output
plexus evaluate accuracy \\
  --scorecard "CMG EDU" \\
  --score "Identify Objections" \\
  --use-score-associated-dataset \\
  --json-only`}</code>
        </pre>
      </section>

      <section className="space-y-3">
        <h2 className="text-2xl font-semibold">What They Are</h2>
        <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
          <li>Single-score datasets with fixed labels.</li>
          <li>Built from curated inputs (for example, scorecard examples and linked feedback/score results).</li>
          <li>Stored as regular DataSet records with deterministic provenance metadata.</li>
          <li>Associated to a score by <code>scoreId</code>; any score-linked dataset is an associated dataset.</li>
        </ul>
      </section>

      <section className="space-y-3">
        <h2 className="text-2xl font-semibold">Why They Matter</h2>
        <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
          <li>Eliminate drift from changing upstream records during optimization loops.</li>
          <li>Make before/after comparisons auditable and repeatable.</li>
          <li>Enable stable acceptance policy decisions when combined with random-sample generalization runs.</li>
        </ul>
      </section>

      <section className="space-y-3">
        <h2 className="text-2xl font-semibold">Label Resolution Policy</h2>
        <p className="text-muted-foreground">
          Two deterministic build paths are available:
        </p>
        <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
          <li><code>dataset load</code> path: uses deterministic label-source priority and reports skipped IDs.</li>
          <li><code>score dataset-curate</code> path: scans qualifying feedback newest-first, uses <code>FeedbackItem.finalAnswerValue</code> labels, and balances class coverage by default.</li>
          <li><code>score dataset-curate-vetted</code> path: runs aligned guideline-vetting report evidence and curates from vetted-good feedback with balancing.</li>
        </ul>
      </section>

      <section className="space-y-3">
        <h2 className="text-2xl font-semibold">Build and Assign</h2>
        <p className="text-muted-foreground">
          Build from a DataSource configuration:
        </p>
        <pre className="bg-muted p-4 rounded-lg overflow-x-auto">
          <code>{`plexus dataset load \\
  --source <data_source_identifier> \\
  --deterministic-order`}</code>
        </pre>
        <p className="text-muted-foreground">
          Or curate directly from qualifying feedback labels:
        </p>
        <pre className="bg-muted p-4 rounded-lg overflow-x-auto">
          <code>{`plexus score dataset-curate \\
  --scorecard "CMG EDU" \\
  --score "Identify Objections" \\
  --max-items 100 \\
  --days 180`}</code>
        </pre>
        <p className="text-muted-foreground">
          Balancing is enabled by default. Use <code>--no-balance</code> to keep pure recency sampling.
        </p>
        <pre className="bg-muted p-4 rounded-lg overflow-x-auto">
          <code>{`plexus score dataset-curate \\
  --scorecard "CMG EDU" \\
  --score "Identify Objections" \\
  --max-items 100 \\
  --no-balance`}</code>
        </pre>
        <p className="text-muted-foreground">
          Or run the canonical vetted workflow (report evidence first, then dataset build):
        </p>
        <pre className="bg-muted p-4 rounded-lg overflow-x-auto">
          <code>{`plexus score dataset-curate-vetted \\
  --scorecard "CMG EDU" \\
  --score "Identify Objections" \\
  --days 180 \\
  --max-items 100`}</code>
        </pre>
        <p className="text-muted-foreground">
          This command auto-runs an aligned guideline-vetting report, uses unanimously non-contradicting
          items in newest-first order, applies balancing, and returns both report and dataset IDs.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-2xl font-semibold">Use in Evaluations</h2>
        <p className="text-muted-foreground">
          Run accuracy evaluation directly against score-associated deterministic datasets:
        </p>
        <pre className="bg-muted p-4 rounded-lg overflow-x-auto">
          <code>{`plexus evaluate accuracy \\
  --scorecard "CMG EDU" \\
  --score "Identify Objections" \\
  --use-score-associated-dataset \\
  --all-score-associated-datasets \\
  --number-of-samples 200`}</code>
        </pre>
        <p className="text-muted-foreground">
          Without <code>--all-score-associated-datasets</code>, the latest associated dataset is used.
        </p>
        <p className="text-muted-foreground">
          Add <code>--json-only</code> for machine-friendly output payloads.
        </p>
        <p className="text-muted-foreground">
          Each new dataset-backed evaluation persists dataset provenance and exposes direct links in the evaluation detail view.
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-2xl font-semibold">Data Routes</h2>
        <p className="text-muted-foreground">
          Sources and datasets are exposed as separate routes for clarity.
        </p>
        <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
          <li>Default Data entrypoint: <code>/lab/datasets</code></li>
          <li>Sources: <code>/lab/data/sources</code></li>
          <li>Datasets inventory: <code>/lab/datasets</code></li>
          <li>Dataset detail: <code>/lab/datasets/&lt;datasetId&gt;</code></li>
        </ul>
      </section>

      <section className="space-y-3">
        <h2 className="text-2xl font-semibold">Datasets Filter Modes</h2>
        <p className="text-muted-foreground">
          The datasets inventory at <code>/lab/datasets</code> uses explicit filter modes with
          standard selectors and index-backed queries only.
        </p>
        <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
          <li><strong>All</strong>: account-wide newest-first dataset list.</li>
          <li><strong>By Score</strong>: scorecard/score selectors with optional score-version selector.</li>
          <li><strong>By Source Version</strong>: data source selector, then source-version selector.</li>
          <li>No raw ID text entry is required in the normal filter flow.</li>
        </ul>
      </section>

      <section className="space-y-3">
        <h2 className="text-2xl font-semibold">Score Page Visibility</h2>
        <p className="text-muted-foreground">
          The score detail page includes an <strong>Associated Datasets</strong> panel that lists datasets
          linked by <code>scoreId</code> and shows:
        </p>
        <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
          <li>Dataset creation recency</li>
          <li>Row count from persisted build metadata</li>
          <li>Label distribution as a segmented bar</li>
        </ul>
        <p className="text-muted-foreground">
          Older datasets without persisted stats are shown with an explicit “stats unavailable” message.
        </p>
      </section>

      <section className="space-y-2">
        <h2 className="text-2xl font-semibold">Related</h2>
        <div className="space-y-2">
          <Link href="/documentation/methods/evaluate-score" className="block text-primary hover:underline">
            Evaluate a Score
          </Link>
          <Link href="/documentation/concepts/evaluations" className="block text-primary hover:underline">
            Evaluations Concept
          </Link>
        </div>
      </section>
    </div>
  )
}
