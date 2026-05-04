---
id: evaluation-feedback.optimizer-objective-recall
title: "Optimizer Objective: Recall"
summary: Optimizer objective tuned for recall.
namespace: evaluation-feedback
status: canonical
disclosure: reference
audience: agent
tags: [optimizer, objective, recall]
---
# Optimization Objective: Recall

PLACEHOLDER — content to be written.

Used for both `recall` (pure) and `recall_safe` (with alignment guardrail) objectives.

Goal: Reduce false negatives — cases where the AI says "No" but the human label is "Yes".

Focus on the **Predicted: No / Actual: Yes** confusion matrix segment.
Widen the "Yes" threshold. Add more inclusive criteria. Clarify edge cases that should qualify.
