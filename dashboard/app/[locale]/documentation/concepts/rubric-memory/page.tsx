import { Button as DocButton } from "@/components/ui/button"
import Link from "next/link"
import { Metadata } from "next"

export const metadata: Metadata = {
  title: "Rubric Memory - Plexus Documentation",
  description: "Learn how Plexus scorecard knowledge bases provide rubric memory for agents, reports, and optimizer workflows."
}

export default function RubricMemoryPage() {
  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">Rubric Memory</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Rubric memory is a local scorecard knowledge-base convention for giving Plexus agents
        and reports relevant policy history, scripts, meeting notes, emails, and other source
        material while keeping the active ScoreVersion rubric as the official authority.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">Authority Model</h2>
          <p className="text-muted-foreground mb-4">
            The official policy authority for score-level analysis is the active score version,
            usually the champion version referenced by <code>Score.championVersionId</code>.
            Corpus material can explain interpretation, history, rationale, exceptions, or gaps,
            but it cannot silently override the official rubric.
          </p>
          <p className="text-muted-foreground">
            Plexus is moving toward <strong className="text-foreground">rubric</strong> as the
            domain term. Some storage fields are still named <code>guidelines</code>, and the
            rubric-memory boundary translates those fields into rubric terminology.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Folder Structure</h2>
          <p className="text-muted-foreground mb-4">
            Knowledge-base folders live beside the pulled score artifacts. They use the same
            sanitized score file names as local score YAML and Markdown files, so the relationship
            between a score and its knowledge base is visible in the file tree.
          </p>
          <pre className="bg-muted rounded-lg mb-4 overflow-x-auto">
            <div className="code-container p-4">
              <code>{`<SCORECARD_CACHE_DIR>/
  <Scorecard Name>/
    scorecard.knowledge-base/
    <Prefix>.knowledge-base/
    <Score Name Stem>.knowledge-base/
    <Score Name Stem>.yaml
    <Score Name Stem>.md`}</code>
            </div>
          </pre>
          <p className="text-muted-foreground mb-4">
            For example, with <code>SCORECARD_CACHE_DIR=dashboard/scorecards</code>, the score
            <code> Medication Review: Dosage</code> in <code>SelectQuote HCS Medium-Risk</code>
            uses this score-level knowledge-base folder:
          </p>
          <pre className="bg-muted rounded-lg overflow-x-auto">
            <div className="code-container p-4">
              <code>{`dashboard/scorecards/SelectQuote HCS Medium-Risk/Medication Review- Dosage.knowledge-base/`}</code>
            </div>
          </pre>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Scope Levels</h2>
          <p className="text-muted-foreground mb-4">
            A retrieval request combines the canonical roots that apply to the score:
          </p>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
            <li>
              <strong className="text-foreground">Score:</strong> exact score-level material from
              <code> &lt;Score Name Stem&gt;.knowledge-base/</code>.
            </li>
            <li>
              <strong className="text-foreground">Prefix:</strong> shared material from matching
              folders such as <code>Information Accuracy.knowledge-base/</code>.
            </li>
            <li>
              <strong className="text-foreground">Scorecard:</strong> broad material from
              <code> scorecard.knowledge-base/</code>.
            </li>
          </ul>
          <p className="text-muted-foreground mt-4">
            Ranking prefers score-specific evidence first, prefix evidence second, and scorecard
            evidence third. Prefix folders are optional overlays, not fallback search locations.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Prefix Knowledge Bases</h2>
          <p className="text-muted-foreground mb-4">
            Prefix knowledge bases support groups of related scores. This is useful when a scorecard
            contains a composite concept and many sub-element scores, such as
            <code> Information Accuracy: High-Pressure Sales Tactics</code>.
          </p>
          <pre className="bg-muted rounded-lg mb-4 overflow-x-auto">
            <div className="code-container p-4">
              <code>{`SelectQuote HCS Medium-Risk/
  Information Accuracy.knowledge-base/
  Information Accuracy- High-Pressure Sales Tactics.yaml
  Information Accuracy- High-Pressure Sales Tactics.knowledge-base/
  Information Accuracy (Composite).yaml`}</code>
            </div>
          </pre>
          <p className="text-muted-foreground">
            A prefix folder matches when its stem is a leading prefix of the sanitized score name at
            a clear boundary, such as a space, hyphen, or parenthesis. Exact score folders and
            <code> scorecard.knowledge-base</code> are excluded from prefix matching to avoid duplicates.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Date Folders</h2>
          <p className="text-muted-foreground mb-4">
            Temporal source metadata comes from folder names. Put raw files under the date of the
            meeting, email, chat, or document. Use <code>unknown-date</code> when no date is known.
          </p>
          <pre className="bg-muted rounded-lg mb-4 overflow-x-auto">
            <div className="code-container p-4">
              <code>{`Medication Review- Dosage.knowledge-base/
  2026-04-24/
    meeting-notes.md
    client-email.txt
  unknown-date/
    pasted-notes-without-date.md`}</code>
            </div>
          </pre>
          <p className="text-muted-foreground">
            Plexus infers <code>source_timestamp</code> from the nearest ancestor folder matching
            <code> YYYY-MM-DD</code>, including nested paths such as
            <code> 2026-04-24/client/source.md</code>. Unknown-date files remain retrievable, but
            they do not contribute to chronological history ordering.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Prepared Corpora</h2>
          <p className="text-muted-foreground mb-4">
            Raw knowledge-base folders are the source of truth and are never rewritten. At runtime,
            Plexus prepares a working Biblicus corpus under ignored local storage:
          </p>
          <pre className="bg-muted rounded-lg mb-4 overflow-x-auto">
            <div className="code-container p-4">
              <code>{`tmp/rubric-memory/prepared/<stable-cache-key>/`}</code>
            </div>
          </pre>
          <p className="text-muted-foreground mb-4">
            The prepared cache stores copied source files, sidecar metadata, source roots, file
            counts, retriever id, schema version, fingerprint, and prepared timestamp. The same
            preparation path runs just in time during retrieval and through the prewarm command:
          </p>
          <pre className="bg-muted rounded-lg overflow-x-auto">
            <div className="code-container p-4">
              <code>{`SCORECARD_CACHE_DIR=dashboard/scorecards plexus rubric-memory prewarm \\
  --scorecard "SelectQuote HCS Medium-Risk" \\
  --score "Medication Review: Dosage"`}</code>
            </div>
          </pre>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Two Products</h2>
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Retrieval-Only Citation Context</h3>
              <p className="text-muted-foreground">
                This is input to an LLM call. Plexus retrieves official rubric authority and relevant
                corpus snippets, assigns citation IDs, separates chronological memory from
                relevance-ranked evidence, and injects the context into an existing agent or report
                prompt. It does not add another synthesis agent.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Rubric Evidence Pack</h3>
              <p className="text-muted-foreground">
                This is an optional structured analysis output. It uses retrieval plus a Tactus
                synthesis step to produce a deeper explanation with rubric reading, evidence
                classification, history of change, likely disagreement reason, confidence, and open
                questions. It is appropriate for drill-through analysis, not default high-volume
                per-item report voting.
              </p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Using Evidence Responsibly</h2>
          <p className="text-muted-foreground mb-4">
            Agents should cite rubric-memory evidence when they make policy claims. If corpus
            evidence answers a question but the rubric is unclear, the right SME question is not
            "What is the policy?" It is "Should the rubric be updated to explicitly say this?"
          </p>
          <p className="text-muted-foreground">
            Sparse, conflicting, or undated evidence should lower confidence and produce open
            questions instead of confident policy conclusions.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Next Steps</h2>
          <div className="flex gap-4">
            <Link href="/documentation/concepts/scores">
              <DocButton variant="outline">Review Scores</DocButton>
            </Link>
            <Link href="/documentation/concepts/reports">
              <DocButton>Review Reports</DocButton>
            </Link>
          </div>
        </section>
      </div>
    </div>
  )
}
