"""
Tests for State Primitive - Mutable state management.

Tests all State primitive methods:
- State.get(key, default)
- State.set(key, value)
- State.increment(key, amount)
- State.append(key, value)
- State.all()
- State.clear()
"""

import pytest
from plexus.cli.procedure.lua_dsl.primitives.state import StatePrimitive


@pytest.fixture
def state():
    """Create a fresh State primitive for each test."""
    return StatePrimitive()


class TestStateGet:
    """Tests for State.get()"""

    def test_get_existing_key(self, state):
        """Should return value for existing key."""
        state._state['count'] = 42
        assert state.get('count') == 42

    def test_get_nonexistent_key_returns_none(self, state):
        """Should return None for non-existent key."""
        assert state.get('missing') is None

    def test_get_nonexistent_key_with_default(self, state):
        """Should return default for non-existent key."""
        assert state.get('missing', 'default_value') == 'default_value'
        assert state.get('missing', 0) == 0
        assert state.get('missing', []) == []

    def test_get_with_various_types(self, state):
        """Should handle various value types."""
        state._state['string'] = "hello"
        state._state['int'] = 123
        state._state['float'] = 45.67
        state._state['list'] = [1, 2, 3]
        state._state['dict'] = {'key': 'value'}
        state._state['bool'] = True

        assert state.get('string') == "hello"
        assert state.get('int') == 123
        assert state.get('float') == 45.67
        assert state.get('list') == [1, 2, 3]
        assert state.get('dict') == {'key': 'value'}
        assert state.get('bool') is True


class TestStateSet:
    """Tests for State.set()"""

    def test_set_new_key(self, state):
        """Should set new key-value pair."""
        state.set('name', 'test')
        assert state._state['name'] == 'test'

    def test_set_overwrites_existing(self, state):
        """Should overwrite existing key."""
        state.set('count', 10)
        assert state._state['count'] == 10

        state.set('count', 20)
        assert state._state['count'] == 20

    def test_set_various_types(self, state):
        """Should handle various value types."""
        state.set('string', "hello")
        state.set('int', 123)
        state.set('float', 45.67)
        state.set('list', [1, 2, 3])
        state.set('dict', {'key': 'value'})
        state.set('bool', False)

        assert state._state['string'] == "hello"
        assert state._state['int'] == 123
        assert state._state['float'] == 45.67
        assert state._state['list'] == [1, 2, 3]
        assert state._state['dict'] == {'key': 'value'}
        assert state._state['bool'] is False

    def test_set_none_value(self, state):
        """Should allow setting None as value."""
        state.set('nullable', None)
        assert state._state['nullable'] is None


class TestStateIncrement:
    """Tests for State.increment()"""

    def test_increment_nonexistent_key(self, state):
        """Should initialize to 0 and increment."""
        result = state.increment('count')
        assert result == 1
        assert state._state['count'] == 1

    def test_increment_existing_key(self, state):
        """Should increment existing numeric value."""
        state._state['count'] = 5
        result = state.increment('count')
        assert result == 6
        assert state._state['count'] == 6

    def test_increment_with_custom_amount(self, state):
        """Should increment by specified amount."""
        state._state['score'] = 10
        result = state.increment('score', 5)
        assert result == 15
        assert state._state['score'] == 15

    def test_increment_with_negative_amount(self, state):
        """Should decrement when amount is negative."""
        state._state['count'] = 10
        result = state.increment('count', -3)
        assert result == 7
        assert state._state['count'] == 7

    def test_increment_with_float(self, state):
        """Should handle float increments."""
        state._state['value'] = 1.5
        result = state.increment('value', 0.5)
        assert result == 2.0
        assert state._state['value'] == 2.0

    def test_increment_nonexistent_with_amount(self, state):
        """Should initialize to 0 and add amount."""
        result = state.increment('new_key', 10)
        assert result == 10
        assert state._state['new_key'] == 10

    def test_increment_nonnumeric_value_resets(self, state):
        """Should reset non-numeric values to 0 and increment."""
        state._state['bad_value'] = "not a number"
        result = state.increment('bad_value')
        assert result == 1
        assert state._state['bad_value'] == 1

    def test_increment_returns_new_value(self, state):
        """Should return the new value after increment."""
        state._state['counter'] = 0
        assert state.increment('counter') == 1
        assert state.increment('counter') == 2
        assert state.increment('counter') == 3


class TestStateAppend:
    """Tests for State.append()"""

    def test_append_to_nonexistent_key(self, state):
        """Should create new list and append."""
        state.append('items', 'first')
        assert state._state['items'] == ['first']

    def test_append_to_existing_list(self, state):
        """Should append to existing list."""
        state._state['items'] = ['first']
        state.append('items', 'second')
        assert state._state['items'] == ['first', 'second']

    def test_append_multiple_values(self, state):
        """Should append multiple values in order."""
        state.append('items', 1)
        state.append('items', 2)
        state.append('items', 3)
        assert state._state['items'] == [1, 2, 3]

    def test_append_various_types(self, state):
        """Should append various value types."""
        state.append('mixed', 'string')
        state.append('mixed', 123)
        state.append('mixed', {'key': 'value'})
        state.append('mixed', [1, 2, 3])
        assert state._state['mixed'] == ['string', 123, {'key': 'value'}, [1, 2, 3]]

    def test_append_to_nonlist_converts(self, state):
        """Should convert non-list values to list."""
        state._state['single'] = 'value'
        state.append('single', 'new_value')
        assert state._state['single'] == ['value', 'new_value']

    def test_append_preserves_list_order(self, state):
        """Should maintain insertion order."""
        for i in range(10):
            state.append('ordered', i)
        assert state._state['ordered'] == list(range(10))


class TestStateAll:
    """Tests for State.all()"""

    def test_all_returns_empty_dict_initially(self, state):
        """Should return empty dict for new state."""
        assert state.all() == {}

    def test_all_returns_all_state(self, state):
        """Should return all key-value pairs."""
        state._state['a'] = 1
        state._state['b'] = 2
        state._state['c'] = 3

        result = state.all()
        assert result == {'a': 1, 'b': 2, 'c': 3}

    def test_all_returns_copy(self, state):
        """Should return a copy, not the original dict."""
        state._state['key'] = 'value'
        result = state.all()

        # Modify the returned dict
        result['key'] = 'modified'
        result['new_key'] = 'new_value'

        # Original should be unchanged
        assert state._state == {'key': 'value'}
        assert 'new_key' not in state._state

    def test_all_with_complex_state(self, state):
        """Should return complex state structures."""
        state._state['string'] = "hello"
        state._state['number'] = 42
        state._state['list'] = [1, 2, 3]
        state._state['dict'] = {'nested': 'value'}

        result = state.all()
        assert result == {
            'string': "hello",
            'number': 42,
            'list': [1, 2, 3],
            'dict': {'nested': 'value'}
        }


class TestStateClear:
    """Tests for State.clear()"""

    def test_clear_empty_state(self, state):
        """Should handle clearing empty state."""
        state.clear()
        assert state._state == {}

    def test_clear_removes_all_state(self, state):
        """Should remove all key-value pairs."""
        state._state['a'] = 1
        state._state['b'] = 2
        state._state['c'] = 3

        state.clear()
        assert state._state == {}
        assert len(state._state) == 0

    def test_clear_allows_new_values(self, state):
        """Should allow setting new values after clear."""
        state._state['old'] = 'value'
        state.clear()

        state.set('new', 'value')
        assert state._state == {'new': 'value'}


class TestStateIntegration:
    """Integration tests combining multiple operations."""

    def test_typical_workflow(self, state):
        """Test typical state management workflow."""
        # Initialize counters
        state.set('phase', 'initialization')
        state.set('attempts', 0)

        # Track items
        state.append('processed_items', 'item1')
        state.append('processed_items', 'item2')

        # Increment counter
        state.increment('attempts')
        state.increment('attempts')

        # Check state
        all_state = state.all()
        assert all_state['phase'] == 'initialization'
        assert all_state['attempts'] == 2
        assert all_state['processed_items'] == ['item1', 'item2']

    def test_accumulator_pattern(self, state):
        """Test accumulating results over multiple operations."""
        state.set('total_score', 0)
        state.append('results', 'pass')

        # Simulate multiple rounds
        for i in range(5):
            state.increment('total_score', 10)
            state.append('results', f'result_{i}')

        assert state.get('total_score') == 50
        assert len(state.get('results')) == 6  # initial + 5

    def test_state_persistence_simulation(self, state):
        """Test that state persists across operations."""
        # Simulate agent turn 1
        state.set('current_node', 'node_1')
        state.append('visited_nodes', 'node_1')
        state.increment('depth')

        # Simulate agent turn 2
        state.set('current_node', 'node_2')
        state.append('visited_nodes', 'node_2')
        state.increment('depth')

        # Check persistence
        assert state.get('current_node') == 'node_2'
        assert state.get('visited_nodes') == ['node_1', 'node_2']
        assert state.get('depth') == 2

    def test_conditional_state_updates(self, state):
        """Test conditional logic with state."""
        state.set('retry_count', 0)
        max_retries = 3

        # Simulate retries
        while state.get('retry_count') < max_retries:
            state.increment('retry_count')
            state.append('retry_timestamps', f'attempt_{state.get("retry_count")}')

        assert state.get('retry_count') == 3
        assert len(state.get('retry_timestamps')) == 3

    def test_reset_and_reuse(self, state):
        """Test clearing and reusing state."""
        # First use
        state.set('phase', 'phase1')
        state.increment('count')
        state.append('items', 'item1')

        # Reset
        state.clear()
        assert state.all() == {}

        # Second use
        state.set('phase', 'phase2')
        state.increment('count')
        state.append('items', 'item2')

        # Should have fresh state
        assert state.get('phase') == 'phase2'
        assert state.get('count') == 1
        assert state.get('items') == ['item2']


class TestStateEdgeCases:
    """Edge case and error condition tests."""

    def test_empty_string_key(self, state):
        """Should handle empty string as key."""
        state.set('', 'value')
        assert state.get('') == 'value'

    def test_special_character_keys(self, state):
        """Should handle keys with special characters."""
        state.set('key-with-dash', 1)
        state.set('key.with.dot', 2)
        state.set('key_with_underscore', 3)
        state.set('key with space', 4)

        assert state.get('key-with-dash') == 1
        assert state.get('key.with.dot') == 2
        assert state.get('key_with_underscore') == 3
        assert state.get('key with space') == 4

    def test_large_list_append(self, state):
        """Should handle appending many items."""
        for i in range(1000):
            state.append('large_list', i)

        assert len(state.get('large_list')) == 1000
        assert state.get('large_list')[0] == 0
        assert state.get('large_list')[999] == 999

    def test_zero_increment(self, state):
        """Should handle incrementing by zero."""
        state.set('value', 5)
        result = state.increment('value', 0)
        assert result == 5
        assert state.get('value') == 5

    def test_very_large_numbers(self, state):
        """Should handle very large numbers."""
        large_num = 10**15
        state.set('big', large_num)
        result = state.increment('big', large_num)
        assert result == large_num * 2

    def test_negative_numbers(self, state):
        """Should handle negative numbers."""
        state.set('negative', -10)
        assert state.get('negative') == -10

        result = state.increment('negative', -5)
        assert result == -15


class TestStateRepr:
    """Tests for __repr__()"""

    def test_repr_empty(self, state):
        """Should show 0 keys for empty state."""
        assert repr(state) == "StatePrimitive(0 keys)"

    def test_repr_with_keys(self, state):
        """Should show correct key count."""
        state.set('a', 1)
        state.set('b', 2)
        state.set('c', 3)
        assert repr(state) == "StatePrimitive(3 keys)"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
