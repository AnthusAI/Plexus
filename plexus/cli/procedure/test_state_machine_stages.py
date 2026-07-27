"""Observable task-stage configurations for built-in procedures."""

from plexus.cli.procedure.state_machine_stages import (
    get_alignment_optimizer_stage_configs,
)


def test_alignment_optimizer_stages_match_the_procedure_progress_events():
    """The task exposes every stage reported by the optimizer procedure."""
    stages = get_alignment_optimizer_stage_configs()

    assert list(stages) == [
        "Setup",
        "Baseline",
        "Exploration",
        "Selection",
        "Finalize",
    ]
    assert [config.order for config in stages.values()] == [1, 2, 3, 4, 5]
