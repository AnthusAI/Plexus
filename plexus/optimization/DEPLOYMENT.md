# Living optimization workflow: release and deployment

The living optimization workflow has a hard cross-repository dependency. Plexus
uses structured, agentless `Human.review` requests that are not available in the
currently released Tactus package. The workflow must not be deployed until the
Tactus change has been released and Plexus is locked to that release.

## Required release order

1. Merge the structured-HITL Tactus change to `develop` through its normal pull
   request.
2. Promote the Tactus change to `main` and allow the semantic-release workflow
   to publish a new Tactus package and tag.
3. Verify that the published package contains the structured HITL contract.
4. Update the exact Tactus version in Plexus `pyproject.toml` and regenerate
   `poetry.lock` from the combined manifest.
5. Install and validate Plexus without `PYTHONPATH`, editable installs, path
   dependencies, or source-tree substitutions.
6. Repeat the model-backed sandbox acceptance run with the released package.
7. Merge and deploy Plexus only after the sandbox evidence is complete.

Do not reverse steps 2 and 4, deploy Plexus with a path dependency, or copy the
Tactus behavior into Plexus. A local Tactus source override is a pre-release
testing technique only; it is not a deployable dependency.

## Tactus release gate

The Tactus commit must preserve the structured HITL fields used by Plexus:

- `action_key`
- typed `resource_refs`
- freshness `preconditions`
- `expires_at`
- JSON `response_schema`
- UI schema hints
- agentless `Human.review` execution and replay/checkpoint behavior

Before merging Tactus, run its complete unit, behavior, and standard-library
suites. After the `main` release completes, record the tag and package version,
then verify the package is downloadable from the package index. The new release
must be newer than the Plexus pin shown by:

```bash
rg -n '^tactus = ' pyproject.toml
```

## Plexus dependency update

Change only the exact Tactus version in `pyproject.toml`, then regenerate the
lock from the complete manifest:

```bash
poetry lock --no-cache
poetry install --with dev --all-extras
poetry check --lock
```

Confirm the environment imports the released package rather than a checkout:

```bash
env -u PYTHONPATH poetry run python -c \
  'import pathlib, tactus; print(tactus.__version__); print(pathlib.Path(tactus.__file__).resolve())'
```

The reported version must equal the new exact pin, and the module path must be
inside the Poetry environment rather than a Tactus source worktree.

## Local pre-release acceptance

Local acceptance may exercise the unreleased Tactus source while the two pull
requests remain under review:

```bash
export PYTHONPATH=/absolute/path/to/Tactus-structured-hitl${PYTHONPATH:+:$PYTHONPATH}
poetry run plexus procedure run \
  --yaml plexus/procedures/optimization_portfolio_run.yaml \
  --set account_id='<opaque-account-id>' \
  --set run_key='<unique-test-run-key>' \
  --set max_cost_usd=0 \
  --set max_semantic_diagnoses=25 \
  --set max_samples=1 \
  --set max_iterations=1 \
  --set max_concurrency=1 \
  --output json
```

Use the locally running dashboard with its normal production API configuration
to inspect the Report and ChatMessage action. Do not run a general task
dispatcher: the procedure is executed directly so the local process cannot
claim unrelated work. An initial safety run uses zero optimizer cost and must
stop at `Human.review`; reject or leave the request unresolved. A later
optimizer acceptance run requires a new explicit approval for the exact targets
and nonzero limits.

The source override must be removed before release validation:

```bash
unset PYTHONPATH
```

## Plexus validation gate

With the released Tactus package installed and no source override, verify:

- Python 3.11 and 3.12 full CI and dispatch regressions
- dashboard typecheck and coverage tests under Node 20
- Storybook build and Chromium interaction tests
- Tactus runtime contract tests
- no Amplify schema, backend-resource, function, index, association, storage,
  or IAM diff
- all report evidence uses existing `TASK_ATTACHMENT` artifacts

Then run the sandbox workflow from initial Report creation through a structured
ChatMessage response and terminal workbook publication. Reconcile the workbook
row counts with the frozen packets and confirm that no score, score version,
guideline, feedback setting, or champion changed unless a separately approved
test explicitly requires that mutation.

## Deployment verification

After deploying Plexus, perform a bounded acceptance run and record:

- Tactus package version imported by the worker
- run key, attempt ID, Task ID, Procedure ID, and Report ID
- Report URL remains stable from start through finalization
- immutable JSON and XLSX revisions use unique attachment keys and checksums
- the Report cover page points to the latest verified workbook revision
- blocking approval uses `Procedure.waitingOnMessageId`
- exactly one valid child `RESPONSE` can claim a pending action
- stale, expired, duplicate, and cross-account responses fail closed
- approved optimizer targets are exact and limited to five
- advisory stakeholder, collection, and promotion responses do not mutate
  operational state automatically

Do not declare the workflow deployed successfully from a created Task or a
pending action alone. Success requires the expected terminal procedure state,
the corresponding final Report revision, and reconciled artifacts.

## Rollback

If the Tactus release is defective before Plexus deploys, do not advance the
Plexus pin. Fix Tactus, release another version, and pin Plexus only to the
corrected package.

If Plexus fails after deployment:

1. Stop new portfolio-run scheduling.
2. Leave already published Report evidence immutable.
3. Mark affected attempts failed when possible; do not reuse a terminal failed
   attempt as a successful retry.
4. Roll Plexus back to the previous application release and its previous exact
   Tactus lock.
5. Re-run the read-only smoke test before resuming schedules.

Rolling Plexus back does not require deleting the newer Tactus package. Do not
rewrite or remove historical Reports, Tasks, Procedures, ChatMessages, or
attachments during rollback.
