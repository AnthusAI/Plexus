# Agent host adapters

Use native host primitives to preserve the logical role model. Treat tool names
and process nesting as transport details, not organizational authority.

## Capability check

Before delegation:

1. Identify native spawn, message, resume, wait, and interrupt primitives.
2. Confirm whether child agents may create nested children.
3. Confirm concurrency limits and whether agents share a filesystem or worktree.
4. Confirm which process remains available to route return artifacts.
5. Resolve the exact repository/worktree path, branch, and base for all work.
6. Record the result in the Engineering Lead plan.

Do not test capability by starting side-effectful work. Do not shell out to an
external agent CLI merely to bypass missing native tools or authentication.

## Model-selection and evidence policy

Select the requested model by assigned role:

| Assigned role | Request |
|---|---|
| Product Owner or Engineering Lead | Inherit the spawning owner's model type and all settings: omit model, reasoning, service-tier, and equivalent overrides. |
| Coding or Review Agent | Request the host's balanced worker class; inherit reasoning and all other settings. |

Resolve the balanced-worker request through repository or host configuration.
The configuration may use a capability alias, model profile, policy rule, or
native automatic selection (on Cursor: **Auto**). Treat `balanced-worker` as a
capability name, not a required native API value or field name; translate it
via the host section below. If the host does not support model selection,
inherit the spawning owner's configuration, record the fallback in
`requested_model_policy`, and do not block safe work solely on unavailable
model routing.

Record all three evidence layers in every handoff or proxy artifact:

- `requested_model_policy`: intended role policy/class and fallback semantics.
- `actual_model_arguments_sent`: exact relevant arguments/options actually
  supplied by the spawn executor, including meaningful explicit omissions.
- `effective_model_if_exposed`: authoritative platform-confirmed effective
  model only, or `not exposed/unconfirmed`.

A request, sent argument, status listing, or child self-report is not
effective-model confirmation.

## Fresh-session Outside Consultant

Do not create the Outside Consultant with a spawn, Task, child, background
agent, proxy, or external agent executable. The human opens a fresh session and
explicitly assigns the role before analysis begins.

The human selects a premium advisory profile suitable for high-level strategic
reasoning. Record the requested profile and only authoritative effective-profile
evidence. If the platform does not expose the effective profile, use `not
exposed/unconfirmed` and continue.

On Cursor, the existing Auto rule remains mandatory for spawned Coding and
Review agents. It does not select the Outside Consultant's fresh-session
profile. Do not pin or alter worker models while configuring a consultation.

The consultant has no spawn topology, logical manager, child return route, or
delivery capacity slot. Its durable return path is existing Kanbus issue
comments plus a verbatim copy in the human-facing session.

## Cursor IDE (Task subagents)

This repository is commonly driven from Cursor. Map role policy to Cursor Task
spawns as follows — **do not improvise by pinning a vendor model slug**.

| Role policy | Cursor Task behavior |
|---|---|
| Inherit (Product Owner, Engineering Lead) | **Omit** the Task `model` parameter entirely so the child inherits the parent session (typically Auto when the human-facing session is Auto). |
| Balanced worker / reviewer (Coding, Review) | Use Cursor **Auto**: omit `model` as well when that is how this host expresses Auto inheritance from an Auto parent; if the host exposes an explicit Auto control for subagents, select **Auto** only — never a concrete slug from the Task model enum. |

**Forbidden misunderstanding:** Concrete vendor model enum entries are **not**
the balanced-worker mapping. Choosing one because it “looks like a default
worker” violates this adapter. `model_profile: "balanced-worker"` in skill prose
means Cursor **Auto** / omit-`model` inheritance — **not** “pick any slug from
the enum.”

When recording evidence for Cursor Task spawns:

- `requested_model_policy`: `owner inheritance` or `balanced-worker → Cursor Auto`
- `actual_model_arguments_sent`: e.g. `Task: model omitted (Auto inherit)` or
  `Task: Auto` if an explicit Auto argument exists
- `effective_model_if_exposed`: `not exposed/unconfirmed` unless Cursor shows
  an authoritative effective model for the child

Proxy spawns from the Product Owner must follow the same omit-`model` / Auto
rules the Lead requested — do not “helpfully” add a pinned slug.

## Runtime adapter

Map the host to these primitives:

| Required behavior | Primitive |
|---|---|
| Create isolated role context | spawn |
| Deliver a bounded artifact | message |
| Continue the logical owner | resume or follow-up |
| Observe completion or escalation | wait |
| Stop unsafe or superseded work | interrupt |

If the host lacks nested spawn but has a top-level spawn executor, use the proxy
protocol. If it lacks any authorized spawn primitive, stop at the completed
brief, plan, or packet and report the capability blocker.

For Product Owner and Engineering Lead spawns, omit model and setting
overrides (Cursor: omit Task `model` → inherit / Auto). For Coding and Review
spawns, resolve `balanced-worker` to Cursor **Auto** (omit Task `model` or
explicit Auto only — never a pinned enum slug) and inherit other settings.
Record the configuration source and actual arguments used. If unavailable or
uncontrollable, inherit the spawning owner's configuration and record the
fallback. Record only platform-confirmed effective-model evidence; otherwise
use `not exposed/unconfirmed`.

Use native spawn, wait, message, resume, and interrupt primitives. Treat nested
spawn availability as a capability to detect, not an assumption. Do not invoke
an external agent executable merely to bypass missing native tools or
authentication.

Child agents may spawn nested roles when the host permits. If the Lead cannot,
return a proxy spawn request to the active Product Owner. Shared filesystems are
common, so assign disjoint files before concurrent editing and never assume an
agent has an isolated worktree.

Start every child in the explicitly assigned worktree. Never infer the target
checkout from the spawning process's current directory when multiple checkouts
exist.

## Child prompt requirements

Include all of the following in every spawn prompt:

1. Assigned role and logical manager
2. Paths to the shared skill, assigned role skill, and required resources
3. Bounded input artifact and acceptance criteria
4. Exact repository/worktree path, branch, base, and governing instructions
5. Side-effect authority, including commit and publication limits
6. Expected return artifact and exact return target
7. Escalation triggers
8. Requested model policy and any fallback
9. Actual model arguments sent, including meaningful omitted overrides
10. Effective model only if authoritatively exposed by the platform

Do not include the full stakeholder transcript, implementer persuasion for a
reviewer, or unrelated workstream state.

## Capacity and persistence

Count the active Product Owner and Engineering Lead against host concurrency
limits. Run independent Coding Agents in as many parallel slots as remain, then
use deterministic waves. Run Review after a coherent diff exists and coding
slots have been released.

Keep the logical parent alive or explicitly resumable. A spawned child without
a known return route is an orphaned workstream, not delegation.
