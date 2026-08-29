# Subject-identity scores

This file marks the addition of two Score classes for scanner
evaluation grades (see plexus/scores/SubjectIdentityScore.py and
plexus/scores/SubjectSpanOverlapScore.py).

- SubjectIdentityScore: match Items by metadata.subjectKey, span-independent.
- SubjectSpanOverlapScore: match when both subjectKey and span overlap.

Kanbus: plx-091f92, plx-065f87.
