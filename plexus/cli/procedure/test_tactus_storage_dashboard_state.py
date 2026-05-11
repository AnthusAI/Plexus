from plexus.cli.procedure.tactus_adapters.storage import _build_dashboard_state


def test_dashboard_state_projects_repeat_active_emerging_recurrence():
    state = {
        "item_recurrence": {
            "account--310918611": {
                "first_cycle": 1,
                "last_cycle": 2,
                "wrong_count": 1,
                "correct_count": 1,
                "segment": "No/Yes",
                "segment_stable": True,
                "recent_label": "Yes",
                "model_prediction": "No",
                "pattern": "EMERGING",
                "per_cycle": [
                    {"cycle": 1, "segment": "No/Yes", "rationale": "missed script carveout"},
                    {"cycle": 2, "segment": "CORRECT"},
                ],
            }
        },
        "iterations": [],
    }

    dashboard_state = _build_dashboard_state(state)

    recurrence = dashboard_state["notable_item_recurrence"]
    projected = recurrence["account--310918611"]
    assert projected["pattern"] == "EMERGING"
    assert projected["feedback_label"] == "Yes"
    assert projected["per_cycle"][-1]["segment"] == "CORRECT"
    assert "item_recurrence" not in dashboard_state


def test_dashboard_state_keeps_single_cycle_emerging_items_hidden():
    state = {
        "item_recurrence": {
            "account--310684957": {
                "first_cycle": 2,
                "last_cycle": 2,
                "wrong_count": 1,
                "correct_count": 0,
                "recent_label": "No",
                "model_prediction": "Yes",
                "pattern": "EMERGING",
                "per_cycle": [
                    {"cycle": 2, "segment": "Yes/No", "rationale": "new one-off miss"},
                ],
            }
        },
        "iterations": [],
    }

    dashboard_state = _build_dashboard_state(state)

    assert "notable_item_recurrence" not in dashboard_state


def test_dashboard_state_projects_persistent_recurrence_even_without_repeat_history():
    state = {
        "item_recurrence": {
            "account--310684886": {
                "first_cycle": 3,
                "last_cycle": 3,
                "wrong_count": 3,
                "correct_count": 0,
                "recent_label": "Yes",
                "model_prediction": "No",
                "pattern": "PERSISTENT",
                "per_cycle": [
                    {"cycle": 1, "segment": "No/Yes"},
                    {"cycle": 2, "segment": "No/Yes"},
                    {"cycle": 3, "segment": "No/Yes"},
                ],
            }
        },
        "iterations": [],
    }

    dashboard_state = _build_dashboard_state(state)

    assert dashboard_state["notable_item_recurrence"]["account--310684886"]["pattern"] == "PERSISTENT"


def test_dashboard_state_projects_recurrence_audit_without_raw_tracker():
    state = {
        "item_recurrence": {
            "account--310684886": {
                "wrong_count": 3,
                "correct_count": 0,
                "pattern": "PERSISTENT",
                "per_cycle": [{"cycle": 3, "segment": "No/Yes"}],
            }
        },
        "last_recurrence_context_audit": {
            "cycle": 4,
            "context": "hypothesis",
            "fingerprint": "target=310684886 PERSISTENT; top3=[310684886 PERSISTENT wrong=3 correct=0]",
        },
        "iterations": [],
    }

    dashboard_state = _build_dashboard_state(state)

    assert "item_recurrence" not in dashboard_state
    assert dashboard_state["last_recurrence_context_audit"]["context"] == "hypothesis"
    assert "target=310684886 PERSISTENT" in dashboard_state["last_recurrence_context_audit"]["fingerprint"]
