# Semantic-budget production pilot checklist

This is an operator packet for a bounded, read-only portfolio pilot. It stores
only Plexus platform evidence; do not put client names, raw prompts, source
content, or opaque identifiers in this checklist.

## Deployment order

Follow **Tactus release/main -> Plexus pin/lock -> local/sandbox -> production
read-only**. The Tactus release must be published and verified before the
Plexus dependency is pinned and locked. Local/sandbox acceptance must use that
released package before a production read-only pilot is considered.

Any checks that import the local cross-repository Tactus checkout are
**pre-release cross-repo source tests only**. The production/full release validation is blocked
until the Tactus release is published and verified and
the Plexus pin/lock is regenerated and installed without a source override.

## Before provider contact

- Record the explicitly verified operator identity and budget, including the account/session scope.
- Record the separately authorized optimizer `max_cost_usd` and decimal-string
  semantic `max_semantic_cost_usd`; neither substitutes for the other.
- Record `max_semantic_diagnoses`, the exact immutable model, and pricing
  policy/version. These are visible run policy, not caller-overridable model
  selection.
- Confirm the pilot is read-only: no score, guideline, feedback, champion, or
  production configuration mutation is authorized.
- Confirm there are **No new GraphQL resources**. Use existing Report, Task,
  blocks, and artifact persistence attachments only.

## Evidence and exit criteria

- Verify the cover page, workbook, and immutable artifact show the same
  Decimal-string authorized, settled, held, and available semantic amounts.
- Verify call counts reconcile for reserved, settled, unknown, and cancelled
  outcomes, and that deferred/exhausted diagnosis work is shown as incomplete.
- Verify the exact ledger reference and digest are present without raw prompts,
  client content, provider request IDs, or target IDs.
- Treat an unknown outcome, budget exhaustion, or incomplete diagnosis as a
  failure/next action. Never label it analysis-ready or create an
  optimization-ready target from it.
