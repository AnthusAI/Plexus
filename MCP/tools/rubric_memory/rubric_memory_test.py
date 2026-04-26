from rubric_memory.rubric_memory import (
    _fetch_feedback_item_context,
    _fetch_score_result_context,
    _merge_context_value,
)


class FakeClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def execute(self, query, variables=None):
        self.calls.append((query, variables))
        key = variables["id"]
        return self.responses[key]


def test_fetch_score_result_context_hydrates_model_fields():
    client = FakeClient({
        "sr-1": {
            "getScoreResult": {
                "id": "sr-1",
                "value": "No",
                "explanation": "Dose missing.",
                "itemId": "item-1",
                "feedbackItemId": "fb-1",
                "scoreId": "score-1",
            }
        }
    })

    context = _fetch_score_result_context(client, "sr-1")

    assert context["score_result_id"] == "sr-1"
    assert context["score_id"] == "score-1"
    assert context["feedback_item_id"] == "fb-1"
    assert context["model_value"] == "No"
    assert context["model_explanation"] == "Dose missing."


def test_fetch_feedback_item_context_hydrates_transcript_and_feedback_fields():
    client = FakeClient({
        "fb-1": {
            "getFeedbackItem": {
                "id": "fb-1",
                "scoreId": "score-1",
                "scorecardId": "scorecard-1",
                "itemId": "item-1",
                "initialAnswerValue": "No",
                "finalAnswerValue": "Yes",
                "initialCommentValue": "initial",
                "finalCommentValue": "final",
                "editCommentValue": "reviewer edit",
                "item": {"id": "item-1", "text": "call transcript"},
            }
        }
    })

    context = _fetch_feedback_item_context(client, "fb-1")

    assert context["feedback_item_id"] == "fb-1"
    assert context["score_id"] == "score-1"
    assert context["transcript_text"] == "call transcript"
    assert context["feedback_value"] == "Yes"
    assert context["feedback_comment"] == "reviewer edit\nfinal\ninitial"


def test_merge_context_value_prefers_explicit_value():
    assert _merge_context_value("explicit", "fetched") == "explicit"
    assert _merge_context_value("", "fetched") == "fetched"
