export default function EvaluateScorePage() {
  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">Evaluate a Score</h1>
      <p className="text-lg text-muted-foreground mb-8">
        Learn how to run evaluations using individual scores or complete scorecards.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">Quickstart: Evaluate Latest Associated Dataset</h2>
          <pre className="bg-muted p-4 rounded-lg overflow-x-auto">
            <code>{`# Build/update dataset for the score
plexus score dataset-curate \\
  --scorecard "CMG EDU" \\
  --score "Identify Objections" \\
  --max-items 100 \\
  --days 180

# Evaluate against the latest associated dataset
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

        <section>
          <h2 className="text-2xl font-semibold mb-4">Running an Evaluation</h2>
          <p className="text-muted-foreground mb-4">
            You can evaluate content using individual scores or entire scorecards. The evaluation
            process analyzes your content against the defined criteria and provides detailed results.
          </p>
          
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Using the Dashboard</h3>
              <ol className="list-decimal pl-6 space-y-2 text-muted-foreground">
                <li>Select your source content</li>
                <li>Choose a scorecard or individual score</li>
                <li>Click "Run Evaluation"</li>
                <li>Monitor the evaluation progress</li>
                <li>Review the results</li>
              </ol>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Using the SDK</h3>
              <pre className="bg-muted p-4 rounded-lg mb-4">
                <code>{`from plexus import Plexus

plexus = Plexus(api_key="your-api-key")

# Evaluate using a specific score (accepts ID, name, key, or external ID)
evaluation = plexus.evaluations.create(
    source_id="source-id",
    score="Grammar Check"  # Can use name, key, ID, or external ID
)

# Or evaluate using an entire scorecard (accepts ID, name, key, or external ID)
evaluation = plexus.evaluations.create(
    source_id="source-id",
    scorecard="Content Quality"  # Can use name, key, ID, or external ID
)

# Get evaluation results
results = evaluation.get_results()

# Print score values
for score in results.scores:
    print(f"{score.name}: {score.value}")`}</code>
              </pre>
              
              <p className="text-muted-foreground mb-4">
                The SDK supports the flexible identifier system, allowing you to reference scorecards and scores using different types of identifiers (name, key, ID, or external ID).
              </p>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Using the CLI</h3>
              <pre className="bg-muted p-4 rounded-lg mb-4">
                <code>{`# Evaluate using a scorecard
plexus evaluate accuracy --scorecard "Content Quality" --number-of-samples 100

# List evaluation results
plexus evaluations list

# View detailed results for a specific evaluation
plexus evaluations list-results --evaluation evaluation-id`}</code>
              </pre>
              
              <p className="text-muted-foreground mb-4">
                The CLI supports the flexible identifier system, allowing you to reference scorecards using different types of identifiers (name, key, ID, or external ID).
              </p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Understanding Results</h2>
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Score Values</h3>
              <p className="text-muted-foreground">
                Numerical or categorical results for each evaluated criterion.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Explanations</h3>
              <p className="text-muted-foreground">
                Detailed reasoning behind each score's evaluation result.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Suggestions</h3>
              <p className="text-muted-foreground">
                Recommendations for improvement based on the evaluation results.
              </p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Misclassification Triage Layer</h2>
          <p className="text-muted-foreground mb-4">
            Feedback-backed evaluations include a misclassification triage layer so operators can
            quickly decide whether to optimize score logic, escalate guideline questions, fix upstream
            data quality, or investigate system issues.
          </p>
          <h3 className="text-xl font-medium mb-2">Per-item categories</h3>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground mb-4">
            <li><strong>score_configuration_problem</strong>: likely fixable in score YAML/prompt logic.</li>
            <li><strong>information_gap</strong>: primary input/context evidence is insufficient or degraded.</li>
            <li><strong>guideline_gap_requires_sme</strong>: rubric ambiguity that needs SME clarification.</li>
            <li><strong>mechanical_malfunction</strong>: execution/system failure patterns.</li>
          </ul>
          <h3 className="text-xl font-medium mb-2">Evaluation-level red flags</h3>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground mb-4">
            <li><strong>prediction_mode_collapse</strong>: misclassifications all predicted as one class.</li>
            <li><strong>mechanical_failures_present</strong>: one or more items classified as mechanical malfunction.</li>
            <li><strong>low_primary_input_coverage</strong>: at least half of analyzed items lacked primary-input context.</li>
          </ul>
          <h3 className="text-xl font-medium mb-2">How to use it in the dashboard</h3>
          <ol className="list-decimal pl-6 space-y-2 text-muted-foreground">
            <li>Open evaluation detail and review the segmented category breakdown plus red flags.</li>
            <li>Expand RCA topics to inspect item-level category, confidence, rationale, and evidence snippets.</li>
            <li>Select a score result to see the same misclassification triage context in item detail view.</li>
          </ol>
          <h3 className="text-xl font-medium mt-4 mb-2">Agent-facing payload contract</h3>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
            <li><code>misclassification_analysis.item_classifications_all</code> is the authoritative per-item triage table for coding agents.</li>
            <li><code>misclassification_analysis.analysis_scope</code> explicitly reports coverage and assignment scope.</li>
            <li><code>analysis_scope.topic_assignment_scope</code> is currently <code>exemplar_only</code>; topic IDs are only guaranteed for exemplars exposed by semantic memory.</li>
            <li><code>misclassification_analysis.category_diagnostics.information_gap</code> explains missing/degraded primary-input and missing-required-context signals when information-gap dominates.</li>
            <li>Use <code>item_classifications_all</code> for optimization decisions and next-action logic; use topics for semantic drill-down and narrative context.</li>
          </ul>
          <h3 className="text-xl font-medium mt-4 mb-2">How to inspect specifics</h3>
          <ol className="list-decimal pl-6 space-y-2 text-muted-foreground">
            <li>Use category summary cards to review representative evidence rows (item, source, quote).</li>
            <li>Click <strong>View items in score results</strong> on a category card to filter score results to that category.</li>
            <li>Use <strong>Clear category filter</strong> to return to the full score-results list.</li>
          </ol>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Batch Evaluations</h2>
          <p className="text-muted-foreground mb-4">
            You can evaluate multiple sources at once using batch processing:
          </p>
          
          <pre className="bg-muted p-4 rounded-lg mb-4">
            <code>{`# Create a batch evaluation
batch = plexus.evaluations.create_batch(
    source_ids=["source-1", "source-2", "source-3"],
    scorecard="Quality Assurance"  # Can use name, key, ID, or external ID
)

# Monitor batch progress
status = batch.get_status()

# Get results when complete
results = batch.get_results()`}</code>
          </pre>
          
          <p className="text-muted-foreground mb-4">
            Like individual evaluations, batch evaluations also support the flexible identifier system for scorecards and scores.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Deterministic Associated Dataset Workflow</h2>
          <p className="text-muted-foreground mb-4">
            For repeatable regression checks, build deterministic associated datasets and run
            evaluation directly against score-associated datasets.
          </p>
          <div className="space-y-4">
            <pre className="bg-muted p-4 rounded-lg overflow-x-auto">
              <code>{`# Build a deterministic associated dataset
plexus dataset load \\
  --source <data_source_identifier> \\
  --deterministic-order

# Or curate from qualifying feedback labels (newest-first)
plexus score dataset-curate \\
  --scorecard "CMG EDU" \\
  --score "Identify Objections" \\
  --max-items 100

# Disable balancing when pure recency sampling is preferred
plexus score dataset-curate \\
  --scorecard "CMG EDU" \\
  --score "Identify Objections" \\
  --max-items 100 \\
  --no-balance

# Or run vetted+balanced curation with report evidence
plexus score dataset-curate-vetted \\
  --scorecard "CMG EDU" \\
  --score "Identify Objections" \\
  --days 180 \\
  --max-items 100

# Evaluate against latest associated dataset for this score
plexus evaluate accuracy \\
  --scorecard "CMG EDU" \\
  --score "Identify Objections" \\
  --use-score-associated-dataset \\
  --number-of-samples 200

# Same run with machine-friendly output
plexus evaluate accuracy \\
  --scorecard "CMG EDU" \\
  --score "Identify Objections" \\
  --use-score-associated-dataset \\
  --number-of-samples 200 \\
  --json-only

# Evaluate across all associated datasets for this score
plexus evaluate accuracy \\
  --scorecard "CMG EDU" \\
  --score "Identify Objections" \\
  --use-score-associated-dataset \\
  --all-score-associated-datasets \\
  --number-of-samples 200`}</code>
            </pre>
            <p className="text-muted-foreground">
              This keeps evaluation source-agnostic once the DataSet artifact exists and enforces
              a single score-association selection path.
            </p>
            <p className="text-muted-foreground">
              The vetted workflow automatically creates fresh report evidence in the Reports tab
              before creating the associated dataset.
            </p>
            <p className="text-muted-foreground">
              The score detail page also includes an <strong>Associated Datasets</strong> panel that
              shows per-dataset row counts and label distributions from persisted build metadata.
            </p>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Evaluation Provenance Links</h2>
          <p className="text-muted-foreground mb-3">
            Evaluation detail views now surface direct provenance links for the exact score version
            and dataset used by the run.
          </p>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
            <li><strong>Score Version</strong> links directly to the tested version when <code>scoreVersionId</code> is present.</li>
            <li><strong>Dataset</strong> links directly to <code>/lab/datasets/&lt;id&gt;</code> when <code>parameters.dataset_id</code> is present.</li>
            <li>Legacy evaluations without stored provenance show <strong>Unavailable</strong> instead of inferred links.</li>
          </ul>
          <p className="text-muted-foreground mt-3">
            The Data navigation lands on <code>/lab/datasets</code> by default; browse sources at <code>/lab/data/sources</code>.
          </p>
          <p className="text-muted-foreground mt-3">
            On <code>/lab/datasets</code>, use the explicit filter modes (<code>All</code>, <code>By Score</code>,
            <code>By Source Version</code>) and standard selectors for score version and source version selection.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Optimization Workflow Runbook (50/200 Cadence)</h2>
          <p className="text-muted-foreground mb-4">
            Standard optimization workflow uses a fast random loop and a hard confirmation gate:
            <strong> n=50 </strong> for iteration speed, then <strong> n=200 </strong> before final accept decisions.
          </p>
          <pre className="bg-muted p-4 rounded-lg overflow-x-auto mb-4">
            <code>{`# Stage A: deterministic associated-dataset check
plexus evaluate accuracy \\
  --scorecard "CMG EDU" \\
  --score "Identify Objections" \\
  --use-score-associated-dataset \\
  --number-of-samples 200

# Stage B: fast random loop
plexus evaluate feedback-runner \\
  --scorecard 1039 \\
  --score 45425 \\
  --days 180 \\
  --max-samples 50 \\
  --kanbus-issue-id plx-9aa370

# Stage C: hard random gate before accept
plexus evaluate feedback-runner \\
  --scorecard 1039 \\
  --score 45425 \\
  --days 180 \\
  --max-samples 200 \\
  --kanbus-issue-id plx-9aa370`}</code>
          </pre>
          <p className="text-muted-foreground mb-3">
            Use <code>feedback-runner</code> for optimization loops. It captures evaluation ID by runner task ID,
            waits on backend evaluation status, and writes a standardized run summary comment to Kanbus when
            <code> --kanbus-issue-id</code> is provided.
          </p>
          <p className="text-muted-foreground mb-3">
            This avoids trusting local process exit and treats the evaluation record as the source of truth
            for completion, metrics, and RCA availability.
          </p>
          <p className="text-muted-foreground mb-3">
            Workflow assessments are recorded as canonical bundles (<code>candidate_assessment_bundle.v1</code>)
            with:
          </p>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground mb-3">
            <li>Identity (scorecard, score, baseline version, candidate version)</li>
            <li>Stage runs (evaluation IDs, sample protocol, status, deltas)</li>
            <li>Malfunction context (category shares, red flags, primary next action)</li>
            <li>Generalization metrics (gap and stability signals)</li>
            <li>Decision outputs (policy decision + workflow routing decision)</li>
          </ul>
          <p className="text-muted-foreground">
            Full bundle payload is persisted as an attachment; compact summary fields are persisted for fast dashboard queries.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Interpreting Workflow KPIs and Decisions</h2>
          <p className="text-muted-foreground mb-4">
            Evaluation detail now includes a <strong>Candidate assessment</strong> panel with
            compact workflow evidence. Use it to quickly decide whether to keep optimizing score
            configuration or reroute to data/SME/system work.
          </p>
          <h3 className="text-xl font-medium mb-2">How to read stage evidence</h3>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground mb-4">
            <li><strong>Deterministic reference</strong>: associated-dataset check of baseline vs candidate.</li>
            <li><strong>Random iteration (n=50)</strong>: fast loop signal for iterative tuning.</li>
            <li><strong>Random gate (n=200)</strong>: required confirmation stage before accept decisions.</li>
            <li>Review per-stage baseline/candidate status and delta values before trusting the decision.</li>
          </ul>
          <h3 className="text-xl font-medium mb-2">How to read generalization KPIs</h3>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground mb-4">
            <li><strong>Baseline gap</strong> and <strong>Candidate gap</strong>: reference AC1 minus random-mean AC1 for each version.</li>
            <li><strong>Gap delta</strong>: candidate gap minus baseline gap. Positive means candidate generalized worse.</li>
            <li><strong>Random delta mean/stddev</strong>: average and stability of candidate-vs-baseline random deltas across random stages.</li>
            <li>Use these with policy thresholds (for example <code>min_reference_delta=0.01</code>, <code>max_generalization_drop=0.02</code>) for accept/reject outcomes.</li>
          </ul>
          <h3 className="text-xl font-medium mb-2">Routing guidance from malfunction context</h3>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground mb-4">
            <li><strong>score_configuration_optimization</strong>: continue YAML/code optimization loop.</li>
            <li><strong>data_remediation</strong>: information gaps dominate; improve input artifact quality or coverage first.</li>
            <li><strong>sme_guideline_clarification</strong>: guideline ambiguity dominates; resolve rubric with SMEs.</li>
            <li><strong>bug_investigation</strong>: mechanical failures dominate; investigate runtime/system issues.</li>
          </ul>
          <p className="text-muted-foreground">
            Keep deterministic associated-dataset runs and misclassification/RCA outputs together in
            review. Deterministic stages answer reproducibility, random stages answer generalization,
            and triage/RCA answers what to do next.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Coming Soon</h2>
          <p className="text-muted-foreground">
            Detailed documentation about evaluations is currently being developed. Check back soon for:
          </p>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground mt-4">
            <li>Advanced evaluation options</li>
            <li>Custom result formatting</li>
            <li>Evaluation performance optimization</li>
            <li>Result analysis techniques</li>
          </ul>
        </section>
      </div>
    </div>
  )
} 
