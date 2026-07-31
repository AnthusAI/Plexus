# Delivery team artifact templates

Use the smallest template that preserves the decision and evidence boundary.
Do not omit acceptance criteria from implementation or review packets.

## Handoff envelope

Prefix every delegated artifact with:

```markdown
Artifact: <name and version>
Logical owner: <role>
Assigned role: <role receiving the work>
Spawn executor: <agent/process that will invoke the host tool>
requested_model_policy: <owner inheritance or configured balanced-worker request; include fallback if used>
actual_model_arguments_sent: <exact relevant spawn arguments/options sent; state meaningful omitted overrides>
effective_model_if_exposed: <platform-confirmed model, or not exposed/unconfirmed>
Return target: <role or agent id>
Repository/worktree: <absolute path, branch, and base>
Decisions already made: <binding decisions>
Open items: <questions the assigned role may resolve>
Side-effect authority: <read-only / edit / test / commit / publish limits>
Expected return artifact: <completion, review, integration, or escalation report>
```

## Product brief

```markdown
# Product brief: <title>

## Problem
## Desired outcome
## Motivation
## Users or consumers
## Relevant scenarios
## Constraints
## Non-goals
## Acceptance criteria
- [ ] <testable criterion>
## Priority
## Open product questions
## Decisions already made
## Authority granted to Engineering Lead
## Escalation conditions
```

## Technical investigation

```markdown
# Investigation: <title>

## Questions answered
## Evidence inspected
## Existing architecture and abstractions
## Contracts that must remain stable
## Existing tests
## Dependencies
## Migration or rollout concerns
## Likely failure modes
## Request ambiguities
## Feasibility
```

## Engineering plan

```markdown
# Engineering plan: <title>

## Approach
## Interfaces and data flow
## Risks and constraints
## Test strategy
## Rollout, observability, and security

## Task graph
| ID | Objective | Ownership | Depends on | Execution wave |
|---|---|---|---|---|

## Integration sequence
1. <step>

## Product questions
```

## Coding task specification

```markdown
# Task: <id> — <title>

## Objective
## Scope
### In scope
### Out of scope
## Files or components
## Interfaces
## Constraints
## Acceptance criteria
- [ ] <criterion>
## Test expectations
## Dependencies
## Definition of completion
## Escalation triggers
```

## Implementation completion report

```markdown
# Completion: <task id>

## Summary
## Files or components changed
## Tests added or updated
## Validation performed
- `<command>` → <result>
## Acceptance criteria
- [x] / [ ] <criterion> — <evidence>
## Assumptions and deviations
## Known limitations
## Concerns or follow-up
## Factual notes for review
```

## Review packet

```markdown
# Review packet: <task or change set>

## Review objective
## Task specification and acceptance criteria
## Relevant requirements and constraints
## Changed files and diff
## Surrounding code to inspect
## Tests and output
## Static analysis or typecheck output
## Explicit reviewer questions
## Omit
Implementer persuasion, desired verdict, unrelated product history, and rejected
alternatives unless comparison is the review question.
```

## Review report

```markdown
# Review report: <task or change set>

## Overall assessment
## Evidence inspected
## Findings
### Blocking
### Major
### Minor
### Questions
### Suggestions
## Acceptance criteria
| Criterion | Evidence | Status |
|---|---|---|
## Recommended disposition
Accept | Accept with minor follow-up | Revise | Reject | Unable to determine
```

Severity meanings:

- **Blocking:** must resolve before technical acceptance
- **Major:** significant correctness, security, reliability, or architecture issue
- **Minor:** real but limited issue
- **Question:** clarification required to judge
- **Suggestion:** optional improvement

## Proxy spawn request

```markdown
# Proxy spawn request: <role and task>

Logical manager: Engineering Lead <agent id>
Spawn executor requested: Product Owner or host coordinator <agent id>
requested_model_policy: <owner inheritance or configured balanced-worker request; include fallback if used>
actual_model_arguments_sent: <exact relevant spawn arguments/options sent; state meaningful omitted overrides>
effective_model_if_exposed: <platform-confirmed model, or not exposed/unconfirmed>
Repository/worktree: <absolute path, branch, and base>
Role skill to load: <skill path>
Shared skill and resources to load: <paths>
Child prompt: <complete, unmodified role assignment and bounded packet>
Side-effect authority: <limits>
Expected return artifact: <artifact>
Route return to: Engineering Lead <agent id>
Concurrency and filesystem notes: <capacity, ownership, worktree>
```

## Outside consultant session brief

```markdown
# Outside consultant session brief

Fresh human-facing session confirmed: yes
Consultation anchor issue: <existing Kanbus issue id>
Focus question: <question or unscoped portfolio review>
Time horizon: <current delivery / release / portfolio>
Repository/worktree: <absolute path, branch, commit, and dirty state>
Requested session profile: <human-selected premium advisory profile>
Effective session profile if exposed: <platform-confirmed profile, or not exposed/unconfirmed>
Comment authority: existing in-scope Kanbus issues only
```

## Outside consultant targeted comment

Post no more than one of these to each affected issue in one consultation:

```markdown
## Outside consultant finding OC-<n>

Classification: Strategic contradiction | Major risk | Opportunity | Question
Evidence: <repository, code, documentation, and Kanbus facts>
Inference: <reasoning clearly separated from evidence>
What should be happening: <desired direction>
Observed divergence: <difference, or none>
Inversion — how this fails: <failure path and missing safeguard>
Recommendation: <specific advisory action>
Open question: <remaining uncertainty, or none>
Suggested owner: Product Owner | Engineering Lead | Human
Disposition required: adopt | defer | reject | investigate | not required
Anchor issue: <issue-id>
```

Use `Disposition required: adopt | defer | reject | investigate` for Strategic
contradictions and Major risks. Use `not required` for Opportunities and
Questions unless the human requests a decision.

## Outside consultant anchor synthesis

Post targeted comments first, capture their IDs or prefixes, then post this to
the consultation anchor:

```markdown
## Outside consultant advisory

Consultation scope: <focus and time horizon>
Repository reference: <path, branch, commit, and dirty state>
Requested session profile: <premium advisory profile>
Effective profile if exposed: <platform-confirmed profile, or not exposed/unconfirmed>
Evidence inspected: <documents, code, tests, history, and Kanbus issue ids>
Executive thesis: <what should be happening>
Vision and code alignment: <aligned areas and material divergence>
Inversion / pre-mortem: <how the project fails and safeguards>
Adversarial challenges: <assumptions, second-order effects, opportunity cost>
Recommended priorities: Now | Next | Later
Targeted findings:
- OC-1 — <issue-id>#<comment-id-or-prefix>
Prior advice still applicable: <references, or none>
Unmapped recommendations: <advice with no existing issue, or none>
Open questions: <questions requiring human or owner input>
Owner dispositions required: <finding ids and owners, or none>
```

If no material divergence exists, say so with evidence and use `Targeted
findings: none`. If a write fails, preserve the exact draft in session output under
`UNPOSTED`, with its intended issue and the command error.

## Integration report

```markdown
# Integration report: <title>

## What was implemented
## Important technical decisions
## Review findings and disposition
## Validation performed
## Evidence for product acceptance
## Deviations, limitations, and remaining risks
## Publication state
## Open items
```

## Product acceptance

```markdown
# Product acceptance: <title>

## Decision
Accept | Reject | Iterate
## Outcome versus desired outcome
## Acceptance criteria results
## Product rationale
## Follow-up
```
