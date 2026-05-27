from plexus.utils.score_result_timestamps import extract_score_result_timestamps


def test_extracts_structured_snake_case_timestamps():
    timestamps = extract_score_result_timestamps(
        {"start_time_seconds": "1.2", "end_time_seconds": 2}
    )

    assert timestamps.start_time_seconds == 1.2
    assert timestamps.end_time_seconds == 2.0
    assert timestamps.as_graphql_input() == {
        "startTimeSeconds": 1.2,
        "endTimeSeconds": 2.0,
    }


def test_extracts_structured_deepgram_start_end_timestamps():
    timestamps = extract_score_result_timestamps({"start": 1.2, "end": "2.0"})

    assert timestamps.start_time_seconds == 1.2
    assert timestamps.end_time_seconds == 2.0


def test_parses_first_bracketed_minute_span_from_explanation():
    timestamps = extract_score_result_timestamps(
        explanation='The agent said "General Kenobi" [0:01.20-0:02.00].'
    )

    assert timestamps.start_time_seconds == 1.2
    assert timestamps.end_time_seconds == 2.0


def test_uses_first_bracketed_span_when_multiple_are_present():
    timestamps = extract_score_result_timestamps(
        explanation='"One" [0:01.00-0:02.00] then "Two" [0:10.00-0:12.00].'
    )

    assert timestamps.start_time_seconds == 1.0
    assert timestamps.end_time_seconds == 2.0


def test_structured_values_win_over_bracketed_values():
    timestamps = extract_score_result_timestamps(
        {"startTimeSeconds": 5, "endTimeSeconds": 6},
        explanation='"One" [0:01.00-0:02.00].',
    )

    assert timestamps.start_time_seconds == 5.0
    assert timestamps.end_time_seconds == 6.0


def test_malformed_brackets_return_no_timestamps():
    timestamps = extract_score_result_timestamps(
        explanation='"One" [not-a-time-0:02.00].'
    )

    assert timestamps.start_time_seconds is None
    assert timestamps.end_time_seconds is None
