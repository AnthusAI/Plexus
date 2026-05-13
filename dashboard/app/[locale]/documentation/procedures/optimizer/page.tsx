import { Metadata } from "next"

export const metadata: Metadata = {
  title: "Feedback Alignment Optimizer - Plexus Documentation",
  description: "Learn how the Feedback Alignment Optimizer iteratively improves score accuracy through hypothesis-driven experimentation"
}

export default function OptimizerPage() {
  return (
    <div className="max-w-4xl mx-auto py-8 px-6">
      <h1 className="text-4xl font-bold mb-4">Feedback Alignment Optimizer</h1>
      <p className="text-lg text-muted-foreground mb-8">
        An automated procedure that iteratively improves score configurations through
        hypothesis-driven experimentation, dual-metric evaluation, and cross-cycle learning.
      </p>

      <div className="space-y-8">
        <section>
          <h2 className="text-2xl font-semibold mb-4">What Does It Do?</h2>
          <p className="text-muted-foreground mb-4">
            The Feedback Alignment Optimizer takes a score that isn&apos;t performing well and
            systematically improves it. It works by:
          </p>
          <ol className="list-decimal pl-6 space-y-2 text-muted-foreground">
            <li>Establishing a baseline measurement of current performance</li>
            <li>Analyzing <em>why</em> the score is making mistakes (root cause analysis)</li>
            <li>Proposing targeted hypotheses to fix specific error patterns</li>
            <li>Implementing and testing each hypothesis</li>
            <li>Accepting improvements and rejecting regressions</li>
            <li>Repeating until performance converges or the cycle limit is reached</li>
          </ol>
          <p className="text-muted-foreground mt-4">
            At the end, it produces three outputs: an <strong>Executive Summary</strong> (plain English
            for any audience), a <strong>Lab Report</strong> (technical action list for operators),
            and an <strong>SME Agenda</strong> (decision-formatted meeting agenda for domain experts).
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">The Optimization Cycle</h2>
          <p className="text-muted-foreground mb-4">
            Each cycle has four phases:
          </p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="border rounded-lg p-4">
              <h3 className="text-xl font-medium mb-2">Phase 1: Planning</h3>
              <p className="text-sm text-muted-foreground">
                The optimizer reviews all prior cycle results, the current root cause analysis,
                known contradictions, and item recurrence patterns. It then proposes multiple
                hypotheses targeting different error families. The number of hypotheses scales
                down after consecutive failures (4 → 2 → 1) to become more conservative.
              </p>
            </div>
            <div className="border rounded-lg p-4">
              <h3 className="text-xl font-medium mb-2">Phase 2: Implementation</h3>
              <p className="text-sm text-muted-foreground">
                Each hypothesis is implemented by editing the score&apos;s YAML configuration.
                The optimizer uses a ReAct loop (view → edit → submit → verify) with up to
                10 steps per hypothesis. After submission, a smoke test catches runtime errors
                immediately.
              </p>
            </div>
            <div className="border rounded-lg p-4">
              <h3 className="text-xl font-medium mb-2">Phase 3: Evaluation</h3>
              <p className="text-sm text-muted-foreground">
                All submitted versions are evaluated on two independent datasets: a fixed
                regression dataset (same items every cycle) and the latest human feedback.
                If no hypothesis succeeds individually, the optimizer attempts to synthesize
                the best ideas from multiple hypotheses into a combined version.
              </p>
            </div>
            <div className="border rounded-lg p-4">
              <h3 className="text-xl font-medium mb-2">Phase 4: Review</h3>
              <p className="text-sm text-muted-foreground">
                The winning version is checked against regression thresholds. If it doesn&apos;t
                regress either metric beyond safety limits, it becomes the new baseline for
                the next cycle. The decision is metric-based, not subjective.
              </p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Dual Metrics</h2>
          <p className="text-muted-foreground mb-4">
            The optimizer tracks two metrics simultaneously to prevent &ldquo;whack-a-mole&rdquo;
            improvements where fixing one set of items breaks another:
          </p>
          <div className="space-y-3">
            <div className="border-l-4 border-blue-500 pl-4">
              <h4 className="font-medium">Accuracy (Regression Dataset)</h4>
              <p className="text-sm text-muted-foreground">
                A fixed dataset built at baseline. The same items are tested every cycle.
                This prevents regression &mdash; if a change helps some items but hurts these
                known-good items, it&apos;s rejected.
              </p>
            </div>
            <div className="border-l-4 border-green-500 pl-4">
              <h4 className="font-medium">Feedback (Alignment)</h4>
              <p className="text-sm text-muted-foreground">
                The latest human feedback items. This measures real-world improvement &mdash;
                are we getting closer to what human reviewers expect?
              </p>
            </div>
          </div>
          <p className="text-muted-foreground mt-4">
            Both use <strong>AC1</strong> (Gwet&apos;s agreement coefficient) as the primary metric.
            A version is accepted only if neither metric regresses beyond safety thresholds.
          </p>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">When It Stops</h2>
          <p className="text-muted-foreground mb-4">
            The optimizer stops for one of these reasons:
          </p>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
            <li><strong>Target reached</strong> &mdash; AC1 hit the target accuracy (default 0.95)</li>
            <li><strong>Max iterations</strong> &mdash; Completed all requested cycles</li>
            <li><strong>Improvement plateau</strong> &mdash; 2 consecutive cycles with minimal improvement</li>
            <li><strong>Early stop</strong> &mdash; 5+ consecutive failed cycles (nothing works)</li>
            <li><strong>User stop</strong> &mdash; Human sent a stop signal via the dashboard</li>
          </ul>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Continuing and Branching</h2>
          <p className="text-muted-foreground mb-4">
            After a run completes, you have two options for extending the work:
          </p>
          <div className="space-y-4">
            <div>
              <h3 className="text-xl font-medium mb-2">Continue</h3>
              <p className="text-muted-foreground">
                Resume from where the optimizer left off with additional cycles. All accumulated
                state is preserved &mdash; no re-baselining, no lost context. Use this when the
                improvement trend is still positive but the run hit its cycle limit.
              </p>
              <p className="text-sm text-muted-foreground mt-2">
                Access via the ellipsis menu (&#8943;) on the procedure card in the dashboard.
              </p>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-2">Branch</h3>
              <p className="text-muted-foreground">
                Fork from a specific earlier cycle to try a completely different approach.
                Creates a new procedure with state truncated to that cycle. The original
                procedure is unchanged. Use this to A/B test strategies or recover from
                a dead-end path.
              </p>
              <p className="text-sm text-muted-foreground mt-2">
                Access via the Branch button in the expanded cycle details panel.
              </p>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Understanding the Information Collected</h2>
          <p className="text-muted-foreground mb-4">
            Beyond improving accuracy, the optimizer collects rich diagnostic information
            about <em>why</em> a score can&apos;t improve further. This is often more valuable
            than the accuracy gains themselves.
          </p>

          <div className="space-y-6">
            <div>
              <h3 className="text-xl font-medium mb-2">Contradictions</h3>
              <p className="text-muted-foreground">
                Items where human reviewers gave conflicting labels for similar content.
                These create an <strong>optimization ceiling</strong> &mdash; the AI cannot
                achieve agreement higher than what humans achieve with each other. When the
                optimizer reports a contradiction ceiling, the path forward is to reconcile
                reviewer standards, not to tune the prompt further.
              </p>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Item Recurrence Patterns</h3>
              <p className="text-muted-foreground mb-2">
                The optimizer tracks individual items across cycles to identify systemic issues:
              </p>
              <ul className="list-disc pl-6 space-y-1 text-sm text-muted-foreground">
                <li><strong>OSCILLATING</strong> (wrong → correct → wrong) &mdash; Classic sign of
                  contradictory norms. Fixing one interpretation breaks another. Often indicates
                  a label quality issue.</li>
                <li><strong>PERSISTENT</strong> (wrong in same way 3+ cycles) &mdash; Genuine policy
                  gap or an item that&apos;s genuinely ambiguous and may need human review.</li>
                <li><strong>FLIP_FLOP</strong> (wrong in different ways) &mdash; Unstable
                  classification boundary. The score is uncertain about this item.</li>
              </ul>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">Feedback Landscape Diagnostic</h3>
              <p className="text-muted-foreground">
                Every 2 cycles (after cycle 3), the optimizer generates a multi-level
                analysis of the error landscape: per-item diagnoses (why each item resists),
                cross-item patterns (anti-correlated groups where fixing one breaks another),
                temporal analysis (are errors shifting over time?), and systemic diagnosis
                (is this a prompt problem or a process problem?).
              </p>
            </div>

            <div>
              <h3 className="text-xl font-medium mb-2">End-of-Run Outputs</h3>
              <p className="text-muted-foreground mb-2">
                When the optimizer finishes, it produces three outputs written for different audiences:
              </p>
              <ul className="list-disc pl-6 space-y-1 text-sm text-muted-foreground">
                <li><strong>Executive Summary</strong>: 4-6 sentences of plain English prose.
                  Covers what improved, the main blocker, and what decisions are needed.
                  Copy-pasteable into an email or Slack message.</li>
                <li><strong>Lab Report</strong>: Technical analysis for operators and the next
                  optimizer run. Includes what happened, why it stalled, error patterns, ceiling
                  analysis, next lab actions (prompt/model/architecture), and suspected
                  mislabeled items. Feeds into the next run as prior context.</li>
                <li><strong>SME Agenda</strong>: Meeting agenda for domain experts.
                  Each item is a <em>decision to make</em> &mdash; phrased as a plain-English question
                  with examples showing what the AI said vs. what reviewers expected, concrete
                  options to choose from, and how many disputed reviews it would resolve.
                  No jargon. No AC1 numbers.</li>
              </ul>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Taking Action on Findings</h2>
          <p className="text-muted-foreground mb-4">
            Each of the three end-of-run outputs drives a different follow-up workflow:
          </p>
          <div className="space-y-6">
            <div>
              <h3 className="text-xl font-medium mb-3">From the Lab Report (operators)</h3>
              <div className="space-y-3">
                <div className="border-l-4 border-yellow-500 pl-4">
                  <h4 className="font-medium">Review flagged labels</h4>
                  <p className="text-sm text-muted-foreground">
                    The lab report identifies specific items suspected of having incorrect or
                    contradictory labels. Review these with domain experts and invalidate or
                    correct as appropriate, then re-run the optimizer.
                  </p>
                </div>
                <div className="border-l-4 border-cyan-500 pl-4">
                  <h4 className="font-medium">Try structural changes</h4>
                  <p className="text-sm text-muted-foreground">
                    If the lab report identifies a structural limit (model capability,
                    transcript format), consider input source changes, model upgrades, or
                    architectural modifications that go beyond prompt tuning.
                  </p>
                </div>
                <div className="border-l-4 border-red-500 pl-4">
                  <h4 className="font-medium">Update guidelines</h4>
                  <p className="text-sm text-muted-foreground">
                    When the lab report reveals genuine policy ambiguity (not just prompt
                    wording issues), update the score&apos;s guidelines document and re-run.
                  </p>
                </div>
              </div>
            </div>
            <div>
              <h3 className="text-xl font-medium mb-3">From the SME Agenda (domain experts)</h3>
              <div className="space-y-3">
                <div className="border-l-4 border-purple-500 pl-4">
                  <h4 className="font-medium">Run your next meeting from it</h4>
                  <p className="text-sm text-muted-foreground">
                    Forward the SME Agenda directly to your domain expert or team lead.
                    Each agenda item is already formatted as a decision question with concrete
                    examples and options — no translation needed.
                  </p>
                </div>
                <div className="border-l-4 border-indigo-500 pl-4">
                  <h4 className="font-medium">Feed decisions back as hints</h4>
                  <p className="text-sm text-muted-foreground">
                    After the meeting, feed the decisions back into the next optimizer run
                    using the <code>hint</code> parameter or by updating the score guidelines.
                    This closes the feedback loop.
                  </p>
                </div>
                <div className="border-l-4 border-green-500 pl-4">
                  <h4 className="font-medium">Address contradictions</h4>
                  <p className="text-sm text-muted-foreground">
                    If the contradiction ceiling is binding, the SME Agenda will surface
                    the specific policy questions causing it. Resolving them unblocks further
                    optimization and may require reviewer calibration.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section>
          <h2 className="text-2xl font-semibold mb-4">Thoughts on Improvement</h2>
          <p className="text-muted-foreground mb-4">
            The optimizer is evolving. Current areas of development:
          </p>
          <ul className="list-disc pl-6 space-y-2 text-muted-foreground">
            <li><strong>Structured output</strong> &mdash; Making the diagnostic and prescription
              machine-parseable so downstream workflows can trigger automatically</li>
            <li><strong>Cross-run learning</strong> &mdash; Automatically chaining one run&apos;s
              findings into the next run&apos;s context, without manual intervention</li>
            <li><strong>Contradiction resolution workflow</strong> &mdash; Auto-creating review
              tasks for flagged items instead of just reporting them</li>
            <li><strong>Long-term pattern tracking</strong> &mdash; Persisting item recurrence
              data across runs to detect norm drift over weeks and months</li>
            <li><strong>Smarter convergence</strong> &mdash; Distinguishing &ldquo;truly stuck&rdquo;
              from &ldquo;slow improvement on hard problems&rdquo; to avoid premature stopping</li>
          </ul>
        </section>

        <section className="bg-muted rounded-lg p-6">
          <h2 className="text-2xl font-semibold mb-4">Running the Optimizer</h2>
          <p className="text-muted-foreground mb-4">
            The optimizer can be triggered from the CLI, MCP tools, or the dashboard:
          </p>
          <pre className="bg-background rounded-lg overflow-x-auto">
            <div className="code-container p-4">
              <code>{`# CLI
plexus procedure run -y plexus/procedures/feedback_alignment_optimizer.yaml \\
  -s scorecard="My Scorecard" \\
  -s score="My Score" \\
  -s max_iterations=10 \\
  -s max_samples=200 \\
  -s days=730

# Key parameters:
#   days          - Feedback lookback window (default: 90)
#   max_iterations - Cycle limit (default: 3)
#   max_samples   - Items per feedback evaluation (default: 200)
#   dry_run       - Test without promoting champion (default: false)
#   hint          - Expert guidance for the optimizer`}</code>
            </div>
          </pre>
        </section>
      </div>
    </div>
  )
}
