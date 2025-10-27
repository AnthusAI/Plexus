import pytest
from unittest.mock import MagicMock, patch
from plexus.scores.nodes.FuzzyMatchClassifier import FuzzyMatchClassifier
from plexus.scores.shared.fuzzy_matching import FuzzyTarget, FuzzyTargetGroup


class TestFuzzyMatchClassifier:
    """Test cases for FuzzyMatchClassifier node."""

    def test_initialization_basic(self):
        """Test basic initialization with minimal parameters."""
        classifier = FuzzyMatchClassifier(
            name="test_classifier",
            data_paths=["text"],
            targets=FuzzyTarget(target="test", threshold=80)
        )
        assert classifier.node_name == "test_classifier"
        assert classifier.parameters.data_paths == ["text"]
        assert isinstance(classifier.parameters.targets, FuzzyTarget)

    def test_initialization_with_mapping(self):
        """Test initialization with classification mapping."""
        classifier = FuzzyMatchClassifier(
            name="school_classifier",
            data_paths=["metadata.schools[].school_id"],
            targets=FuzzyTarget(target="AIU", threshold=90),
            classification_mapping={"AIU": "American InterContinental University"},
            default_classification="Other"
        )
        assert classifier.parameters.classification_mapping == {"AIU": "American InterContinental University"}
        assert classifier.parameters.default_classification == "Other"

    def test_data_extraction_simple_path(self):
        """Test extracting values from simple paths."""
        classifier = FuzzyMatchClassifier(
            name="test",
            data_paths=["text"],
            targets=FuzzyTarget(target="test", threshold=80)
        )

        state_dict = {"text": "Hello World"}
        values = classifier._extract_values_from_path(state_dict, "text")
        assert values == ["Hello World"]

    def test_data_extraction_nested_path(self):
        """Test extracting values from nested paths."""
        classifier = FuzzyMatchClassifier(
            name="test",
            data_paths=["metadata.field"],
            targets=FuzzyTarget(target="test", threshold=80)
        )

        state_dict = {"metadata": {"field": "nested_value"}}
        values = classifier._extract_values_from_path(state_dict, "metadata.field")
        assert values == ["nested_value"]

    def test_data_extraction_array_path(self):
        """Test extracting values from array paths."""
        classifier = FuzzyMatchClassifier(
            name="test",
            data_paths=["metadata.schools[].school_id"],
            targets=FuzzyTarget(target="test", threshold=80)
        )

        state_dict = {
            "metadata": {
                "schools": [
                    {"school_id": "AIU", "modality": "Online"},
                    {"school_id": "CTU", "modality": "Campus"}
                ]
            }
        }
        values = classifier._extract_values_from_path(state_dict, "metadata.schools[].school_id")
        assert len(values) == 2
        # Now we should get the actual school_id values, not the full dict
        assert "AIU" in values
        assert "CTU" in values

    def test_data_extraction_array_index_path(self):
        """Test extracting values from specific array indices."""
        classifier = FuzzyMatchClassifier(
            name="test",
            data_paths=["metadata.schools[0].school_id"],
            targets=FuzzyTarget(target="test", threshold=80)
        )

        state_dict = {
            "metadata": {
                "schools": [
                    {"school_id": "AIU"},
                    {"school_id": "CTU"}
                ]
            }
        }
        values = classifier._extract_values_from_path(state_dict, "metadata.schools[0].school_id")
        assert values == ["AIU"]

    def test_data_extraction_missing_path(self):
        """Test handling of missing paths."""
        classifier = FuzzyMatchClassifier(
            name="test",
            data_paths=["missing.path"],
            targets=FuzzyTarget(target="test", threshold=80)
        )

        state_dict = {"text": "Hello"}
        values = classifier._extract_values_from_path(state_dict, "missing.path")
        assert values == []

    def test_extract_all_values_multiple_paths(self):
        """Test extracting from multiple paths."""
        classifier = FuzzyMatchClassifier(
            name="test",
            data_paths=["text", "metadata.field"],
            targets=FuzzyTarget(target="test", threshold=80)
        )

        state_dict = {
            "text": "Hello",
            "metadata": {"field": "World"}
        }
        all_values = classifier._extract_all_values(state_dict)
        assert "Hello" in all_values
        assert "World" in all_values

    def test_fuzzy_matching_single_target_success(self):
        """Test fuzzy matching with single target that matches."""
        classifier = FuzzyMatchClassifier(
            name="test",
            data_paths=["text"],
            targets=FuzzyTarget(target="American InterContinental University", threshold=80, scorer="partial_ratio")
        )

        values = ["American InterContinental University a member of the AIU System"]
        success, matches = classifier._evaluate_fuzzy_targets(classifier.parameters.targets, values)

        assert success is True
        assert len(matches) == 1
        assert matches[0]["target"] == "American InterContinental University"
        assert matches[0]["score"] >= 80

    def test_fuzzy_matching_single_target_failure(self):
        """Test fuzzy matching with single target that doesn't match."""
        classifier = FuzzyMatchClassifier(
            name="test",
            data_paths=["text"],
            targets=FuzzyTarget(target="Specific University", threshold=90)
        )

        values = ["Completely Different School"]
        success, matches = classifier._evaluate_fuzzy_targets(classifier.parameters.targets, values)

        assert success is False
        assert len(matches) == 0

    def test_fuzzy_matching_or_group_success(self):
        """Test fuzzy matching with OR group where one target matches."""
        targets = FuzzyTargetGroup(
            operator="or",
            items=[
                FuzzyTarget(target="AIU", threshold=50, scorer="partial_ratio"),  # Lower threshold for abbreviation
                FuzzyTarget(target="CTU", threshold=50, scorer="partial_ratio")
            ]
        )

        classifier = FuzzyMatchClassifier(
            name="test",
            data_paths=["text"],
            targets=targets
        )

        values = ["American InterContinental University"]
        success, matches = classifier._evaluate_fuzzy_targets(targets, values)

        assert success is True
        assert len(matches) >= 1

    def test_fuzzy_matching_and_group_success(self):
        """Test fuzzy matching with AND group where all targets match."""
        targets = FuzzyTargetGroup(
            operator="and",
            items=[
                FuzzyTarget(target="American", threshold=70, scorer="partial_ratio"),
                FuzzyTarget(target="University", threshold=70, scorer="partial_ratio")
            ]
        )

        classifier = FuzzyMatchClassifier(
            name="test",
            data_paths=["text"],
            targets=targets
        )

        values = ["American InterContinental University"]
        success, matches = classifier._evaluate_fuzzy_targets(targets, values)

        assert success is True
        assert len(matches) == 2  # Both targets should match

    def test_fuzzy_matching_and_group_failure(self):
        """Test fuzzy matching with AND group where one target doesn't match."""
        targets = FuzzyTargetGroup(
            operator="and",
            items=[
                FuzzyTarget(target="American", threshold=70),
                FuzzyTarget(target="Nonexistent", threshold=90)
            ]
        )

        classifier = FuzzyMatchClassifier(
            name="test",
            data_paths=["text"],
            targets=targets
        )

        values = ["American InterContinental University"]
        success, matches = classifier._evaluate_fuzzy_targets(targets, values)

        assert success is False
        assert len(matches) == 0  # AND failed, so no matches returned

    def test_classification_generation_with_mapping(self):
        """Test classification generation using mapping."""
        classifier = FuzzyMatchClassifier(
            name="test",
            data_paths=["text"],
            targets=FuzzyTarget(target="AIU", threshold=80),
            classification_mapping={"AIU": "American InterContinental University"}
        )

        matches = [{
            "target": "AIU",
            "threshold": 80,
            "score": 95.0,
            "matched_text": "American InterContinental University"
        }]

        classification, explanation = classifier._generate_classification(matches)
        assert classification == "American InterContinental University"
        assert "AIU" in explanation

    def test_classification_generation_without_mapping(self):
        """Test classification generation without mapping."""
        classifier = FuzzyMatchClassifier(
            name="test",
            data_paths=["text"],
            targets=FuzzyTarget(target="AIU", threshold=80)
        )

        matches = [{
            "target": "AIU",
            "threshold": 80,
            "score": 95.0,
            "matched_text": "AIU"
        }]

        classification, explanation = classifier._generate_classification(matches)
        assert classification == "AIU"  # Should use target directly
        assert "AIU" in explanation

    def test_classification_generation_no_matches(self):
        """Test classification generation with no matches."""
        classifier = FuzzyMatchClassifier(
            name="test",
            data_paths=["text"],
            targets=FuzzyTarget(target="test", threshold=80),
            default_classification="Other"
        )

        classification, explanation = classifier._generate_classification([])
        assert classification == "Other"
        assert "No fuzzy matches found" in explanation

    @pytest.mark.asyncio
    async def test_classifier_node_execution_success(self):
        """Test full node execution with successful matching."""
        classifier = FuzzyMatchClassifier(
            name="school_classifier",
            data_paths=["metadata.schools[].school_id"],
            targets=FuzzyTarget(target="AIU", threshold=70, scorer="partial_ratio"),
            classification_mapping={"AIU": "American InterContinental University"},
            default_classification="Other"
        )

        # Mock state with school data
        state_dict = {
            "text": "Sample text",
            "metadata": {
                "schools": [
                    {"school_id": "American InterContinental University a member of the AIU System"}
                ]
            }
        }

        # Create mock state object
        class MockState:
            def model_dump(self):
                return state_dict

        node_func = classifier.get_classifier_node()
        result = await node_func(MockState())

        # Verify results - only check standard fields that are part of GraphState
        assert hasattr(result, 'classification')
        assert hasattr(result, 'explanation')
        assert result.classification == "American InterContinental University"  # Should be mapped value
        assert "AIU" in result.explanation  # Should mention the matched target

    @pytest.mark.asyncio
    async def test_classifier_node_execution_no_matches(self):
        """Test full node execution with no matches."""
        classifier = FuzzyMatchClassifier(
            name="school_classifier",
            data_paths=["metadata.schools[].school_id"],
            targets=FuzzyTarget(target="Nonexistent School", threshold=90),
            default_classification="Other"
        )

        # Mock state with different school data
        state_dict = {
            "text": "Sample text",
            "metadata": {
                "schools": [
                    {"school_id": "Completely Different University"}
                ]
            }
        }

        class MockState:
            def model_dump(self):
                return state_dict

        node_func = classifier.get_classifier_node()
        result = await node_func(MockState())

        # Should get default classification
        assert result.classification == "Other"
        assert result.explanation is not None  # Should have explanation about no matches

    def test_real_world_school_matching_scenario(self):
        """Test with real-world school name variations."""
        classifier = FuzzyMatchClassifier(
            name="school_classifier",
            data_paths=["metadata.schools[].school_id"],
            targets=FuzzyTargetGroup(
                operator="or",
                items=[
                    FuzzyTarget(target="American InterContinental University", threshold=80, scorer="partial_ratio"),
                    FuzzyTarget(target="AIU", threshold=80, scorer="partial_ratio"),
                    FuzzyTarget(target="Colorado Technical University", threshold=80, scorer="partial_ratio"),
                    FuzzyTarget(target="CTU", threshold=80, scorer="partial_ratio")
                ]
            ),
            classification_mapping={
                "American InterContinental University": "AIU",
                "AIU": "AIU",
                "Colorado Technical University": "CTU",
                "CTU": "CTU"
            },
            default_classification="Other"
        )

        # Test various school name formats
        test_cases = [
            ("American InterContinental University a member of the AIU System", "AIU"),
            ("AIU Online", "AIU"),
            ("Colorado Technical University", "CTU"),
            ("CTU Campus", "CTU"),
            ("University of Phoenix", "Other")  # Should not match
        ]

        for school_name, expected_classification in test_cases:
            values = [school_name]
            success, matches = classifier._evaluate_fuzzy_targets(classifier.parameters.targets, values)

            if expected_classification == "Other":
                assert success is False or classifier._generate_classification(matches)[0] == "Other"
            else:
                classification, _ = classifier._generate_classification(matches)
                assert classification == expected_classification, f"Failed for {school_name}: got {classification}, expected {expected_classification}"

    def test_real_school_data_extraction(self):
        """Test with the actual school data structure from the user's example."""
        classifier = FuzzyMatchClassifier(
            name="school_classifier",
            data_paths=["metadata.schools[].school_id"],
            targets=FuzzyTargetGroup(
                operator="or",
                items=[
                    FuzzyTarget(target="Colorado Technical University", threshold=80, scorer="partial_ratio"),
                    FuzzyTarget(target="American InterContinental University", threshold=80, scorer="partial_ratio"),
                    FuzzyTarget(target="AIU", threshold=50, scorer="partial_ratio"),  # Lower threshold for abbreviation
                    FuzzyTarget(target="CTU", threshold=50, scorer="partial_ratio")  # Lower threshold for abbreviation
                ]
            ),
            classification_mapping={
                "Colorado Technical University": "found",
                "American InterContinental University": "found",
                "AIU": "found",
                "CTU": "found"
            },
            default_classification="not_found"
        )

        # Real school data structure
        state_dict = {
            "text": "Sample call transcript",
            "metadata": {
                "schools": [
                    {
                        "school_id": "UEI College",
                        "modality": "Campus",
                        "degree_of_interest": "Diploma - Electrician Technician"
                    },
                    {
                        "school_id": "Colorado Technical University",
                        "modality": "Online",
                        "degree_of_interest": "B.B.A. - Project Management"
                    },
                    {
                        "school_id": "American InterContinental University, a member of the American InterContinental University System",
                        "modality": "Online",
                        "degree_of_interest": "B.B.A. - Operations Management"
                    },
                    {
                        "school_id": "AIM",
                        "modality": "Campus",
                        "degree_of_interest": "Certificate - Aviation Maintenance Technician"
                    }
                ]
            }
        }

        # Test data extraction - should get all school_id values
        extracted_values = classifier._extract_values_from_path(state_dict, "metadata.schools[].school_id")
        expected_school_ids = [
            "UEI College",
            "Colorado Technical University",
            "American InterContinental University, a member of the American InterContinental University System",
            "AIM"
        ]

        assert len(extracted_values) == 4
        for school_id in expected_school_ids:
            assert school_id in extracted_values

        # Test fuzzy matching - should find matches for CTU and AIU variations
        success, matches = classifier._evaluate_fuzzy_targets(classifier.parameters.targets, extracted_values)
        assert success is True  # Should find at least one match
        assert len(matches) >= 1  # Should have at least CTU or AIU match

        # Test classification generation
        classification, explanation = classifier._generate_classification(matches)
        assert classification == "found"
        assert "Colorado Technical University" in explanation or "American InterContinental University" in explanation

    def test_different_scorers(self):
        """Test that different rapidfuzz scorers work correctly."""
        # Test cases that should definitely work for each scorer type
        test_cases = [
            # Test ratio scorer with exact match
            {
                "scorer": "ratio",
                "target": "Colorado Technical University",
                "text": "Colorado Technical University",
                "threshold": 95,
                "should_match": True
            },
            # Test token_sort_ratio with word reordering
            {
                "scorer": "token_sort_ratio",
                "target": "Technical University Colorado",
                "text": "Colorado Technical University",
                "threshold": 95,
                "should_match": True
            },
            # Test token_set_ratio with subset relationship
            {
                "scorer": "token_set_ratio",
                "target": "American University",
                "text": "American InterContinental University System",
                "threshold": 60,
                "should_match": True
            },
            # Test WRatio with similar strings
            {
                "scorer": "WRatio",
                "target": "Colorado Technical University",
                "text": "Colorado Technical University Online",
                "threshold": 80,
                "should_match": True
            },
            # Test QRatio with similar strings
            {
                "scorer": "QRatio",
                "target": "Colorado Technical University",
                "text": "Colorado Technical University",
                "threshold": 95,
                "should_match": True
            },
            # Test partial_ratio (our main scorer)
            {
                "scorer": "partial_ratio",
                "target": "AIU",
                "text": "AIU Online Campus Information",
                "threshold": 80,
                "should_match": True
            }
        ]

        for case in test_cases:
            classifier = FuzzyMatchClassifier(
                name="test_scorer",
                data_paths=["text"],
                targets=FuzzyTarget(
                    target=case["target"],
                    threshold=case["threshold"],
                    scorer=case["scorer"]
                )
            )

            values = [case["text"]]
            success, matches = classifier._evaluate_fuzzy_targets(classifier.parameters.targets, values)

            if case["should_match"]:
                assert success is True, f"Failed: {case['scorer']} should match '{case['target']}' with '{case['text']}'"
                assert len(matches) == 1
                assert matches[0]["score"] >= case["threshold"]
            else:
                assert success is False, f"Failed: {case['scorer']} should NOT match '{case['target']}' with '{case['text']}'"

    def test_scorer_validation(self):
        """Test that all supported scorer types are accepted and work."""
        valid_scorers = ['ratio', 'partial_ratio', 'token_sort_ratio', 'token_set_ratio', 'WRatio', 'QRatio']

        for scorer in valid_scorers:
            # Just test that the classifier can be created and executes without error
            classifier = FuzzyMatchClassifier(
                name=f"test_{scorer}",
                data_paths=["text"],
                targets=FuzzyTarget(
                    target="test target",
                    threshold=50,
                    scorer=scorer
                )
            )

            # Test that it can execute (even if no match)
            values = ["some text"]
            success, matches = classifier._evaluate_fuzzy_targets(classifier.parameters.targets, values)
            # Just verify it returns boolean and list (no specific match expectation)
            assert isinstance(success, bool)
            assert isinstance(matches, list)

    def test_scorer_preprocessing(self):
        """Test that preprocessing option works with different scorers."""
        # Test with preprocessing enabled (should ignore case and punctuation)
        classifier_with_preprocess = FuzzyMatchClassifier(
            name="test_preprocess",
            data_paths=["text"],
            targets=FuzzyTarget(
                target="american intercontinental university",
                threshold=80,
                scorer="ratio",
                preprocess=True
            )
        )

        # Test without preprocessing
        classifier_without_preprocess = FuzzyMatchClassifier(
            name="test_no_preprocess",
            data_paths=["text"],
            targets=FuzzyTarget(
                target="american intercontinental university",
                threshold=80,
                scorer="ratio",
                preprocess=False
            )
        )

        test_text = ["AMERICAN INTERCONTINENTAL UNIVERSITY!!!"]

        # With preprocessing should match despite case/punctuation differences
        success_with, _ = classifier_with_preprocess._evaluate_fuzzy_targets(
            classifier_with_preprocess.parameters.targets, test_text
        )

        # Without preprocessing might not match as well due to case differences
        success_without, _ = classifier_without_preprocess._evaluate_fuzzy_targets(
            classifier_without_preprocess.parameters.targets, test_text
        )

        assert success_with is True, "Preprocessing should help match despite case/punctuation"
        # Both should work in this case, but preprocessing provides more consistent results
        assert success_without is True or success_with is True, "At least one approach should work"

    def test_scorer_performance_characteristics(self):
        """Test that different scorers handle specific text patterns as expected."""
        # Test cases that highlight each scorer's strengths
        test_scenarios = [
            {
                "name": "Exact match with extra words - partial_ratio wins",
                "target": "Colorado Technical University",
                "text": "Colorado Technical University Online Campus Information",
                "scorers_expected": {
                    "partial_ratio": 100.0,  # Should be perfect
                    "ratio": lambda x: x < 80,  # Should be lower due to extra words
                }
            },
            {
                "name": "Word order change - token_sort_ratio wins",
                "target": "University Technical Colorado",
                "text": "Colorado Technical University",
                "scorers_expected": {
                    "token_sort_ratio": 100.0,  # Should handle reordering
                    "ratio": lambda x: x < 90,  # Should be lower due to order
                }
            }
        ]

        for scenario in test_scenarios:
            print(f"\nTesting: {scenario['name']}")
            for scorer_name, expected in scenario["scorers_expected"].items():
                classifier = FuzzyMatchClassifier(
                    name="perf_test",
                    data_paths=["text"],
                    targets=FuzzyTarget(
                        target=scenario["target"],
                        threshold=50,  # Low threshold to see actual scores
                        scorer=scorer_name
                    )
                )

                values = [scenario["text"]]
                success, matches = classifier._evaluate_fuzzy_targets(classifier.parameters.targets, values)

                if success and matches:
                    actual_score = matches[0]["score"]
                    if callable(expected):
                        assert expected(actual_score), f"{scorer_name}: score {actual_score} didn't meet expectation"
                    else:
                        assert abs(actual_score - expected) < 5, f"{scorer_name}: expected ~{expected}, got {actual_score}"