---
name: plexus-score-optimizer
description: Run, debug, and steer the Plexus feedback-alignment optimizer from the direct CLI, including contradiction analysis, SME rubric questions, and approval-gated feedback invalidation.
---

# Plexus Score Optimizer

Use this skill when the task is to run, monitor, debug, or steer a feedback-alignment optimization procedure for a Plexus score.

Examples below assume you are in the repo root and are using `python -m plexus.cli`. If your shell does not provide `python`, replace it with the repo's Python interpreter.

## Purpose and Optimization Mindset

The optimizer is not just a code-tuning loop. Its job is to move a measurable needle such as alignment, AC1, accuracy, precision, recall, or cost efficiency.

That work usually falls into three lanes:

1. Improve the score logic or prompt under the current rubric.
2. Identify rubric gaps, policy ambiguities, or clarification questions for stakeholders and SMEs.
3. Identify feedback items that appear inconsistent with the rubric expressed in the current guidelines or newer SME decisions.

This is how optimization can "move the goal posts" in a disciplined way:

- The iterative metacognitive loop tries to improve a quantifiable metric.
- Contradiction analysis shows where the current feedback set may not match the current rubric.
- SME questions help refine the rubric when the current guidelines are underspecified or outdated.
- Approved feedback invalidation removes labels that were created under a different rubric or were simply applied incorrectly.

Do not treat every contradiction as a score bug. A contradiction can mean:

- the score needs to change
- the rubric needs clarification
- the feedback should be invalidated
- the item is mechanical noise and should not drive optimization

## Hard Guardrails

- Use the direct CLI for optimizer execution and debugging. Do not treat dashboard or dispatcher state alone as proof that a run is healthy.
- Prefer `python -m plexus.cli` from the repo root over a possibly stale installed `plexus` binary.
- Capture stdout/stderr with `tee` for real runs so you keep the traceback and early procedure/task IDs.
- Baseline evaluations are the real start of meaningful optimizer work. Procedure creation alone is not.
- Never invalidate feedback automatically.
- Never invalidate feedback just because a contradictions report flagged an item.
- Always discuss candidate invalidation groups with the user first.
- Only invalidate items after the user explicitly approves the exact group.
- Start invalidation triage from contradiction report output, not ad hoc individual item inspection.
- Use MCP for inspection around the optimizer when helpful, but not as the primary execution path during debugging.
- When you prepare a score for optimizer work with `python -m plexus.cli score push`, remember that CLI-published guidelines come from `scorecards/<scorecard>/guidelines/<score>.md`. A sidecar markdown file next to the YAML is not the canonical guidelines path for CLI push.

## Direct CLI as Source of Truth

During development and debugging, the direct CLI log is the source of truth:

```bash
python -m plexus.cli procedure optimize ...
```

Do not infer optimizer health from:

- a dashboard `RUNNING` badge
- dispatcher state
- a task record without matching local process evidence

If a run exits unexpectedly, capture and report the exact CLI traceback before proposing fixes.

## Preferred Normal Launch Path With `procedure optimize`

### What `procedure optimize` actually does

The convenience command wraps the feedback-alignment optimizer procedure YAML. A normal run does this:

1. Creates a new `Procedure` record.
2. Creates or reuses a `Task` plus dashboard stages.
3. Starts a Tactus runtime and a procedure chat session.
4. Pulls the starting score version locally.
5. Refreshes the contradictions report in the background.
6. Looks for reusable baselines.
7. If baselines are not reused, runs two fresh baseline evaluations in parallel:
   - regression baseline: accuracy evaluation on the associated deterministic dataset
   - recent baseline: feedback evaluation on recent human-reviewed items
8. If baselines succeed, proposes hypotheses, edits the score, submits candidate versions, evaluates them, compares deltas, and repeats up to `max_iterations`.

Default optimization objective is alignment. If you need a non-default objective such as precision or recall variants, use the manual procedure/YAML path instead of assuming the convenience CLI can switch objectives for you.

### Identifier resolution

`--scorecard` and `--score` use shared resolvers. You can pass any of these if they uniquely resolve:

- DynamoDB ID
- external ID
- name
- key

Do not waste time resolving UUIDs manually unless there is an ambiguity or you need the exact resolved ID for debugging.

### Recommended run command

```bash
ts=$(date +%Y%m%d-%H%M%S)
log=/tmp/optimizer-$ts.log
python -m plexus.cli procedure optimize \
  --scorecard "<scorecard>" \
  --score "<score>" \
  --days <days> \
  --max-samples <max_samples> \
  --max-iterations <max_cycles> \
  --version "<start_version>" \
  --resume-recent-eval "<resume_recent_eval>" \
  --resume-regression-eval "<resume_regression_eval>" \
  --hint "<hint>" \
  2>&1 | tee "$log"
```

Only include the optional flags that are actually needed.
Pass `--max-samples` explicitly instead of relying on the CLI default. If the user does not specify a sample cap, use `200`.

## How To Read A Live Run and Spot Real Progress

Things you should expect to see early in the log:

- `Starting feedback alignment optimization...`
- `Created Task ... for procedure ...`
- `Running optimization procedure...`
- `Starting procedure run for procedure ID: ...`
- `Chat session created: ...`
- `Running 2 fresh baseline evaluation(s) ...`

If you do not see baseline reuse or baseline evaluations dispatch, the optimizer has not really started doing the important work yet.

Treat the following as high-signal failure modes:

- A contradictions report refresh near cycle 0 is not the baseline itself. Do not mistake report generation for successful baseline execution.
- If a baseline evaluation fails, stop and inspect the direct CLI log for the first concrete exception, not just the final dashboard status.
- Use the item, content, and feedback identifiers from the first failure to inspect the bad record or bad score code.
- The contradictions report may already be complete even if the shell wrapper still looks busy. Check the emitted report metadata before rerunning it.
- GPT-5-class models can return empty or partial completions when `max_tokens` or `max_output_tokens` is too low. If you see `No completion received from LLM`, truncated outputs, or retries with blank responses, inspect the score's token budget immediately.
- Invalidation triage must start from contradiction report output, not from ad hoc item-by-item reconstruction.

## Process Lookup and Kill Workflow

When a user says an optimizer is still running and needs to die, start with live local process evidence:

```bash
ps -o pid,ppid,etime,command -ax | rg "<procedure-id>|procedure optimize|procedure run|<score name>"
```

Do not narrow this search too aggressively. Older or wrapper-style launches can appear as:

- `python -m plexus.cli procedure optimize ...`
- `python -m plexus.cli procedure run ...`
- `python -c ... score.main(args=['optimize', ...])`

Expected outcomes:

- If a matching local PID exists, it is a local CLI-owned run and can be terminated locally.
- If no matching local PID exists, do not assume the dashboard `RUNNING` state means a local process still exists on this host.
- If there is fresh procedure chat activity but no local PID, the run may be executing on another host or only persisted state may still be alive.

Safe stop sequence:

1. Send `TERM` to the exact confirmed PID:

```bash
kill <pid>
```

2. Re-check with `ps`:

```bash
ps -o pid,ppid,etime,command -ax | rg "<pid>|<procedure-id>|<score name>"
```

3. Only if the exact PID ignores `TERM`, escalate:

```bash
kill -9 <pid>
```

Important limitations:

- `python -m plexus.cli procedure show <procedure-id>` does not currently expose runtime PID or host information.
- For non-stale runs, PID correlation may require `ps` plus direct CLI log correlation rather than a single CLI lookup command.
- Killing a local PID stops the process. It does not by itself rewrite database state from `RUNNING` to `STALLED` or `FAILED`.

## Stale-Timeout Workflow

Use stale-timeout when you need to decide whether persisted `RUNNING` procedures are actually stalled.

Manual dry-run command:

```bash
python -m plexus.cli procedure timeout-stale \
  --threshold-seconds <seconds> \
  --lookback-hours <hours> \
  --dry-run \
  -o json
```

What stale-timeout uses:

- latest procedure chat activity timestamp
- fallback to `task startedAt` if there is no chat yet

How to read the output:

- `timed_out` means the procedure would be marked `STALLED`
- `skipped` with `fresh_chat_activity` means the procedure is still considered active
- `skipped` with `fresh_no_chat_runtime` means it started recently and has not emitted chat yet
- `waiting_for_human` means the run is intentionally excluded from stale timeout

Without `--dry-run`, the command:

- marks task, procedure, and chat sessions `STALLED`
- records timeout failure metadata
- does **not** kill a local PID directly

Important caveats:

- New optimizer launches already trigger an automatic background stale scan for older procedures via `launch_async_stale_timeout_scan`, excluding the current procedure ID.
- `--account <raw-account-id>` is currently unreliable through this resolver path. Prefer omitting `--account` and using the default account context unless you have a verified account key or name.
- Stale-timeout is for persisted run state. Use OS signals when you actually have a local PID to kill.

## Contradiction-Report and Approval-Gated Invalidation Workflow

### Resolve the score context

```bash
python -m plexus.cli score info \
  --scorecard "<scorecard>" \
  --score "<score>"
```

### Run or refresh the contradictions report

If a current contradictions report does not already exist for the score and time window, run one:

```bash
python -m plexus.cli feedback report contradictions \
  --scorecard "<scorecard>" \
  --score "<score>" \
  --days <days> \
  --fresh \
  --format json
```

If you queue it in the background, process it with:

```bash
python -m plexus.cli command dispatcher --once
```

Use the report to sort findings into these buckets:

- score logic change
- rubric clarification / SME question
- feedback invalidation candidate
- mechanical / no action

### Locate the exact historical report before comparing results

When you need a true pre/post comparison, do not rely on memory, Kanbus summaries, or whichever report happens to be cached. Find the exact historical report object first.

List recent reports and match by title plus timestamp:

```bash
python -m plexus.cli report list --limit 30
```

Notes:

- `report list` is table-oriented; it does not currently offer a structured `-o json` path.
- Use the report title, score name, and `Created At` timestamp to identify the pre-change and post-change reports you want.
- For contradiction work, it is common to have several same-day reports for the same score. Pick the latest report that still predates the invalidation batch or rubric/code change you are comparing against.

Inspect a specific historical report once you have the ID:

```bash
python -m plexus.cli report show <report_id>
```

`report show` gives you:

- report metadata and timestamp
- run parameters
- the report block type
- the compacted output preview
- the attachment pointer for the full stored block output

If you need the full historical contradiction payload for a diff, load the report block attachment directly:

```bash
python - <<'PY'
from plexus.cli.shared.client_utils import create_client
from plexus.dashboard.api.models.report_block import ReportBlock
from plexus.cli.dataset.curation import _load_feedback_contradictions_output_from_block

client = create_client()
blocks = ReportBlock.list_by_report_id("<report_id>", client=client)
payload = _load_feedback_contradictions_output_from_block(blocks[0])

print(payload["contradictions_found"], payload["aligned_found"])
print([t["label"] for t in payload.get("topics", [])])
PY
```

Use this path when you need to answer questions like:

- which contradiction items disappeared after invalidation?
- did the contradiction count really drop, or did clustering just surface different items?
- which report is the correct pre-invalidation baseline?

### Mechanical hints for working with the contradictions report

Do not guess from memory and do not reconstruct contradiction themes from lower-level item tools first. Use the stored contradictions report output as the source of truth.

Treat these as completion signals:

- the command prints report metadata with a `report_id`
- the command prints that the report block was generated or cached
- the command prints contradiction/aligned counts or a final run summary

If you saw those signals, inspect the stored report output next instead of rerunning the whole report blindly.

When the top-level CLI output is too shallow and you need the actual exemplar payload, use the existing helper that reads the `ReportBlock` attachment:

```bash
python - <<'PY'
from plexus.cli.shared.client_utils import create_client
from plexus.dashboard.api.models.report_block import ReportBlock
from plexus.cli.dataset.curation import _load_feedback_contradictions_output_from_block

client = create_client()
block = ReportBlock.get_by_id("<report_block_id>", client=client)
payload = _load_feedback_contradictions_output_from_block(block)

for topic in payload.get("topics", []):
    for exemplar in topic.get("exemplars", []):
        print({
            "item_id": exemplar.get("item_id"),
            "item_external_id": exemplar.get("item_external_id"),
            "feedback_item_id": exemplar.get("feedback_item_id"),
            "edit_comment": exemplar.get("edit_comment"),
            "reason": exemplar.get("reason"),
            "category": exemplar.get("category"),
            "guideline_quote": exemplar.get("guideline_quote"),
            "is_invalid": exemplar.get("is_invalid"),
        })
PY
```

When filtering a candidate invalidation group from the report payload, prioritize:

- `edit_comment`
- `reason`
- `category`
- `guideline_quote`
- `item_external_id`
- `feedback_item_id`
- `is_invalid`

Practical filtering rules:

- Build candidate groups from shared editor rationale, not just from the contradiction verdict.
- For invalidation discussions, prefer contradictions whose `edit_comment` or `reason` explicitly shows the older rubric being applied, such as `for all meds`, `for each med`, or `single miss caused No`.
- Exclude `policy_gap` cases from invalidation-first batches unless the user explicitly wants to review them.
- Exclude mechanical or truncated-context cases from invalidation-first batches unless the user explicitly asks for them.
- Present the user-facing group with stable item identifiers, usually `item_external_id`, and keep `feedback_item_id` available for the actual invalidation step.

### Handle contradiction findings at the right level

When the report reveals a contradiction cluster:

- summarize the shared pattern
- explain whether it looks like a score issue, rubric issue, or feedback-quality issue
- propose a candidate invalidation group only when the contradiction clearly reflects old or incorrect rubric application
- cite the report evidence that makes the cluster fit that group, especially the `edit_comment` and `reason`
- ask for approval before invalidating anything

### Invalidate feedback only after explicit user approval

Once the user approves an exact group, invalidate items one at a time:

```bash
python -m plexus.cli feedback invalidate "<identifier>" \
  --scorecard "<scorecard>" \
  --score "<score>"
```

Rules:

- This command is for operator-approved targeted invalidation only.
- It must not be run automatically by the optimizer.
- Before running it, restate the approved group back to the user in a flat list so there is no ambiguity.
- After running it, report the exact identifiers invalidated and whether any item was already invalid.

### Conservative contradiction-cleanup loop before optimization

Use this conservative loop when a score has likely rubric-drift labels and you need to clean the feedback pool before trusting optimizer output.

1. Run a fresh contradictions report for the score and window:

```bash
python -m plexus.cli feedback report contradictions \
  --scorecard "<scorecard>" \
  --score "<score>" \
  --days <days> \
  --fresh \
  --format json
```

2. Run a fresh feedback evaluation for the same score and window:

```bash
python -m plexus.cli evaluate feedback \
  --scorecard "<scorecard>" \
  --score "<score>" \
  --days <days> \
  --max-items <max_samples> \
  --sampling-mode newest \
  --version "<score_version>"
```

Before trusting the evaluation as optimizer input, do one mechanical sanity pass. If you recently changed parsing, output formatting, or score structure, verify that stored score results are not showing `value`/explanation contradictions.

Example direct check:

```bash
python - <<'PY'
from plexus.dashboard.api.client import PlexusDashboardClient

client = PlexusDashboardClient()
evaluation_id = "<evaluation_id>"
query = """
query Q($evaluationId: String!) {
  listScoreResultByEvaluationId(evaluationId: $evaluationId, limit: 500) {
    items { id value explanation }
  }
}
"""

items = client.execute(query, {"evaluationId": evaluation_id})["listScoreResultByEvaluationId"]["items"]
mismatches = []
for row in items or []:
    value = (row.get("value") or "").strip().lower()
    explanation = (row.get("explanation") or "").strip()
    last_line = explanation.splitlines()[-1].strip().lower() if explanation else ""
    if last_line in {"yes", "no"} and value and last_line != value:
        mismatches.append((row["id"], value, last_line))

print({"results": len(items or []), "mismatches": len(mismatches), "examples": mismatches[:10]})
PY
```

3. Look at both outputs together before invalidating anything.

What to compare:

- contradiction clusters from the contradictions report
- current error shape from the fresh evaluation
- exact feedback items that appear in both places

Practical rule:

- Start with the biggest contradiction categories first, especially clusters that clearly reflect an older rubric such as `all meds`, `each med`, or other stricter-than-current thresholds.
- Within the biggest category, start with the narrowest high-confidence subgroup first instead of invalidating every candidate at once.
- Prefer contradiction items that also show up in the current evaluation error set, because those are the labels actively distorting the optimizer target.
- Leave likely real score-behavior problems in place for the optimizer.
- Leave `policy_gap` items out of the first invalidation batch unless the user explicitly approves them.

If you need an explicit overlap check, compare the stored contradiction payload with the fresh evaluation score results:

```bash
python - <<'PY'
import json
from plexus.cli.shared.client_utils import create_client
from plexus.dashboard.api.models.report_block import ReportBlock
from plexus.cli.dataset.curation import _load_feedback_contradictions_output_from_block

client = create_client()
report_block = ReportBlock.get_by_id("<report_block_id>", client=client)
payload = _load_feedback_contradictions_output_from_block(report_block)
contradiction_ids = {
    ex["feedback_item_id"]
    for topic in payload.get("topics", [])
    for ex in topic.get("exemplars", [])
    if ex.get("feedback_item_id")
}

query = """
query ListScoreResultsForEvaluation($evaluationId: String!, $limit: Int, $nextToken: String) {
  listScoreResultByEvaluationId(evaluationId: $evaluationId, limit: $limit, nextToken: $nextToken) {
    items { metadata }
    nextToken
  }
}
"""

def extract_feedback_id(metadata):
    if isinstance(metadata, dict):
        return metadata.get("feedback_item_id") or metadata.get("feedbackItemId")
    if isinstance(metadata, str) and metadata.strip():
        try:
            parsed = json.loads(metadata)
        except Exception:
            return None
        if isinstance(parsed, str):
            try:
                parsed = json.loads(parsed)
            except Exception:
                return None
        if isinstance(parsed, dict):
            return parsed.get("feedback_item_id") or parsed.get("feedbackItemId")
    return None

evaluation_ids = set()
next_token = None
while True:
    result = client.execute(query, {
        "evaluationId": "<evaluation_id>",
        "limit": 200,
        "nextToken": next_token,
    })
    payload = (result or {}).get("listScoreResultByEvaluationId") or {}
    for row in payload.get("items") or []:
        fid = extract_feedback_id(row.get("metadata"))
        if fid:
            evaluation_ids.add(fid)
    next_token = payload.get("nextToken")
    if not next_token:
        break

print(sorted(contradiction_ids & evaluation_ids))
PY
```

4. Propose a narrow invalidation batch to the user, grouped by shared rationale.

Good first-batch candidates:

- items where the feedback explicitly applies the superseded rubric
- duplicate contradictory labels on the same item
- contradiction clusters with strong consensus and clean rationale
- the cleanest exemplars from the largest contradiction category, when that category is clearly driving the error set

Avoid first-batch invalidation for:

- items that look like prompt or recognition failures
- items with mixed evidence about whether the feedback or the score is wrong
- items whose contradiction depends on a new policy question not yet settled

5. After approval, invalidate only the approved batch.

6. Immediately rerun the fresh feedback evaluation for the same score and window.

What you want to see:

- sample size drops by the number of newly invalidated items, or close to it if duplicates collapse
- the newly invalidated IDs are absent from the new evaluation
- error count and contradiction-shaped errors decrease
- value/explanation mismatch count stays at zero if you just fixed a parsing or output-format issue

7. Immediately rerun the contradictions report for the same score and window.

What you want to see:

- contradiction count drops
- the invalidated contradiction clusters disappear
- the remaining contradiction set is smaller, cleaner, and more focused

8. Only after the post-invalidation evaluation and post-invalidation contradictions report both look cleaner should you trust the remaining set as optimizer input.

This is the gating question:

- Are the remaining errors mostly real score-behavior problems under the current rubric?

If yes, proceed with optimizer work.
If no, do another conservative invalidation review or escalate rubric questions to SMEs first.

### Artifact-reuse freshness and restart policy

The optimizer now treats feedback edits/invalidation as target-mutation events and will not trust stale cached artifacts.

- Fresh feedback evaluation selectors already exclude `isInvalid=true` items.
- Remaining leakage risk comes from artifact reuse, not live feedback fetch.
- Reuse is now guarded by a feedback watermark (`latest FeedbackItem.updatedAt` in the score window bounded by `editedAt + days`).
- Associated regression datasets are reused only when they are materialized, large enough, and fresh relative to that watermark.
- Cached baseline reuse is exact-match:
  - accuracy baseline reuse requires matching `dataset_id`
  - feedback baseline reuse requires matching `days`, `max_feedback_items`, and `sampling_mode`, and must be newer than the watermark
- If feedback changes during a run, optimizer stops with `feedback_target_changed_restart_required`.
  This is expected behavior. Restart so all baselines and cycle comparisons are computed against one consistent target.

## Advanced Manual Procedure Path With `procedure create` and `procedure run`

Keep this path for cases where you want to inspect or patch optimizer YAML directly.

List recent procedures:

```bash
python -m plexus.cli procedure list \
  --account "call-criteria" \
  --scorecard "<scorecard>"
```

Pull the latest YAML from a recent optimizer procedure:

```bash
python -m plexus.cli procedure pull <procedure_id> \
  --output /tmp/optimizer_patched.yaml
```

Patch the YAML locally. Set `value:` fields on the relevant params:

```yaml
scorecard:
  type: string
  value: "<scorecard name>"

score:
  type: string
  value: "<score name>"

max_iterations:
  type: number
  value: <max_cycles>

max_samples:
  type: number
  value: <max_samples>

days:
  type: number
  value: <days>

start_version:
  type: string
  value: "<version_id>"

resume_recent_eval:
  type: string
  value: "<eval_id>"

resume_regression_eval:
  type: string
  value: "<eval_id>"

hint:
  type: string
  value: "<hint text>"
```

Create the procedure from YAML:

```bash
python -m plexus.cli procedure create \
  --account "call-criteria" \
  --scorecard "<scorecard>" \
  --score "<score>" \
  --yaml /tmp/optimizer_patched.yaml \
  --output json
```

Then run it:

```bash
python -m plexus.cli procedure run <procedure_id>
```
