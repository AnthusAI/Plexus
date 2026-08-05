"""Tests for execution-scoped command progress reporting."""

from concurrent.futures import ThreadPoolExecutor

from plexus.cli.shared.CommandProgress import CommandProgress


def test_progress_callback_receives_updates_from_its_execution_context() -> None:
    observed = []
    CommandProgress.set_update_callback(observed.append)

    CommandProgress.update(2, 5, "running")

    assert [(state.current, state.total, state.status) for state in observed] == [
        (2, 5, "running")
    ]


def test_progress_state_and_callback_do_not_cross_thread_boundaries() -> None:
    def run(current: int) -> tuple[int, int]:
        observed = []
        CommandProgress.set_update_callback(observed.append)
        CommandProgress.update(current, 10, f"command-{current}")
        state = CommandProgress.get_current_state()
        assert state is not None
        return state.current, observed[0].current

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = sorted(executor.map(run, (3, 7)))

    assert results == [(3, 3), (7, 7)]


def test_track_restores_prior_progress_state_after_completion() -> None:
    CommandProgress.update(1, 4, "outer")

    with CommandProgress.track(10, "inner"):
        CommandProgress.update(5, 10, "inner")
        assert CommandProgress.get_current_state().current == 5

    restored = CommandProgress.get_current_state()
    assert restored is not None
    assert restored.current == 1
    assert restored.status == "outer"
