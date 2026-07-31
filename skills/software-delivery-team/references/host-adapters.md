# Agent host adapter

Use native host primitives to preserve the simple role model. Tool names and
process nesting are transport details, not organizational authority.

## Capability check

Before delegation:

1. Identify native spawn, message, wait, resume, and interrupt primitives.
2. Confirm concurrency limits and whether agents share a filesystem or worktree.
3. Resolve the exact repository path, branch, base, and governing instructions.
4. Determine which process remains available to review returned work.
5. Resolve worker settings using the precedence below.

Do not shell out to an external agent executable merely to bypass missing
native tools or authentication.

## Coding Agent settings precedence

Resolve settings in this order:

1. **Explicit user settings:** If the user names a Coding Agent model, model
   class, effort, or equivalent tuning, pass those settings exactly when the
   host supports them. User settings override repository defaults for that
   delegation scope.
2. **Economical default:** Otherwise resolve `economical-coding-worker` through
   repository or host configuration to the simplest, lower-cost profile that is
   reasonably capable of the bounded task.
3. **Host automatic selection:** On Cursor, map the default profile to **Auto**.
   Omit the Task `model` parameter when omission expresses Auto, or select the
   explicit Auto control. Never pin a concrete model-menu value as a substitute.
4. **Uncontrollable routing:** Inherit the main session's configuration and
   disclose that the economical policy could not be enforced.

An explicit user effort setting travels with the explicit user model setting or
may be specified independently. Do not silently discard it. If a requested
combination is unsupported, report the exact translation or omission.

Do not use a cheaper profile when the bounded task demonstrably needs more
capability. Prefer splitting, narrowing, or clarifying the task before raising
cost; escalate to the user when the tradeoff is material.

Record:

- `requested_worker_settings`
- `actual_worker_arguments_sent`
- `effective_worker_profile_if_exposed`

Only authoritative platform evidence confirms the effective profile. Requests,
arguments, status listings, and child self-reports do not.

## Runtime mapping

| Required behavior | Primitive |
|---|---|
| Create bounded Coding Agent context | spawn |
| Deliver or clarify a task | message |
| Observe completion or escalation | wait |
| Continue the main agent's review | resume or follow-up |
| Stop unsafe or superseded work | interrupt |

The active main agent is always the Coding Agent's logical manager, reviewer,
and return target. There is no nested leadership or review topology.

Shared filesystems are common. Assign disjoint files before concurrent editing
and never assume a child has an isolated worktree. Start every child in the
explicitly assigned checkout.

## Coding Agent prompt requirements

Include:

1. Coding Agent role and main-agent return target
2. Paths to shared and Coding Agent skills
3. Bounded task and acceptance criteria
4. Repository/worktree path, branch, base, and governing instructions
5. Files/components owned and concurrency constraints
6. Side-effect authority
7. Required completion report
8. Escalation triggers
9. Requested worker settings
10. Actual arguments sent and authoritative effective profile if exposed

Do not include unrelated workstream state or ask the worker to decide product
priority, architecture across tasks, review disposition, or acceptance.

## Capacity and persistence

Count the active main agent against the host concurrency limit. Use remaining
slots for disjoint Coding Agents in deterministic waves. Keep the main agent
alive or resumable until it has received, inspected, and dispositioned every
expected return artifact.

## Fresh-session Outside Consultant

Do not spawn the Outside Consultant. The human opens a fresh session and
explicitly assigns that role. Its durable return path is existing Kanbus issue
comments plus a verbatim copy in the human-facing session. Consultant session
settings do not change Coding Agent worker settings.
