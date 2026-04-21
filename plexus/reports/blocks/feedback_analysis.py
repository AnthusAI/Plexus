from .feedback_alignment import FeedbackAlignment


class FeedbackAnalysis(FeedbackAlignment):
    """
    Backward-compatible alias for FeedbackAlignment.

    Report configurations that reference `class: FeedbackAnalysis` should execute
    with the same behavior and config contract as FeedbackAlignment, including
    support for `days` and explicit `start_date` / `end_date` windows.
    """

