"""
Tests for Stage Primitive - Workflow progress tracking.

Tests all Stage primitive methods:
- Stage.current()
- Stage.set(stage)
- Stage.advance()
- Stage.is_current(stage) [spec says is(), but implemented as is_current()]
- Stage.history()
- Stage.count()
- Stage.clear_history()
"""

import pytest
from datetime import datetime, timezone
from plexus.cli.procedure.lua_dsl.primitives.stage import StagePrimitive


@pytest.fixture
def stage():
    """Create a Stage primitive with typical stages."""
    return StagePrimitive(declared_stages=['setup', 'processing', 'validation', 'completion'])


@pytest.fixture
def stage_no_declaration():
    """Create a Stage primitive without declared stages."""
    return StagePrimitive()


class TestStageCurrent:
    """Tests for Stage.current()"""

    def test_current_returns_none_initially(self, stage):
        """Should return None when no stage has been set."""
        assert stage.current() is None

    def test_current_returns_set_stage(self, stage):
        """Should return the stage that was set."""
        stage.set('setup')
        assert stage.current() == 'setup'

        stage.set('processing')
        assert stage.current() == 'processing'

    def test_current_persists_across_calls(self, stage):
        """Should return same value on repeated calls."""
        stage.set('validation')
        assert stage.current() == 'validation'
        assert stage.current() == 'validation'
        assert stage.current() == 'validation'


class TestStageSet:
    """Tests for Stage.set()"""

    def test_set_valid_stage(self, stage):
        """Should set stage when it's in declared stages."""
        stage.set('setup')
        assert stage.current() == 'setup'

    def test_set_multiple_stages(self, stage):
        """Should allow setting different stages."""
        stage.set('setup')
        assert stage.current() == 'setup'

        stage.set('processing')
        assert stage.current() == 'processing'

        stage.set('validation')
        assert stage.current() == 'validation'

    def test_set_invalid_stage_raises_error(self, stage):
        """Should raise ValueError for undeclared stage."""
        with pytest.raises(ValueError, match="Invalid stage 'invalid_stage'"):
            stage.set('invalid_stage')

    def test_set_records_history(self, stage):
        """Should record transition in history."""
        stage.set('setup')
        assert len(stage._history) == 1
        assert stage._history[0]['from_stage'] is None
        assert stage._history[0]['to_stage'] == 'setup'

        stage.set('processing')
        assert len(stage._history) == 2
        assert stage._history[1]['from_stage'] == 'setup'
        assert stage._history[1]['to_stage'] == 'processing'

    def test_set_includes_timestamp(self, stage):
        """Should include timestamp in history entry."""
        before = datetime.now(timezone.utc).isoformat()
        stage.set('setup')
        after = datetime.now(timezone.utc).isoformat()

        transition = stage._history[0]
        assert 'timestamp' in transition
        assert before <= transition['timestamp'] <= after

    def test_set_without_declared_stages(self, stage_no_declaration):
        """Should allow any stage when no stages declared."""
        stage_no_declaration.set('any_stage')
        assert stage_no_declaration.current() == 'any_stage'

        stage_no_declaration.set('another_stage')
        assert stage_no_declaration.current() == 'another_stage'

    def test_set_same_stage_twice(self, stage):
        """Should allow setting same stage multiple times."""
        stage.set('setup')
        stage.set('setup')
        assert stage.current() == 'setup'
        assert len(stage._history) == 2


class TestStageAdvance:
    """Tests for Stage.advance()"""

    def test_advance_moves_to_next_stage(self, stage):
        """Should move to next stage in sequence."""
        stage.set('setup')
        next_stage = stage.advance()
        assert next_stage == 'processing'
        assert stage.current() == 'processing'

    def test_advance_through_all_stages(self, stage):
        """Should advance through all stages in order."""
        stage.set('setup')
        assert stage.advance() == 'processing'
        assert stage.advance() == 'validation'
        assert stage.advance() == 'completion'

    def test_advance_at_final_stage_returns_none(self, stage):
        """Should return None when already at final stage."""
        stage.set('completion')
        result = stage.advance()
        assert result is None
        assert stage.current() == 'completion'  # Stays at final stage

    def test_advance_without_current_stage_raises_error(self, stage):
        """Should raise ValueError when no current stage set."""
        with pytest.raises(ValueError, match="Cannot advance: no current stage set"):
            stage.advance()

    def test_advance_without_declared_stages_raises_error(self, stage_no_declaration):
        """Should raise ValueError when no stages declared."""
        stage_no_declaration.set('some_stage')
        with pytest.raises(ValueError, match="Cannot advance: no stages declared"):
            stage_no_declaration.advance()

    def test_advance_with_invalid_current_stage_raises_error(self, stage):
        """Should raise ValueError if current stage not in declared stages."""
        # Manually set an invalid current stage (bypassing validation)
        stage._current_stage = 'invalid_stage'
        with pytest.raises(ValueError, match="Current stage 'invalid_stage' not in declared stages"):
            stage.advance()

    def test_advance_records_history(self, stage):
        """Should record transition in history."""
        stage.set('setup')
        stage.advance()

        # Should have 2 entries: set + advance
        assert len(stage._history) == 2
        assert stage._history[1]['from_stage'] == 'setup'
        assert stage._history[1]['to_stage'] == 'processing'


class TestStageIsCurrent:
    """Tests for Stage.is_current() [spec says is()]"""

    def test_is_current_returns_true_for_current_stage(self, stage):
        """Should return True when checking current stage."""
        stage.set('processing')
        assert stage.is_current('processing') is True

    def test_is_current_returns_false_for_other_stage(self, stage):
        """Should return False when checking non-current stage."""
        stage.set('processing')
        assert stage.is_current('setup') is False
        assert stage.is_current('validation') is False

    def test_is_current_returns_false_when_no_stage_set(self, stage):
        """Should return False when no stage has been set."""
        assert stage.is_current('setup') is False
        assert stage.is_current('processing') is False

    def test_is_current_case_sensitive(self, stage):
        """Should be case-sensitive in stage comparison."""
        stage.set('setup')
        assert stage.is_current('setup') is True
        assert stage.is_current('Setup') is False
        assert stage.is_current('SETUP') is False


class TestStageHistory:
    """Tests for Stage.history()"""

    def test_history_returns_empty_initially(self, stage):
        """Should return empty list/table when no transitions."""
        history = stage.history()
        assert len(history) == 0

    def test_history_returns_all_transitions(self, stage):
        """Should return all stage transitions."""
        stage.set('setup')
        stage.set('processing')
        stage.set('validation')

        history = stage.history()
        assert len(history) == 3

    def test_history_entries_have_required_fields(self, stage):
        """Should have from_stage, to_stage, and timestamp."""
        stage.set('setup')
        history = stage.history()

        assert len(history) == 1
        entry = history[0]
        assert 'from_stage' in entry
        assert 'to_stage' in entry
        assert 'timestamp' in entry

    def test_history_tracks_transitions_in_order(self, stage):
        """Should maintain chronological order of transitions."""
        stage.set('setup')
        stage.set('processing')
        stage.set('validation')

        history = stage.history()
        assert history[0]['to_stage'] == 'setup'
        assert history[1]['to_stage'] == 'processing'
        assert history[2]['to_stage'] == 'validation'

    def test_history_includes_advance_transitions(self, stage):
        """Should include transitions from advance()."""
        stage.set('setup')
        stage.advance()
        stage.advance()

        history = stage.history()
        assert len(history) == 3
        assert history[0]['to_stage'] == 'setup'
        assert history[1]['to_stage'] == 'processing'
        assert history[2]['to_stage'] == 'validation'

    def test_history_returns_copy(self, stage):
        """Should return copy so modifications don't affect internal state."""
        stage.set('setup')
        history = stage.history()

        # Modify the returned history
        if isinstance(history, list):
            history.append({'fake': 'entry'})
            # Internal history should be unchanged
            assert len(stage._history) == 1


class TestStageCount:
    """Tests for Stage.count()"""

    def test_count_returns_zero_initially(self, stage):
        """Should return 0 when no transitions."""
        assert stage.count() == 0

    def test_count_returns_transition_count(self, stage):
        """Should return number of transitions."""
        stage.set('setup')
        assert stage.count() == 1

        stage.set('processing')
        assert stage.count() == 2

        stage.set('validation')
        assert stage.count() == 3

    def test_count_includes_advance_transitions(self, stage):
        """Should include transitions from advance()."""
        stage.set('setup')
        stage.advance()
        stage.advance()
        assert stage.count() == 3


class TestStageClearHistory:
    """Tests for Stage.clear_history()"""

    def test_clear_history_removes_all_transitions(self, stage):
        """Should clear all history entries."""
        stage.set('setup')
        stage.set('processing')
        stage.set('validation')

        assert len(stage._history) == 3
        stage.clear_history()
        assert len(stage._history) == 0
        assert stage.count() == 0

    def test_clear_history_preserves_current_stage(self, stage):
        """Should not affect current stage."""
        stage.set('processing')
        current_before = stage.current()

        stage.clear_history()

        assert stage.current() == current_before
        assert stage.current() == 'processing'

    def test_clear_history_allows_new_transitions(self, stage):
        """Should allow adding new transitions after clear."""
        stage.set('setup')
        stage.clear_history()

        stage.set('processing')
        assert len(stage._history) == 1
        assert stage.history()[0]['to_stage'] == 'processing'


class TestStageIntegration:
    """Integration tests combining multiple operations."""

    def test_typical_workflow_progression(self, stage):
        """Test typical stage progression through workflow."""
        # Start workflow
        stage.set('setup')
        assert stage.current() == 'setup'
        assert stage.is_current('setup')

        # Progress through stages
        stage.advance()
        assert stage.current() == 'processing'
        assert stage.is_current('processing')

        stage.advance()
        assert stage.current() == 'validation'

        stage.advance()
        assert stage.current() == 'completion'

        # Verify history
        history = stage.history()
        assert len(history) == 4
        assert stage.count() == 4

    def test_non_linear_stage_transitions(self, stage):
        """Test jumping between stages (not just advancing)."""
        stage.set('setup')
        stage.set('validation')  # Skip processing
        stage.set('processing')  # Go back
        stage.set('completion')  # Jump forward

        assert stage.current() == 'completion'
        assert stage.count() == 4

        history = stage.history()
        assert history[0]['to_stage'] == 'setup'
        assert history[1]['to_stage'] == 'validation'
        assert history[2]['to_stage'] == 'processing'
        assert history[3]['to_stage'] == 'completion'

    def test_stage_with_retries(self, stage):
        """Test returning to same stage multiple times."""
        stage.set('setup')
        stage.advance()  # to processing
        stage.set('setup')  # retry
        stage.advance()  # to processing again
        stage.advance()  # to validation

        assert stage.current() == 'validation'
        assert stage.count() == 5

    def test_conditional_advancement(self, stage):
        """Test conditional stage advancement logic."""
        stage.set('setup')

        # Simulate conditional logic
        if stage.is_current('setup'):
            next_stage = stage.advance()
            assert next_stage == 'processing'

        if stage.is_current('processing'):
            stage.advance()

        assert stage.current() == 'validation'


class TestStageEdgeCases:
    """Edge case and error condition tests."""

    def test_single_stage_workflow(self):
        """Should handle workflow with only one stage."""
        single_stage = StagePrimitive(declared_stages=['only_stage'])
        single_stage.set('only_stage')

        # Cannot advance past single stage
        result = single_stage.advance()
        assert result is None
        assert single_stage.current() == 'only_stage'

    def test_two_stage_workflow(self):
        """Should handle minimal two-stage workflow."""
        two_stage = StagePrimitive(declared_stages=['first', 'second'])
        two_stage.set('first')
        assert two_stage.advance() == 'second'
        assert two_stage.advance() is None

    def test_many_stages_workflow(self):
        """Should handle workflow with many stages."""
        many_stages = [f'stage_{i}' for i in range(20)]
        workflow = StagePrimitive(declared_stages=many_stages)

        workflow.set('stage_0')
        for i in range(1, 20):
            result = workflow.advance()
            assert result == f'stage_{i}'

        # At final stage
        assert workflow.advance() is None

    def test_empty_declared_stages_list(self):
        """Should allow any stage with empty declared stages list."""
        empty = StagePrimitive(declared_stages=[])
        # Empty list behaves same as no declared stages - allows anything
        empty.set('any_stage')
        assert empty.current() == 'any_stage'

    def test_stage_names_with_special_characters(self):
        """Should handle stage names with special characters."""
        special = StagePrimitive(declared_stages=['stage-1', 'stage_2', 'stage.3', 'stage 4'])
        special.set('stage-1')
        assert special.current() == 'stage-1'
        special.advance()
        assert special.current() == 'stage_2'

    def test_unicode_stage_names(self):
        """Should handle unicode in stage names."""
        unicode_stages = StagePrimitive(declared_stages=['开始', '处理', '完成'])
        unicode_stages.set('开始')
        assert unicode_stages.current() == '开始'
        unicode_stages.advance()
        assert unicode_stages.current() == '处理'


class TestStageRepr:
    """Tests for __repr__()"""

    def test_repr_no_current_stage(self, stage):
        """Should show None for current when not set."""
        assert repr(stage) == "StagePrimitive(current=None, stages=['setup', 'processing', 'validation', 'completion'])"

    def test_repr_with_current_stage(self, stage):
        """Should show current stage."""
        stage.set('processing')
        assert repr(stage) == "StagePrimitive(current=processing, stages=['setup', 'processing', 'validation', 'completion'])"

    def test_repr_no_declared_stages(self, stage_no_declaration):
        """Should show empty stages list."""
        assert repr(stage_no_declaration) == "StagePrimitive(current=None, stages=[])"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
