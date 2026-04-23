from .feedback_alignment import FeedbackAlignment


class FeedbackAnalysis(FeedbackAlignment):
    """
    Backward-compatible alias for FeedbackAlignment.

    Report configurations that reference `class: FeedbackAnalysis` should execute
    with the same behavior and config contract as FeedbackAlignment, including
    support for `days` and explicit `start_date` / `end_date` windows.
    """

    async def generate(self):
        # Keep legacy FeedbackAnalysis execution lightweight/safe by default.
        # Memory analysis remains available as an explicit opt-in.
        if "memory_analysis" not in self.config:
            self.config["memory_analysis"] = False
        return await super().generate()
