# Optimizer Cookbook Overview

The optimizer now uses lane-specific cookbooks instead of one shared cookbook.
Each hypothesis slot receives only the cookbook for its lane.

## Lane Cookbooks

- `optimizer-cookbook-normal`: used by `recent_incremental`, `recent_bold`,
  and `regression_fix`. Focuses on rubric alignment, missing policy,
  ambiguous criteria, feedback-direction targeting, conservative prompt
  clarity, and limited examples.
- `optimizer-cookbook-structural`: used by `structural`, `reframe`, and
  `full_rewrite`. Covers model swaps, input source changes, preprocessing,
  decomposition, N/A gates, extractor nodes, and late prompt-shape tactics.
- `optimizer-cookbook-creative`: used only by `creative` from cycle 4 onward.
  Covers weird but testable prompt transformations.

## Shared Constraints

The optimizer YAML owns global constraints that apply to every lane:

- Do not edit classification guidelines.
- Do not modify parser, output-normalization, framework, or optimizer runtime
  code.
- Target one confusion direction per hypothesis unless the slot objective asks
  for synthesis or reframing.
- Avoid repeating harmful prior ideas.
- Use held-out evaluations and keep only variants that win.

Use the lane docs directly when adding or reviewing optimizer tactics.
