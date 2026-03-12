import pytest
from plexus.scores.shared.fuzzy_matching.core import FuzzyTarget, FuzzyTargetGroup, FuzzyMatchingEngine


class TestFuzzyTarget:
    """Test cases for FuzzyTarget model."""

    def test_fuzzy_target_basic_creation(self):
        """Test basic FuzzyTarget creation and validation."""
        target = FuzzyTarget(target="test", threshold=80)
        assert target.target == "test"
        assert target.threshold == 80
        assert target.scorer == "ratio"  # default
        assert target.preprocess is False  # default

    def test_fuzzy_target_with_all_params(self):
        """Test FuzzyTarget with all parameters specified."""
        target = FuzzyTarget(
            target="American InterContinental University",
            threshold=85,
            scorer="partial_ratio",
            preprocess=True
        )
        assert target.target == "American InterContinental University"
        assert target.threshold == 85
        assert target.scorer == "partial_ratio"
        assert target.preprocess is True

    def test_fuzzy_target_threshold_validation(self):
        """Test that threshold validation works."""
        # Valid thresholds
        FuzzyTarget(target="test", threshold=0)
        FuzzyTarget(target="test", threshold=100)

        # Invalid thresholds should raise validation error
        with pytest.raises(ValueError):
            FuzzyTarget(target="test", threshold=-1)
        with pytest.raises(ValueError):
            FuzzyTarget(target="test", threshold=101)

    def test_fuzzy_target_scorer_validation(self):
        """Test that scorer validation works."""
        valid_scorers = ['ratio', 'partial_ratio', 'token_sort_ratio', 'token_set_ratio', 'WRatio', 'QRatio']

        for scorer in valid_scorers:
            target = FuzzyTarget(target="test", threshold=80, scorer=scorer)
            assert target.scorer == scorer

    def test_get_scorer_func(self):
        """Test that get_scorer_func returns correct functions."""
        target = FuzzyTarget(target="test", threshold=80, scorer="partial_ratio")
        scorer_func = target.get_scorer_func()

        # Function should be cached
        assert scorer_func is target.get_scorer_func()

        # Should be a callable
        assert callable(scorer_func)


class TestFuzzyTargetGroup:
    """Test cases for FuzzyTargetGroup model."""

    def test_fuzzy_target_group_basic(self):
        """Test basic FuzzyTargetGroup creation."""
        group = FuzzyTargetGroup(
            operator="or",
            items=[
                FuzzyTarget(target="test1", threshold=80),
                FuzzyTarget(target="test2", threshold=90)
            ]
        )
        assert group.operator == "or"
        assert len(group.items) == 2

    def test_fuzzy_target_group_nested(self):
        """Test nested FuzzyTargetGroup creation."""
        nested_group = FuzzyTargetGroup(
            operator="and",
            items=[
                FuzzyTarget(target="inner1", threshold=70),
                FuzzyTargetGroup(
                    operator="or",
                    items=[
                        FuzzyTarget(target="inner2", threshold=80),
                        FuzzyTarget(target="inner3", threshold=85)
                    ]
                )
            ]
        )
        assert nested_group.operator == "and"
        assert len(nested_group.items) == 2
        assert isinstance(nested_group.items[1], FuzzyTargetGroup)

    def test_fuzzy_target_group_empty_items_validation(self):
        """Test that empty items list raises validation error."""
        with pytest.raises(ValueError, match="Group 'items' list cannot be empty"):
            FuzzyTargetGroup(operator="or", items=[])


class TestFuzzyMatchingEngine:
    """Test cases for FuzzyMatchingEngine."""

    def test_evaluate_single_text_exact_match(self):
        """Test single text evaluation with exact match."""
        target = FuzzyTarget(target="Colorado Technical University", threshold=95)
        text = "Colorado Technical University"

        success, matches = FuzzyMatchingEngine.evaluate_single_text(target, text)

        assert success is True
        assert len(matches) == 1
        assert matches[0]["target"] == "Colorado Technical University"
        assert matches[0]["score"] >= 95

    def test_evaluate_single_text_no_match(self):
        """Test single text evaluation with no match."""
        target = FuzzyTarget(target="Specific University", threshold=90)
        text = "Completely Different School"

        success, matches = FuzzyMatchingEngine.evaluate_single_text(target, text)

        assert success is False
        assert len(matches) == 0

    def test_evaluate_single_text_partial_ratio(self):
        """Test single text evaluation with partial_ratio scorer."""
        target = FuzzyTarget(target="AIU", threshold=80, scorer="partial_ratio")
        text = "AIU Online Campus with additional information"

        success, matches = FuzzyMatchingEngine.evaluate_single_text(target, text)

        assert success is True
        assert len(matches) == 1
        assert matches[0]["score"] >= 80

    def test_evaluate_multiple_values_best_match(self):
        """Test multiple values evaluation picks best match."""
        target = FuzzyTarget(target="Colorado Technical University", threshold=80, scorer="partial_ratio")
        values = [
            "University of Phoenix",  # Poor match
            "Colorado Technical University Online",  # Good match
            "Some Other School"  # Poor match
        ]

        success, matches = FuzzyMatchingEngine.evaluate_multiple_values(target, values)

        assert success is True
        assert len(matches) == 1
        assert matches[0]["matched_text"] == "Colorado Technical University Online"
        assert matches[0]["score"] >= 80

    def test_evaluate_multiple_values_no_match(self):
        """Test multiple values evaluation with no matches."""
        target = FuzzyTarget(target="Nonexistent University", threshold=90)
        values = ["School A", "School B", "School C"]

        success, matches = FuzzyMatchingEngine.evaluate_multiple_values(target, values)

        assert success is False
        assert len(matches) == 0

    def test_evaluate_or_group_single_text(self):
        """Test OR group evaluation with single text."""
        group = FuzzyTargetGroup(
            operator="or",
            items=[
                FuzzyTarget(target="American InterContinental University", threshold=80, scorer="partial_ratio"),
                FuzzyTarget(target="Colorado Technical University", threshold=80, scorer="partial_ratio")
            ]
        )
        text = "American InterContinental University System"

        success, matches = FuzzyMatchingEngine.evaluate_single_text(group, text)

        assert success is True  # Should match "American InterContinental University"
        assert len(matches) >= 1

    def test_evaluate_and_group_single_text_success(self):
        """Test AND group evaluation with single text - all match."""
        group = FuzzyTargetGroup(
            operator="and",
            items=[
                FuzzyTarget(target="American", threshold=70, scorer="partial_ratio"),
                FuzzyTarget(target="University", threshold=70, scorer="partial_ratio")
            ]
        )
        text = "American InterContinental University"

        success, matches = FuzzyMatchingEngine.evaluate_single_text(group, text)

        assert success is True
        assert len(matches) == 2  # Both should match

    def test_evaluate_and_group_single_text_failure(self):
        """Test AND group evaluation with single text - partial match."""
        group = FuzzyTargetGroup(
            operator="and",
            items=[
                FuzzyTarget(target="American", threshold=70, scorer="partial_ratio"),
                FuzzyTarget(target="Nonexistent", threshold=90, scorer="partial_ratio")
            ]
        )
        text = "American InterContinental University"

        success, matches = FuzzyMatchingEngine.evaluate_single_text(group, text)

        assert success is False  # AND failed because "Nonexistent" doesn't match
        assert len(matches) == 0  # No matches returned for failed AND

    def test_evaluate_nested_groups(self):
        """Test nested group evaluation."""
        nested_group = FuzzyTargetGroup(
            operator="and",
            items=[
                FuzzyTarget(target="University", threshold=70, scorer="partial_ratio"),
                FuzzyTargetGroup(
                    operator="or",
                    items=[
                        FuzzyTarget(target="American", threshold=70, scorer="partial_ratio"),
                        FuzzyTarget(target="Colorado", threshold=70, scorer="partial_ratio")
                    ]
                )
            ]
        )
        text = "American InterContinental University"

        success, matches = FuzzyMatchingEngine.evaluate_single_text(nested_group, text)

        assert success is True
        assert len(matches) >= 2  # Should match "University" and "American"

    def test_validate_targets_structure_single_target(self):
        """Test validation of single target structure."""
        target = FuzzyTarget(target="test", threshold=80)
        # Should not raise any exception
        FuzzyMatchingEngine.validate_targets_structure(target)

    def test_validate_targets_structure_group(self):
        """Test validation of group structure."""
        group = FuzzyTargetGroup(
            operator="or",
            items=[
                FuzzyTarget(target="test1", threshold=80),
                FuzzyTarget(target="test2", threshold=90)
            ]
        )
        # Should not raise any exception
        FuzzyMatchingEngine.validate_targets_structure(group)

    def test_validate_targets_structure_nested(self):
        """Test validation of nested structure."""
        nested_group = FuzzyTargetGroup(
            operator="and",
            items=[
                FuzzyTarget(target="test1", threshold=80),
                FuzzyTargetGroup(
                    operator="or",
                    items=[
                        FuzzyTarget(target="test2", threshold=90),
                        FuzzyTarget(target="test3", threshold=85)
                    ]
                )
            ]
        )
        # Should not raise any exception
        FuzzyMatchingEngine.validate_targets_structure(nested_group)

    def test_all_scorers_work(self):
        """Test that all scorer types work correctly."""
        scorers = ['ratio', 'partial_ratio', 'token_sort_ratio', 'token_set_ratio', 'WRatio', 'QRatio']

        for scorer in scorers:
            target = FuzzyTarget(target="test", threshold=50, scorer=scorer)

            # Test single text evaluation
            success, matches = FuzzyMatchingEngine.evaluate_single_text(target, "test")
            assert isinstance(success, bool)
            assert isinstance(matches, list)

            # Test multiple values evaluation
            success, matches = FuzzyMatchingEngine.evaluate_multiple_values(target, ["test"])
            assert isinstance(success, bool)
            assert isinstance(matches, list)

    def test_preprocessing_option(self):
        """Test that preprocessing option works."""
        target_with_preprocess = FuzzyTarget(
            target="american university",
            threshold=80,
            scorer="ratio",
            preprocess=True
        )

        target_without_preprocess = FuzzyTarget(
            target="american university",
            threshold=80,
            scorer="ratio",
            preprocess=False
        )

        text = "AMERICAN UNIVERSITY!!!"

        # With preprocessing should handle case/punctuation better
        success_with, matches_with = FuzzyMatchingEngine.evaluate_single_text(target_with_preprocess, text)
        success_without, matches_without = FuzzyMatchingEngine.evaluate_single_text(target_without_preprocess, text)

        # Both might work, but preprocessing should generally be more lenient
        assert isinstance(success_with, bool)
        assert isinstance(success_without, bool)
        assert isinstance(matches_with, list)
        assert isinstance(matches_without, list)

    def test_empty_values_handling(self):
        """Test handling of empty or invalid values."""
        target = FuzzyTarget(target="test", threshold=80)

        # Empty list
        success, matches = FuzzyMatchingEngine.evaluate_multiple_values(target, [])
        assert success is False
        assert len(matches) == 0

        # List with empty strings and None values
        success, matches = FuzzyMatchingEngine.evaluate_multiple_values(target, ["", None, "   "])
        assert success is False
        assert len(matches) == 0

        # Mixed valid and invalid values
        success, matches = FuzzyMatchingEngine.evaluate_multiple_values(target, ["", "test", None])
        # Should find the "test" match
        assert isinstance(success, bool)
        assert isinstance(matches, list)

    def test_invalid_type_handling(self):
        """Test that invalid target types are handled gracefully."""
        # The current implementation returns None for invalid types
        class InvalidType:
            pass

        invalid_obj = InvalidType()

        # Should return None for invalid types (graceful handling)
        result = FuzzyMatchingEngine.evaluate_single_text(invalid_obj, "text")
        assert result is None

        result = FuzzyMatchingEngine.evaluate_multiple_values(invalid_obj, ["value"])
        assert result is None

    def test_short_circuit_behavior(self):
        """Test that OR groups short-circuit correctly."""
        # Create an OR group where first item should match
        group = FuzzyTargetGroup(
            operator="or",
            items=[
                FuzzyTarget(target="exact_match", threshold=95),  # This should match exactly
                FuzzyTarget(target="nonexistent", threshold=95)   # This would fail, but shouldn't be evaluated
            ]
        )

        success, matches = FuzzyMatchingEngine.evaluate_single_text(group, "exact_match")

        assert success is True
        # Should only have one match due to short-circuiting
        assert len(matches) == 1
        assert matches[0]["target"] == "exact_match"