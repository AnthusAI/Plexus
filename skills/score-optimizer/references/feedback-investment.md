# Feedback Investment and Diminishing-Returns Screen

Use this protocol to prioritize feedback-driven score work and to identify
scores where broad feedback collection may have reached diminishing returns.
It is a screening decision, not an automatic instruction to disable feedback.

## Fixed inputs

Record these inputs so the result is reproducible:

- scorecard and score identifiers
- assessment end timestamp
- recent assessment window; default: 90 complete days
- trend buckets; default: 12 complete calendar weeks
- maximum acceptable disagreement rate; default: 10%
- minimum valid feedback items; default: 200
- minimum final-label items per reachable terminal class; default: 30
- stability span; default: the latest 4 complete, non-overlapping weeks
- maximum stable disagreement-rate range; default: 5 percentage points
- maximum stable AC1 range; default: 0.05

Use a score-specific business target instead of the default disagreement target
when one has been explicitly approved. Never silently change thresholds between
scores in the same portfolio scan.

## Required evidence

For the fixed recent window, collect:

- valid feedback count `n`
- agreement and disagreement counts
- disagreement rate
- Gwet AC1
- final-label count for every reachable terminal class, including zero counts
- 95% Wilson confidence interval for the disagreement rate

For each of the fixed trend buckets, collect the same alignment metrics. The
`feedback-investment-v1` policy has no fixed weekly minimum: always expose the
bucket counts and a low-volume warning, but do not turn that warning into a
blocking gate. Do not treat a rolling point extended with older feedback as an
independent weekly observation.

Run the existing volume and alignment timeline reports over the same timestamp
boundaries. Preserve the report parameters and raw compact metric output with
the recommendation.

## Deterministic recommendation order

Apply these rules in order:

1. **Continue broad collection** when fewer than the configured minimum valid
   items exist. The evidence is not yet mature enough for a stop decision.
2. **Collect targeted scarce classes or boundaries** when the total is mature
   but any reachable terminal class has fewer than the configured minimum final
   labels. More random examples of an already dominant class are not useful
   substitutes.
3. **Pause broad collection pending repair or clarification** when the lower
   bound of the disagreement-rate confidence interval is above the maximum
   acceptable rate. Existing feedback already establishes that the score or
   rubric needs action; undirected collection should not be used to reconfirm
   the same conclusion.
4. **Reduce to periodic and drift-triggered monitoring** when the upper bound is
   at or below the maximum acceptable disagreement rate and all stability gates
   pass: the latest configured number of complete buckets are present, their
   disagreement-rate range is within the configured limit, and their AC1 range
   is within its configured limit. Report low-volume buckets as a warning, not
   a blocker.
5. **Continue broad collection** when the confidence interval crosses the
   acceptable-rate boundary or the recent buckets are unstable. More evidence
   is still capable of changing the decision.

Always report the first failed gate, all observed values, and the threshold
profile. This makes the recommendation explainable and independently
repeatable.

## Prioritizing optimization work

For scores not already classified for monitoring, begin portfolio ranking with:

```text
estimated reviewed disagreements = valid feedback count * disagreement rate
```

Then refine the order using AC1, class coverage, recent drift, rubric clarity,
business importance, and fixability. The formula estimates the size of the
reviewed problem; it is not itself a promotion or collection-stop rule.

## After a change

Do not reuse a pre-change monitoring recommendation after a champion, rubric,
or upstream scoring-path change. Start a new post-change evidence window. Keep
targeted checks for every reachable class and retain periodic or drift-triggered
review even after broad collection is reduced.
