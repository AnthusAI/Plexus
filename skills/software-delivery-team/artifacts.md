# Delivery team artifact templates

Use the smallest template that preserves decisions, authority, and evidence.

## Main-agent decision brief

```markdown
# Decision brief: <title>

## Vision and desired outcome
## Current state and evidence
## Requested action
## Value and opportunity cost
## Inversion — how this fails
## What we should not do
## Recommended path
## Alternatives
## CEO decision required
## Scope and non-goals
## Acceptance criteria
- [ ] <testable criterion>
## Constraints and reserved authority
```

## Technical investigation

```markdown
# Investigation: <title>

## Questions answered
## Evidence inspected
## Existing architecture and abstractions
## Contracts that must remain stable
## Existing tests
## Dependencies and prerequisites
## Migration or rollout concerns
## Inverted failure modes and safeguards
## Request ambiguities
## Feasibility
```

## Delivery plan

```markdown
# Delivery plan: <title>

## Approach
## Interfaces and data flow
## Risks, constraints, and actions to avoid
## Test strategy
## Rollout, observability, rollback, and security

## Task graph
| ID | Objective | Files/components | Depends on | Execution wave |
|---|---|---|---|---|

## Integration sequence
1. <step>

## Open decisions
```

## Coding Agent handoff

```markdown
Artifact: Coding task <id>
Logical owner and return target: Main Product Owner + Engineering Lead <agent id>
Assigned role: Coding Agent
requested_worker_settings: <explicit user model/effort, or economical-coding-worker profile>
actual_worker_arguments_sent: <exact arguments and meaningful omissions>
effective_worker_profile_if_exposed: <platform-confirmed profile, or not exposed/unconfirmed>
Repository/worktree: <absolute path, branch, and base>
Side-effect authority: <edit / test / commit / publish limits>
Expected return artifact: implementation completion report

# Task: <id> — <title>

## Objective
## Scope
### In scope
### Out of scope
## Files or components
## Interfaces and binding decisions
## Constraints and actions to avoid
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
## Factual notes for direct review
```

## Main-agent direct review

```markdown
# Direct review: <task or change set>

## Diff and surrounding code inspected
## Tests and validation independently verified
## Acceptance criteria
| Criterion | Evidence | Status |
|---|---|---|
## Correctness, security, reliability, and maintainability
## Integration effects
## Inversion — remaining ways this could fail
## Findings and Coding Agent revisions
## Residual risks
## Decision
Accept | Revise | Reject | Replan | Escalate to CEO
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
Suggested owner: Main delivery agent | Human
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
findings: none`. If a write fails, preserve the exact draft in session output
under `UNPOSTED`, with its intended issue and command error.

## Final delivery report

```markdown
# Delivery report: <title>

## CEO decision and intended outcome
## What was implemented
## Important product and technical decisions
## Coding Agent work and direct-review disposition
## Validation performed
## Acceptance criteria results
## Inversion risks addressed
## Deviations, limitations, and remaining risks
## Publication state
## Follow-up
```
