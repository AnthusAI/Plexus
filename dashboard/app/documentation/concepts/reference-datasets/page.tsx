import Link from "next/link"
import { Metadata } from "next"

export const metadata: Metadata = {
  title: "Deterministic Associated Datasets - Plexus Documentation",
  description: "How deterministic score-associated datasets work and how to use them in evaluation workflows."
}

export default function ReferenceDatasetsPage() {
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
          <li><code>score dataset-curate</code> path: scans qualifying feedback newest-first and uses <code>FeedbackItem.finalAnswerValue</code> labels.</li>
          <li><code>score dataset-curate --feedback-item-ids</code> path: builds from an explicit vetted snapshot of feedback IDs.</li>
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
          Or curate from an explicit vetted snapshot:
        </p>
        <pre className="bg-muted p-4 rounded-lg overflow-x-auto">
          <code>{`plexus score dataset-curate \\
  --scorecard "CMG EDU" \\
  --score "Identify Objections" \\
  --feedback-item-ids "<id1>,<id2>,<id3>"`}</code>
        </pre>
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
