---
name: client-redaction
description: Scan the Plexus repository for non-sponsor client names and specific client-work references, then redact or remove sensitive mentions from files, Kanbus issues, commit messages, and related text surfaces.
---

# Plexus Client Redaction

Use this skill for repository hygiene passes that identify and remove sensitive
client references from Plexus.

Official sponsor names that may remain when context is appropriate:

- Call Criteria
- Capacity

Every other client, prospect, customer, account, implementation, or specific
client-work reference is sensitive unless the user explicitly says otherwise.

## Operating Rules

- Start by creating or updating Kanbus work for the redaction pass.
- Do not read or edit `project/` directly. Use `kanbus` commands for issue text.
- Preserve enough local evidence for review before changing anything: file path,
  line number or commit hash, and a short sanitized description.
- Redact client identity and specific work details. Do not replace one sensitive
  client name with another concrete customer name.
- Keep sponsor references only when they refer to Call Criteria or Capacity in
  sponsor, platform, or public documentation context.
- Treat client-work details as sensitive even without a client name, including
  scorecard names, account-specific workflows, private integrations, client data
  layouts, support cases, production incidents, and implementation notes.
- Never rewrite pushed/shared Git history without explicit user approval and a
  coordination plan.

## Standard Workflow

1. **Define the scan window.** Decide whether the pass covers the whole working
   tree, a branch range, recent commits, Kanbus issues, docs, or all surfaces.
2. **Collect candidate terms.** Include known non-sponsor client names,
   project/account names, private scorecard names, and distinctive work phrases.
   Add sponsor names to the allowlist, not to the sensitive term list.
3. **Run deterministic scans.** Use the helper script from the repository root:

   ```bash
   python skills/client-redaction/scripts/scan_sensitive_refs.py \
     --terms-file /path/to/sensitive_terms.txt \
     --include-git-log \
     --include-untracked
   ```

   For a small one-off pass, pass repeated `--term` values instead of a file.
   Add `--no-cues` only when you need a literal-term verification pass after
   reviewing client-work language separately.
4. **Review semantically.** Search for client-work language that may not include
   a known client name:

   ```bash
   rg -n -i "client|customer|prospect|account|implementation|integration|scorecard|production|support case|pilot|deployment|tenant"
   git log --all --format='%H %s%n%b' | rg -n -i "client|customer|prospect|account|implementation|integration|scorecard|production|support case|pilot|deployment|tenant"
   ```

5. **Redact by surface.**
   - Files: replace sensitive specifics with neutral phrasing such as
     `[REDACTED CLIENT]`, `[REDACTED CLIENT WORK]`, or a generic category like
     `a customer scorecard`.
   - Kanbus: use `kanbus show`, `kanbus update`, and `kanbus comment`; never
     inspect or edit `project/` files.
   - Current unpushed commit message: amend the message after confirming the
     commit is local-only.
   - Older local-only commit message: use a non-interactive rebase plan only
     when the affected commits are not shared.
   - Pushed/shared history: stop and ask the user. History rewrite, force push,
     and downstream coordination require explicit approval.
6. **Verify.** Rerun the deterministic scan and repeat semantic searches. Check
   `git diff` for accidental disclosure in the replacement text itself.
7. **Report.** Summarize surfaces scanned, redactions made, remaining risks, and
   anything that needs user approval.

## Helper Script Behavior

`scripts/scan_sensitive_refs.py` scans tracked files by default, with optional
untracked files and Git commit messages. It always skips `project/` because
Kanbus text must be accessed only through `kanbus` commands. It reports:

- `literal-term`: matches for supplied sensitive terms, excluding approved
  sponsors.
- `client-work-cue`: high-signal phrases that may describe specific client work.

The script is intentionally read-only. It does not prove the repository is free
of sensitive information; it gives the agent a deterministic queue for review.

## Redaction Standards

Use the least specific replacement that preserves technical meaning:

- `[CLIENT NAME] enrollment scorecard` -> `a customer enrollment scorecard`
- `[CLIENT NAME] production incident` -> `a customer production incident`
- `custom workflow for [CLIENT NAME]` -> `custom workflow for a customer`
- `Call Criteria sponsor demo` -> keep if public/sponsor context is correct
- `Capacity integration` -> keep if public/sponsor context is correct

When a sentence exists only to document private client work, remove the sentence
instead of leaving a dense block of redactions.

## Completion Checklist

- Kanbus issue records the scope and outcome.
- Sensitive term scan returns no unresolved matches.
- Semantic searches have been reviewed.
- Files and Kanbus text no longer disclose non-sponsor clients or specific work.
- Commit messages in the relevant local range are clean or escalated for
  approved history cleanup.
- Final response lists residual risks without repeating sensitive names.
