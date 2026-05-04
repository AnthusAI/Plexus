---
id: evaluation-feedback.optimizer-objective-precision
title: "Optimizer Objective: Precision"
summary: Optimizer objective tuned for precision.
namespace: evaluation-feedback
status: canonical
disclosure: reference
audience: agent
tags: [optimizer, objective, precision]
---
# Optimization Objective: Precision

PLACEHOLDER — content to be written.

Used for both `precision` (pure) and `precision_safe` (with alignment guardrail) objectives.

Goal: Reduce false positives — cases where the AI says "Yes" but the human label is "No".

Focus on the **Predicted: Yes / Actual: No** confusion matrix segment.
Tighten the "Yes" threshold. Add clearer exclusion criteria. Clarify what does NOT qualify.
