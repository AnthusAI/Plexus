import pandas as pd


def test_resolve_human_label_falls_back_to_stored_score_name_when_alias_is_absent():
    from plexus.Evaluation import _resolve_human_label

    row = pd.Series({"Stored Score": "No"})

    label, found = _resolve_human_label(
        row=row,
        label_score_name="Renamed Human Label",
        score_name="Stored Score",
    )

    assert found is True
    assert label == "No"


def test_resolve_human_label_uses_populated_stored_column_when_alias_column_is_empty():
    from plexus.Evaluation import _resolve_human_label

    row = pd.Series({"Renamed Human Label": "", "Stored Score": "Yes"})

    label, found = _resolve_human_label(
        row=row,
        label_score_name="Renamed Human Label",
        score_name="Stored Score",
    )

    assert found is True
    assert label == "Yes"
