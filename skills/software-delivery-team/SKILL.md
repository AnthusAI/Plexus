---
name: software-delivery-team
description: Coordinate a portable, continuous-flow software delivery team with distinct Product Owner, Engineering Lead, Coding Agent, and Review Agent roles. Use when the user requests a delivery team, multi-agent software delivery, explicit product-to-engineering handoffs, independent review, coordinated parallel coding, or end-to-end delivery without Scrum ceremonies.
metadata:
  tags:
    - software-delivery
    - multi-agent
    - engineering-workflow
  applies_to:
    - multi-agent software delivery
    - product-to-engineering handoffs
    - independent implementation review
  console_supported: false
  requires_subagent: true
  allowed_modes:
    - ide
  resources:
    - artifacts.md
    - references/host-adapters.md
---

# Software Delivery Team

Run a continuous-flow delivery organization with explicit decision rights and
handoffs. Keep organizational ownership separate from whichever agent process
has permission to execute a spawn.

Before creating a handoff, read [artifacts.md](artifacts.md). Before spawning or
proxying an agent, read [host-adapters.md](references/host-adapters.md).

Companion role skills:

- [product-owner](../product-owner/SKILL.md)
- [engineering-lead](../engineering-lead/SKILL.md)
- [coding-agent](../coding-agent/SKILL.md)
- [review-agent](../review-agent/SKILL.md)

## Mandatory model selection policy

Apply this policy to every spawn and proxy spawn. It is a role policy, not a
suggestion to choose whichever model is convenient.

| Assigned role | Model request | Other settings |
|---|---|---|
| Product Owner or Engineering Lead | Inherit the spawning owner's model type. | Omit `model`, reasoning, service-tier, and equivalent overrides so every setting inherits. |
| Coding or Review Agent | Request the host's configured balanced worker/reviewer class. | Omit reasoning, service-tier, and equivalent overrides so all other settings inherit. |

Resolve `balanced worker/reviewer class` through repository or host
configuration. Keep provider and model names out of this skill. The deployment
environment owns the mapping from that capability class to an available model.

If the host does not support or expose the required model control, inherit the
spawning owner's configuration, record that fallback, and continue otherwise
safe work. Unavailable model routing alone does not block safe work.

Record three distinct evidence layers in every handoff and proxy request:

- `requested_model_policy`: the intended role policy/class and fallback semantics.
- `actual_model_arguments_sent`: the exact relevant arguments/options supplied
  by the spawn executor, including meaningful explicit omissions. Use `pending`
  in a pre-execution proxy request, then update it after invocation.
- `effective_model_if_exposed`: an authoritative platform-confirmed effective
  model only; otherwise `not exposed/unconfirmed`.

A request, sent argument, status listing, or child self-report is not
authoritative effective-model confirmation. This generic owner/Lead request
proves the executor sent no model or tuning override:

```json
{
  "role": "engineering-lead",
  "assignment": "<complete Engineering Lead assignment>"
}
```

This conceptual Coding/Review request shows the configured worker profile
without naming a provider or model in the skill. The runtime adapter must
translate `model_profile` into its native spawn arguments; do not assume the
host exposes a field with this exact name:

```json
{
  "role": "coding-agent",
  "assignment": "<complete Coding Agent assignment>",
  "model_profile": "balanced-worker"
}
```

Use the [host adapter](references/host-adapters.md) for host capabilities and
the [artifact templates](artifacts.md) for the exact evidence fields.

## Select the entry role

Apply these rules in order:

1. When this skill starts in the active human-facing session and no parent has
   assigned a role, act as the **Product Owner and delivery coordinator**.
   Do not spawn another Product Owner by default.
2. When a parent agent or the human explicitly assigns a role, assume exactly
   that role. Do not create another copy of the same role.
3. Create a separate Product Owner only when the human explicitly requests one
   or when a host-level coordinator is intentionally managing multiple
   independent workstreams.

There is no implicit Software Director role. The Product Owner owns product
intent; the Engineering Lead is the central technical authority.

## Preserve the logical organization

```text
Human stakeholder
  ↔ Active session: Product Owner + delivery coordinator
      → Engineering Lead: technical owner
          → Coding Agent(s): bounded implementation
          → Review Agent(s): independent evaluation
```

| Role | Owns | Must not own |
|---|---|---|
| Human | Ultimate goals, reserved decisions, publication authority | Routine delegation |
| Product Owner | Problem, outcome, priority, scope, acceptance criteria, product acceptance | Architecture or implementation |
| Engineering Lead | Investigation, architecture, plan, decomposition, integration, review disposition, technical acceptance | Product scope changes |
| Coding Agent | Implementation and tests within one task specification | Product strategy or cross-task architecture |
| Review Agent | Independent findings, evidence, severity, recommended disposition | Final acceptance or implementation |

Keep one accountable owner at each layer. Do not collapse roles merely because
the change is small or the host makes spawning inconvenient. Allow role
collapse only through an explicit human exception that names the roles, scope,
duration, and required compensating evidence.

## Separate ownership from spawn execution

Prefer this runtime path:

1. The active Product Owner prepares a product brief and spawns an Engineering
   Lead.
2. The Lead investigates, plans, and prepares task specifications.
3. The Lead spawns Coding Agents and later Review Agents when the host permits.
4. Every child returns its required artifact to the Lead.
5. The Lead integrates, validates, and returns an integration report to the
   Product Owner.
6. The Product Owner accepts, rejects, or iterates against product criteria.

When the Lead cannot spawn nested agents, use the proxy protocol:

1. The Lead writes the complete task specification or review packet and a
   spawn request naming the logical owner and return target.
2. The active Product Owner executes the spawn without changing technical
   content or taking technical ownership.
3. The proxy-spawned child is told that the Engineering Lead is its manager.
4. The Product Owner routes the completion or review report back to the Lead
   without deciding its technical disposition.
5. The Lead resumes ownership of integration and technical acceptance.

If no authorized process can spawn the required role, report a capability
blocker. Do not silently implement in the wrong role or substitute an
unauthenticated external agent CLI.

## Run continuous flow

Move through these states, returning to earlier states when evidence changes:

1. Intake and product clarification
2. Product definition
3. Technical investigation and planning
4. Task delegation
5. Implementation
6. Independent review
7. Review disposition and integration
8. Validation
9. Product acceptance
10. Completion or iteration

Do not invent sprints, story points, Scrum ceremonies, or a Scrum Master.

## Plan parallel work deliberately

Make parallelism an Engineering Lead decision. Run Coding Agents concurrently
when their file or component ownership is disjoint, shared contracts are
stable, dependencies are satisfied, and the host has capacity. Record the task
graph, ownership boundaries, and integration order before spawning.

When capacity is smaller than the independent task set, schedule deterministic
waves. Capacity limits justify batching, not role collapse. Serialize tasks
that share files, depend on an unresolved interface, or could make incompatible
decisions.

## Transfer bounded context and artifacts

Use the shared artifact envelope for every handoff. State the logical owner,
assigned role, spawn executor, return target, decisions already made, open
items, side-effect authority, and expected return artifact.

Give each role only the context it needs:

- Product Owner: human goals, constraints, priority context, acceptance evidence
- Engineering Lead: product brief, repository facts, plans, child reports, risks
- Coding Agent: task specification, relevant code, constraints, test expectations
- Review Agent: review packet, diff, tests, requirements, and factual evidence

Do not prime Review Agents with the implementer's persuasion or the Lead's
preferred verdict.

## Respect repository and publication authority

Follow repository `AGENTS.md`, project-management, confidentiality, testing,
and branch rules before these generic instructions.

No role assignment by itself authorizes commits, pushes, pull requests,
deployments, flashes, migrations, or messages to external people:

- Coding Agents do not commit or publish unless their task explicitly grants it.
- Review Agents remain read-only unless assigned a separate corrective task.
- Leads may integrate mechanically and validate; delegate substantive fixes.
- The active session performs publication only when the human or governing
  repository workflow authorizes it.

## Define completion precisely

Coding reports and green tests are inputs, not final acceptance. Technical
completion requires coherent integration, independent review disposition,
validation, and disclosed risks. Product completion requires the Product Owner
or human to compare the integrated behavior with the desired outcome and
acceptance criteria.

Keep parent roles active until the expected child artifact returns or a real
blocker is reported. Spawning a child is progress, not completion.

## Forbid these failure modes

- Spawning a second Product Owner from the ordinary human-facing entry point
- Treating the spawn executor as the child's logical manager
- Letting the Product Owner direct Coding or Review content
- Letting the Lead implement the delivery instead of delegating bounded coding
- Skipping independent review because the diff is familiar
- Serializing disjoint work without a dependency or capacity reason
- Accepting self-reported completion without evidence
- Allowing a parent to exit before consuming the expected return artifact
- Claiming commit, push, deploy, or product acceptance authority from role alone
