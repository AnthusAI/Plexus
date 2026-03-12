from types import SimpleNamespace

import plexus.cli.tuning.operations as ops


class DummyLLM:
    def __init__(self):
        self.messages = None

    def invoke(self, messages):
        self.messages = messages
        return SimpleNamespace(content="ok")


def test_generate_llm_completion_uses_item_pipeline_when_item_config_present(monkeypatch):
    dummy_llm = DummyLLM()

    monkeypatch.setattr(ops, "ChatOpenAI", lambda *args, **kwargs: dummy_llm)

    dummy_item = SimpleNamespace(
        to_score_input=lambda item_config=None: SimpleNamespace(text="RIGHT", metadata={})
    )
    monkeypatch.setattr(
        ops,
        "Item",
        SimpleNamespace(get_by_id=lambda item_id, client=None: dummy_item),
        raising=False,
    )
    monkeypatch.setattr(ops, "_get_item_client", lambda: None)

    score_instance = SimpleNamespace(
        parameters=SimpleNamespace(
            graph=[
                {
                    "system_message": "system",
                    "user_message": "{{ text }}",
                    "completion_llm_provider": "ChatOpenAI",
                }
            ],
            item_config={"class": "DeepgramInputSource"},
        )
    )

    row = {"text": "WRONG", "label": "Yes", "item_id": "item-123"}
    completion_template = "{{ label }}"

    ops.generate_llm_completion(score_instance, row, completion_template)

    assert dummy_llm.messages is not None
    user_message = dummy_llm.messages[1]["content"]
    assert "RIGHT" in user_message
    assert "WRONG" not in user_message
