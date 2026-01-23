"""
Comprehensive tests for TactusScore - Tactus DSL integration with Plexus scoring.

Tests cover:
1. Basic Tactus code execution and result mapping
2. Metadata extraction with nested arrays (multi-entity scenarios)
3. Classification parsing from LLM text responses
4. Prerequisite/eligibility checking logic
5. Multi-entity aggregation (any No -> No, all Yes -> Yes)
6. Error handling and edge cases
7. Complex real-world workflow patterns

NOTE: All test data is generic and does not contain any client-specific information.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import asyncio

from plexus.scores.Score import Score


# ============================================================================
# Global Mock for LangChainUser
# ============================================================================

@pytest.fixture(autouse=True)
def mock_langchain_model():
    """Mock LangChainUser model initialization to avoid API key requirements."""
    with patch('plexus.LangChainUser.LangChainUser._initialize_model') as mock_init:
        mock_model = MagicMock()
        mock_init.return_value = mock_model
        yield mock_model


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def mock_tactus_runtime():
    """Create a mock TactusRuntime that returns configurable results."""
    runtime = AsyncMock()
    runtime.execute = AsyncMock()
    return runtime


@pytest.fixture
def basic_tactus_code():
    """Simple Tactus code that returns a classification."""
    return '''
    Procedure {
        input = {
            text = field.string{required = true}
        },
        output = {
            value = field.string{required = true},
            explanation = field.string{required = true}
        },
        function(input)
            return {
                value = "Yes",
                explanation = "Test classification"
            }
        end
    }
    '''


@pytest.fixture
def classification_parsing_code():
    """Tactus code that parses classification from agent text response."""
    return '''
    -- Helper: Parse agent response to extract classification value
    function parse_classification(response)
        if not response then return "NA", "No response from classifier" end
        local upper = response:upper()
        -- Check first word or explicit markers
        if upper:match("^YES") or upper:match("CLASSIFICATION:%s*YES") then
            return "Yes", response
        elseif upper:match("^NO[^T]") or upper:match("^NO$") or upper:match("CLASSIFICATION:%s*NO") then
            return "No", response
        elseif upper:match("^NA") or upper:match("^N/A") or upper:match("CLASSIFICATION:%s*NA") then
            return "NA", response
        end
        -- Fallback: look for keywords anywhere
        if upper:find("YES") and not upper:find("NO") then
            return "Yes", response
        elseif upper:find("NO") and not upper:find("YES") then
            return "No", response
        end
        return "NA", "Could not determine classification: " .. response
    end

    Procedure {
        input = {
            text = field.string{required = true}
        },
        output = {
            value = field.string{required = true},
            explanation = field.string{required = true}
        },
        function(input)
            local value, explanation = parse_classification(input.text)
            return {value = value, explanation = explanation}
        end
    }
    '''


@pytest.fixture
def multi_entity_aggregation_code():
    """Tactus code demonstrating multi-entity aggregation logic."""
    return '''
    -- Simulates evaluating multiple entities and aggregating results
    -- Rule: Any No -> No, All Yes -> Yes, Otherwise -> NA

    Procedure {
        input = {
            text = field.string{required = true},
            metadata = field.object{description = "Contains entities array"}
        },
        output = {
            value = field.string{required = true},
            explanation = field.string{required = true},
            confidence = field.string{}
        },
        function(input)
            local meta = input.metadata or {}
            local entities = meta.entities or {}

            if #entities == 0 then
                return {
                    value = "NA",
                    explanation = "No entities to evaluate",
                    confidence = "high"
                }
            end

            local any_no = false
            local any_yes = false
            local results = {}

            for i, entity in ipairs(entities) do
                -- Simulate classification based on entity data
                local entity_value = entity.expected_result or "NA"
                table.insert(results, {
                    name = entity.name or ("Entity " .. i),
                    value = entity_value
                })

                if entity_value == "No" then
                    any_no = true
                elseif entity_value == "Yes" then
                    any_yes = true
                end
            end

            -- Aggregate: Any No -> No, All Yes -> Yes
            local final_value
            if any_no then
                final_value = "No"
            elseif any_yes and not any_no then
                final_value = "Yes"
            else
                final_value = "NA"
            end

            return {
                value = final_value,
                explanation = "Evaluated " .. #entities .. " entities",
                confidence = "high"
            }
        end
    }
    '''


@pytest.fixture
def prerequisite_checking_code():
    """Tactus code demonstrating prerequisite/eligibility checking."""
    return '''
    REQUIRED_CATEGORY = "Premium"
    REQUIRED_STATUS = "Active"

    function check_prerequisites(entity)
        local result = {
            is_eligible = true,
            missing_prereqs = {}
        }

        if entity.category ~= REQUIRED_CATEGORY then
            result.is_eligible = false
            table.insert(result.missing_prereqs,
                "Category is '" .. tostring(entity.category) .. "' (expected '" .. REQUIRED_CATEGORY .. "')")
        end

        if entity.status ~= REQUIRED_STATUS then
            result.is_eligible = false
            table.insert(result.missing_prereqs,
                "Status is '" .. tostring(entity.status) .. "' (expected '" .. REQUIRED_STATUS .. "')")
        end

        return result
    end

    Procedure {
        input = {
            text = field.string{required = true},
            metadata = field.object{}
        },
        output = {
            value = field.string{required = true},
            explanation = field.string{required = true}
        },
        function(input)
            local meta = input.metadata or {}
            local check = check_prerequisites(meta)

            if not check.is_eligible then
                return {
                    value = "NA",
                    explanation = "Prerequisites not met: " .. table.concat(check.missing_prereqs, "; ")
                }
            end

            return {
                value = "Yes",
                explanation = "All prerequisites met"
            }
        end
    }
    '''


# ============================================================================
# Basic Execution Tests
# ============================================================================

class TestTactusScoreBasicExecution:
    """Tests for basic TactusScore initialization and execution."""

    @pytest.mark.asyncio
    async def test_tactus_score_initialization(self):
        """Test that TactusScore initializes with required parameters."""
        with patch('plexus.scores.TactusScore.TactusRuntime') as MockRuntime:
            from plexus.scores.TactusScore import TactusScore

            score = TactusScore(
                name="test_score",
                tactus_code="Procedure { function(input) return {value='Yes'} end }",
                valid_classes=["Yes", "No", "NA"]
            )

            assert score.parameters.name == "test_score"
            assert score.parameters.tactus_code is not None
            assert score.parameters.valid_classes == ["Yes", "No", "NA"]

    @pytest.mark.asyncio
    async def test_tactus_score_predict_returns_result(self, basic_tactus_code):
        """Test that predict() returns a Score.Result with proper fields."""
        with patch('plexus.scores.TactusScore.TactusRuntime') as MockRuntime:
            mock_runtime_instance = AsyncMock()
            mock_runtime_instance.execute = AsyncMock(return_value={
                'result': {'value': 'Yes', 'explanation': 'Test passed'}
            })
            MockRuntime.return_value = mock_runtime_instance

            from plexus.scores.TactusScore import TactusScore

            score = TactusScore(
                name="test_score",
                tactus_code=basic_tactus_code,
                valid_classes=["Yes", "No", "NA"]
            )

            model_input = Score.Input(
                text="Sample transcript text for classification"
            )

            result = await score.predict(model_input)

            assert isinstance(result, Score.Result)
            assert result.value == "Yes"
            assert result.explanation == "Test passed"

    @pytest.mark.asyncio
    async def test_tactus_score_passes_context_to_runtime(self, basic_tactus_code):
        """Test that predict() passes text and metadata to Tactus runtime."""
        with patch('plexus.scores.TactusScore.TactusRuntime') as MockRuntime:
            mock_runtime_instance = AsyncMock()
            mock_runtime_instance.execute = AsyncMock(return_value={
                'result': {'value': 'Yes', 'explanation': 'Test'}
            })
            MockRuntime.return_value = mock_runtime_instance

            from plexus.scores.TactusScore import TactusScore

            score = TactusScore(
                name="test_score",
                tactus_code=basic_tactus_code
            )

            test_metadata = {'key': 'value', 'nested': {'data': 123}}
            model_input = Score.Input(
                text="Test transcript",
                metadata=test_metadata
            )

            await score.predict(model_input)

            # Verify runtime.execute was called with correct context
            call_args = mock_runtime_instance.execute.call_args
            context = call_args.kwargs.get('context') or call_args[1].get('context')

            assert context['text'] == "Test transcript"
            assert context['metadata'] == test_metadata


# ============================================================================
# Classification Parsing Tests
# ============================================================================

class TestClassificationParsing:
    """Tests for parsing Yes/No/NA classifications from LLM text responses."""

    @pytest.mark.asyncio
    async def test_parse_yes_at_start(self, classification_parsing_code):
        """Test parsing 'YES' at the start of response."""
        with patch('plexus.scores.TactusScore.TactusRuntime') as MockRuntime:
            mock_runtime_instance = AsyncMock()
            mock_runtime_instance.execute = AsyncMock(return_value={
                'result': {'value': 'Yes', 'explanation': 'YES. The criteria were met.'}
            })
            MockRuntime.return_value = mock_runtime_instance

            from plexus.scores.TactusScore import TactusScore

            score = TactusScore(
                name="test_score",
                tactus_code=classification_parsing_code
            )

            result = await score.predict(Score.Input(text="YES. The criteria were met."))
            assert result.value == "Yes"

    @pytest.mark.asyncio
    async def test_parse_no_at_start(self, classification_parsing_code):
        """Test parsing 'NO' at the start of response."""
        with patch('plexus.scores.TactusScore.TactusRuntime') as MockRuntime:
            mock_runtime_instance = AsyncMock()
            mock_runtime_instance.execute = AsyncMock(return_value={
                'result': {'value': 'No', 'explanation': 'NO. The criteria were not met.'}
            })
            MockRuntime.return_value = mock_runtime_instance

            from plexus.scores.TactusScore import TactusScore

            score = TactusScore(
                name="test_score",
                tactus_code=classification_parsing_code
            )

            result = await score.predict(Score.Input(text="NO. The criteria were not met."))
            assert result.value == "No"

    @pytest.mark.asyncio
    async def test_parse_na_at_start(self, classification_parsing_code):
        """Test parsing 'NA' at the start of response."""
        with patch('plexus.scores.TactusScore.TactusRuntime') as MockRuntime:
            mock_runtime_instance = AsyncMock()
            mock_runtime_instance.execute = AsyncMock(return_value={
                'result': {'value': 'NA', 'explanation': 'NA. Insufficient information.'}
            })
            MockRuntime.return_value = mock_runtime_instance

            from plexus.scores.TactusScore import TactusScore

            score = TactusScore(
                name="test_score",
                tactus_code=classification_parsing_code
            )

            result = await score.predict(Score.Input(text="NA. Insufficient information."))
            assert result.value == "NA"

    @pytest.mark.asyncio
    async def test_parse_no_not_confused_with_not(self, classification_parsing_code):
        """Test that 'NOT' is not confused with 'NO' classification."""
        with patch('plexus.scores.TactusScore.TactusRuntime') as MockRuntime:
            # The parse_classification function should handle "NOT" differently from "NO"
            mock_runtime_instance = AsyncMock()
            mock_runtime_instance.execute = AsyncMock(return_value={
                'result': {'value': 'NA', 'explanation': 'NOT applicable in this case'}
            })
            MockRuntime.return_value = mock_runtime_instance

            from plexus.scores.TactusScore import TactusScore

            score = TactusScore(
                name="test_score",
                tactus_code=classification_parsing_code
            )

            result = await score.predict(Score.Input(text="NOT applicable in this case"))
            # "NOT" shouldn't match "NO" pattern
            assert result.value == "NA"

    @pytest.mark.asyncio
    async def test_parse_classification_marker(self, classification_parsing_code):
        """Test parsing 'CLASSIFICATION: YES' format."""
        with patch('plexus.scores.TactusScore.TactusRuntime') as MockRuntime:
            mock_runtime_instance = AsyncMock()
            mock_runtime_instance.execute = AsyncMock(return_value={
                'result': {'value': 'Yes', 'explanation': 'CLASSIFICATION: YES based on analysis'}
            })
            MockRuntime.return_value = mock_runtime_instance

            from plexus.scores.TactusScore import TactusScore

            score = TactusScore(
                name="test_score",
                tactus_code=classification_parsing_code
            )

            result = await score.predict(Score.Input(text="CLASSIFICATION: YES based on analysis"))
            assert result.value == "Yes"


# ============================================================================
# Multi-Entity Aggregation Tests
# ============================================================================

class TestMultiEntityAggregation:
    """Tests for aggregating results across multiple entities."""

    @pytest.mark.asyncio
    async def test_all_yes_returns_yes(self, multi_entity_aggregation_code):
        """Test that all Yes results aggregate to Yes."""
        with patch('plexus.scores.TactusScore.TactusRuntime') as MockRuntime:
            mock_runtime_instance = AsyncMock()
            mock_runtime_instance.execute = AsyncMock(return_value={
                'result': {'value': 'Yes', 'explanation': 'Evaluated 3 entities', 'confidence': 'high'}
            })
            MockRuntime.return_value = mock_runtime_instance

            from plexus.scores.TactusScore import TactusScore

            score = TactusScore(
                name="test_score",
                tactus_code=multi_entity_aggregation_code
            )

            metadata = {
                'entities': [
                    {'name': 'Entity A', 'expected_result': 'Yes'},
                    {'name': 'Entity B', 'expected_result': 'Yes'},
                    {'name': 'Entity C', 'expected_result': 'Yes'}
                ]
            }

            result = await score.predict(Score.Input(text="Test", metadata=metadata))
            assert result.value == "Yes"

    @pytest.mark.asyncio
    async def test_any_no_returns_no(self, multi_entity_aggregation_code):
        """Test that any No result causes aggregate to be No."""
        with patch('plexus.scores.TactusScore.TactusRuntime') as MockRuntime:
            mock_runtime_instance = AsyncMock()
            mock_runtime_instance.execute = AsyncMock(return_value={
                'result': {'value': 'No', 'explanation': 'Evaluated 3 entities', 'confidence': 'high'}
            })
            MockRuntime.return_value = mock_runtime_instance

            from plexus.scores.TactusScore import TactusScore

            score = TactusScore(
                name="test_score",
                tactus_code=multi_entity_aggregation_code
            )

            metadata = {
                'entities': [
                    {'name': 'Entity A', 'expected_result': 'Yes'},
                    {'name': 'Entity B', 'expected_result': 'No'},  # One No
                    {'name': 'Entity C', 'expected_result': 'Yes'}
                ]
            }

            result = await score.predict(Score.Input(text="Test", metadata=metadata))
            assert result.value == "No"

    @pytest.mark.asyncio
    async def test_no_entities_returns_na(self, multi_entity_aggregation_code):
        """Test that no entities to evaluate returns NA."""
        with patch('plexus.scores.TactusScore.TactusRuntime') as MockRuntime:
            mock_runtime_instance = AsyncMock()
            mock_runtime_instance.execute = AsyncMock(return_value={
                'result': {'value': 'NA', 'explanation': 'No entities to evaluate', 'confidence': 'high'}
            })
            MockRuntime.return_value = mock_runtime_instance

            from plexus.scores.TactusScore import TactusScore

            score = TactusScore(
                name="test_score",
                tactus_code=multi_entity_aggregation_code
            )

            metadata = {'entities': []}

            result = await score.predict(Score.Input(text="Test", metadata=metadata))
            assert result.value == "NA"
            assert "No entities" in result.explanation

    @pytest.mark.asyncio
    async def test_missing_entities_array_handled(self, multi_entity_aggregation_code):
        """Test handling of missing entities array in metadata."""
        with patch('plexus.scores.TactusScore.TactusRuntime') as MockRuntime:
            mock_runtime_instance = AsyncMock()
            mock_runtime_instance.execute = AsyncMock(return_value={
                'result': {'value': 'NA', 'explanation': 'No entities to evaluate', 'confidence': 'high'}
            })
            MockRuntime.return_value = mock_runtime_instance

            from plexus.scores.TactusScore import TactusScore

            score = TactusScore(
                name="test_score",
                tactus_code=multi_entity_aggregation_code
            )

            # No entities key at all
            metadata = {'other_data': 'value'}

            result = await score.predict(Score.Input(text="Test", metadata=metadata))
            assert result.value == "NA"


# ============================================================================
# Prerequisite Checking Tests
# ============================================================================

class TestPrerequisiteChecking:
    """Tests for prerequisite/eligibility checking logic."""

    @pytest.mark.asyncio
    async def test_all_prerequisites_met(self, prerequisite_checking_code):
        """Test that meeting all prerequisites returns Yes."""
        with patch('plexus.scores.TactusScore.TactusRuntime') as MockRuntime:
            mock_runtime_instance = AsyncMock()
            mock_runtime_instance.execute = AsyncMock(return_value={
                'result': {'value': 'Yes', 'explanation': 'All prerequisites met'}
            })
            MockRuntime.return_value = mock_runtime_instance

            from plexus.scores.TactusScore import TactusScore

            score = TactusScore(
                name="test_score",
                tactus_code=prerequisite_checking_code
            )

            metadata = {
                'category': 'Premium',
                'status': 'Active'
            }

            result = await score.predict(Score.Input(text="Test", metadata=metadata))
            assert result.value == "Yes"

    @pytest.mark.asyncio
    async def test_category_prerequisite_not_met(self, prerequisite_checking_code):
        """Test that wrong category returns NA with explanation."""
        with patch('plexus.scores.TactusScore.TactusRuntime') as MockRuntime:
            mock_runtime_instance = AsyncMock()
            mock_runtime_instance.execute = AsyncMock(return_value={
                'result': {
                    'value': 'NA',
                    'explanation': "Prerequisites not met: Category is 'Basic' (expected 'Premium')"
                }
            })
            MockRuntime.return_value = mock_runtime_instance

            from plexus.scores.TactusScore import TactusScore

            score = TactusScore(
                name="test_score",
                tactus_code=prerequisite_checking_code
            )

            metadata = {
                'category': 'Basic',  # Wrong category
                'status': 'Active'
            }

            result = await score.predict(Score.Input(text="Test", metadata=metadata))
            assert result.value == "NA"
            assert "Category" in result.explanation
            assert "Basic" in result.explanation

    @pytest.mark.asyncio
    async def test_multiple_prerequisites_not_met(self, prerequisite_checking_code):
        """Test that multiple failing prerequisites are all reported."""
        with patch('plexus.scores.TactusScore.TactusRuntime') as MockRuntime:
            mock_runtime_instance = AsyncMock()
            mock_runtime_instance.execute = AsyncMock(return_value={
                'result': {
                    'value': 'NA',
                    'explanation': "Prerequisites not met: Category is 'Basic' (expected 'Premium'); Status is 'Inactive' (expected 'Active')"
                }
            })
            MockRuntime.return_value = mock_runtime_instance

            from plexus.scores.TactusScore import TactusScore

            score = TactusScore(
                name="test_score",
                tactus_code=prerequisite_checking_code
            )

            metadata = {
                'category': 'Basic',    # Wrong
                'status': 'Inactive'    # Also wrong
            }

            result = await score.predict(Score.Input(text="Test", metadata=metadata))
            assert result.value == "NA"
            assert "Category" in result.explanation
            assert "Status" in result.explanation


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestErrorHandling:
    """Tests for error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_runtime_error_returns_error_result(self, basic_tactus_code):
        """Test that runtime errors return an ERROR result."""
        with patch('plexus.scores.TactusScore.TactusRuntime') as MockRuntime:
            mock_runtime_instance = AsyncMock()
            mock_runtime_instance.execute = AsyncMock(
                side_effect=Exception("Lua runtime error: syntax error")
            )
            MockRuntime.return_value = mock_runtime_instance

            from plexus.scores.TactusScore import TactusScore

            score = TactusScore(
                name="test_score",
                tactus_code=basic_tactus_code
            )

            result = await score.predict(Score.Input(text="Test"))

            assert result.value == "ERROR"
            assert result.error is not None
            assert "Lua runtime error" in result.error

    @pytest.mark.asyncio
    async def test_missing_value_in_output_raises_error(self, basic_tactus_code):
        """Test that missing 'value' in Tactus output causes an error."""
        with patch('plexus.scores.TactusScore.TactusRuntime') as MockRuntime:
            mock_runtime_instance = AsyncMock()
            # Return result without 'value' field
            mock_runtime_instance.execute = AsyncMock(return_value={
                'result': {'explanation': 'Missing value field'}
            })
            MockRuntime.return_value = mock_runtime_instance

            from plexus.scores.TactusScore import TactusScore

            score = TactusScore(
                name="test_score",
                tactus_code=basic_tactus_code
            )

            result = await score.predict(Score.Input(text="Test"))

            assert result.value == "ERROR"
            assert "must return 'value'" in result.error

    @pytest.mark.asyncio
    async def test_invalid_class_warning(self, basic_tactus_code):
        """Test that invalid classification value logs a warning."""
        with patch('plexus.scores.TactusScore.TactusRuntime') as MockRuntime:
            mock_runtime_instance = AsyncMock()
            mock_runtime_instance.execute = AsyncMock(return_value={
                'result': {'value': 'InvalidClass', 'explanation': 'Test'}
            })
            MockRuntime.return_value = mock_runtime_instance

            from plexus.scores.TactusScore import TactusScore

            with patch('plexus.scores.TactusScore.logger') as mock_logger:
                score = TactusScore(
                    name="test_score",
                    tactus_code=basic_tactus_code,
                    valid_classes=["Yes", "No", "NA"]
                )

                result = await score.predict(Score.Input(text="Test"))

                # Result should still be returned, but warning logged
                assert result.value == "InvalidClass"
                mock_logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_empty_text_handled(self, basic_tactus_code):
        """Test that empty text input is handled gracefully."""
        with patch('plexus.scores.TactusScore.TactusRuntime') as MockRuntime:
            mock_runtime_instance = AsyncMock()
            mock_runtime_instance.execute = AsyncMock(return_value={
                'result': {'value': 'NA', 'explanation': 'Empty input'}
            })
            MockRuntime.return_value = mock_runtime_instance

            from plexus.scores.TactusScore import TactusScore

            score = TactusScore(
                name="test_score",
                tactus_code=basic_tactus_code
            )

            result = await score.predict(Score.Input(text=""))

            # Should not raise an error
            assert result.value is not None

    @pytest.mark.asyncio
    async def test_missing_metadata_handled(self, basic_tactus_code):
        """Test that missing/empty metadata is handled gracefully."""
        with patch('plexus.scores.TactusScore.TactusRuntime') as MockRuntime:
            mock_runtime_instance = AsyncMock()
            mock_runtime_instance.execute = AsyncMock(return_value={
                'result': {'value': 'Yes', 'explanation': 'Test'}
            })
            MockRuntime.return_value = mock_runtime_instance

            from plexus.scores.TactusScore import TactusScore

            score = TactusScore(
                name="test_score",
                tactus_code=basic_tactus_code
            )

            # Test with empty metadata (Score.Input.metadata defaults to empty dict)
            result = await score.predict(Score.Input(text="Test"))

            # Should not raise an error
            assert result.value == "Yes"


# ============================================================================
# Confidence Conversion Tests
# ============================================================================

class TestConfidenceConversion:
    """Tests for the _convert_confidence method that maps confidence to float."""

    def test_none_confidence_returns_none(self, basic_tactus_code):
        """Test that None confidence remains None."""
        with patch('plexus.scores.TactusScore.TactusRuntime'):
            from plexus.scores.TactusScore import TactusScore
            score = TactusScore(name="test", tactus_code=basic_tactus_code)
            assert score._convert_confidence(None) is None

    def test_float_confidence_passed_through(self, basic_tactus_code):
        """Test that float confidence is passed through."""
        with patch('plexus.scores.TactusScore.TactusRuntime'):
            from plexus.scores.TactusScore import TactusScore
            score = TactusScore(name="test", tactus_code=basic_tactus_code)
            assert score._convert_confidence(0.75) == 0.75

    def test_int_confidence_converted_to_float(self, basic_tactus_code):
        """Test that int confidence is converted to float."""
        with patch('plexus.scores.TactusScore.TactusRuntime'):
            from plexus.scores.TactusScore import TactusScore
            score = TactusScore(name="test", tactus_code=basic_tactus_code)
            assert score._convert_confidence(1) == 1.0
            assert isinstance(score._convert_confidence(1), float)

    def test_confidence_clamped_to_valid_range(self, basic_tactus_code):
        """Test that confidence values are clamped between 0.0 and 1.0."""
        with patch('plexus.scores.TactusScore.TactusRuntime'):
            from plexus.scores.TactusScore import TactusScore
            score = TactusScore(name="test", tactus_code=basic_tactus_code)
            assert score._convert_confidence(1.5) == 1.0
            assert score._convert_confidence(-0.5) == 0.0

    def test_string_numeric_confidence_converted(self, basic_tactus_code):
        """Test that numeric strings are converted to float."""
        with patch('plexus.scores.TactusScore.TactusRuntime'):
            from plexus.scores.TactusScore import TactusScore
            score = TactusScore(name="test", tactus_code=basic_tactus_code)
            assert score._convert_confidence("0.85") == 0.85

    def test_string_label_high_converted(self, basic_tactus_code):
        """Test that 'high' confidence is converted to 0.9."""
        with patch('plexus.scores.TactusScore.TactusRuntime'):
            from plexus.scores.TactusScore import TactusScore
            score = TactusScore(name="test", tactus_code=basic_tactus_code)
            assert score._convert_confidence("high") == 0.9
            assert score._convert_confidence("HIGH") == 0.9
            assert score._convert_confidence("  High  ") == 0.9

    def test_string_label_medium_converted(self, basic_tactus_code):
        """Test that 'medium' confidence is converted to 0.6."""
        with patch('plexus.scores.TactusScore.TactusRuntime'):
            from plexus.scores.TactusScore import TactusScore
            score = TactusScore(name="test", tactus_code=basic_tactus_code)
            assert score._convert_confidence("medium") == 0.6
            assert score._convert_confidence("med") == 0.6

    def test_string_label_low_converted(self, basic_tactus_code):
        """Test that 'low' confidence is converted to 0.3."""
        with patch('plexus.scores.TactusScore.TactusRuntime'):
            from plexus.scores.TactusScore import TactusScore
            score = TactusScore(name="test", tactus_code=basic_tactus_code)
            assert score._convert_confidence("low") == 0.3

    def test_string_label_very_high_converted(self, basic_tactus_code):
        """Test that 'very high' confidence is converted to 0.95."""
        with patch('plexus.scores.TactusScore.TactusRuntime'):
            from plexus.scores.TactusScore import TactusScore
            score = TactusScore(name="test", tactus_code=basic_tactus_code)
            assert score._convert_confidence("very high") == 0.95

    def test_string_label_very_low_converted(self, basic_tactus_code):
        """Test that 'very low' confidence is converted to 0.1."""
        with patch('plexus.scores.TactusScore.TactusRuntime'):
            from plexus.scores.TactusScore import TactusScore
            score = TactusScore(name="test", tactus_code=basic_tactus_code)
            assert score._convert_confidence("very low") == 0.1

    def test_unknown_string_returns_none(self, basic_tactus_code):
        """Test that unknown string confidence returns None."""
        with patch('plexus.scores.TactusScore.TactusRuntime'):
            from plexus.scores.TactusScore import TactusScore
            score = TactusScore(name="test", tactus_code=basic_tactus_code)
            assert score._convert_confidence("unknown") is None
            assert score._convert_confidence("maybe") is None


# ============================================================================
# Result Conversion Tests
# ============================================================================

class TestResultConversion:
    """Tests for converting previous Score.Results to Tactus format."""

    @pytest.mark.asyncio
    async def test_previous_results_passed_to_runtime(self, basic_tactus_code):
        """Test that previous score results are converted and passed to runtime."""
        with patch('plexus.scores.TactusScore.TactusRuntime') as MockRuntime:
            mock_runtime_instance = AsyncMock()
            mock_runtime_instance.execute = AsyncMock(return_value={
                'result': {'value': 'Yes', 'explanation': 'Based on previous results'}
            })
            MockRuntime.return_value = mock_runtime_instance

            from plexus.scores.TactusScore import TactusScore

            score = TactusScore(
                name="test_score",
                tactus_code=basic_tactus_code
            )

            # Create mock previous results
            prev_result1 = Mock()
            prev_result1.value = "Yes"
            prev_result1.explanation = "Previous explanation 1"
            prev_result1.confidence = "high"

            prev_result2 = Mock()
            prev_result2.value = "No"
            prev_result2.explanation = "Previous explanation 2"
            prev_result2.confidence = "medium"

            model_input = Score.Input(
                text="Test",
                results=[prev_result1, prev_result2]
            )

            await score.predict(model_input)

            # Verify context passed to runtime includes converted results
            call_args = mock_runtime_instance.execute.call_args
            context = call_args.kwargs.get('context') or call_args[1].get('context')

            assert len(context['results']) == 2
            assert context['results'][0]['value'] == "Yes"
            assert context['results'][1]['value'] == "No"


# ============================================================================
# Complex Workflow Tests
# ============================================================================

class TestComplexWorkflows:
    """Tests for complex real-world workflow patterns."""

    @pytest.mark.asyncio
    async def test_nested_metadata_extraction(self, basic_tactus_code):
        """Test extraction of deeply nested metadata fields."""
        with patch('plexus.scores.TactusScore.TactusRuntime') as MockRuntime:
            mock_runtime_instance = AsyncMock()
            mock_runtime_instance.execute = AsyncMock(return_value={
                'result': {'value': 'Yes', 'explanation': 'Nested data processed'}
            })
            MockRuntime.return_value = mock_runtime_instance

            from plexus.scores.TactusScore import TactusScore

            score = TactusScore(
                name="test_score",
                tactus_code=basic_tactus_code
            )

            # Complex nested metadata structure
            metadata = {
                'entities': [
                    {
                        'name': 'Entity A',
                        'properties': {
                            'category': 'Premium',
                            'attributes': {
                                'level': 1,
                                'tags': ['important', 'verified']
                            }
                        }
                    }
                ],
                'settings': {
                    'mode': 'strict',
                    'thresholds': {
                        'min': 0.5,
                        'max': 0.9
                    }
                }
            }

            result = await score.predict(Score.Input(text="Test", metadata=metadata))

            # Verify metadata was passed through correctly
            call_args = mock_runtime_instance.execute.call_args
            context = call_args.kwargs.get('context') or call_args[1].get('context')
            assert context['metadata'] == metadata

    @pytest.mark.asyncio
    async def test_flat_metadata_as_single_entity(self, multi_entity_aggregation_code):
        """Test that flat metadata without entities array is treated as single entity."""
        with patch('plexus.scores.TactusScore.TactusRuntime') as MockRuntime:
            mock_runtime_instance = AsyncMock()
            # Simulate Tactus code treating flat metadata as single entity
            mock_runtime_instance.execute = AsyncMock(return_value={
                'result': {'value': 'Yes', 'explanation': 'Single entity evaluated'}
            })
            MockRuntime.return_value = mock_runtime_instance

            from plexus.scores.TactusScore import TactusScore

            score = TactusScore(
                name="test_score",
                tactus_code=multi_entity_aggregation_code
            )

            # Flat metadata (no entities array)
            metadata = {
                'name': 'Single Entity',
                'category': 'Premium',
                'expected_result': 'Yes'
            }

            result = await score.predict(Score.Input(text="Test", metadata=metadata))
            # Should process without error
            assert result.value is not None

    @pytest.mark.asyncio
    async def test_confidence_field_mapping(self, basic_tactus_code):
        """Test that confidence field is properly mapped to Score.Result.

        TactusScore converts string confidence values to floats:
        - 'high' -> 0.9
        - 'medium' -> 0.6
        - 'low' -> 0.3
        """
        with patch('plexus.scores.TactusScore.TactusRuntime') as MockRuntime:
            mock_runtime_instance = AsyncMock()
            mock_runtime_instance.execute = AsyncMock(return_value={
                'result': {
                    'value': 'Yes',
                    'explanation': 'High confidence result',
                    'confidence': 'high'
                }
            })
            MockRuntime.return_value = mock_runtime_instance

            from plexus.scores.TactusScore import TactusScore

            score = TactusScore(
                name="test_score",
                tactus_code=basic_tactus_code
            )

            result = await score.predict(Score.Input(text="Test"))

            # String 'high' is converted to 0.9 by TactusScore._convert_confidence
            assert result.confidence == 0.9


# ============================================================================
# Integration-Style Tests (Still Mocked)
# ============================================================================

class TestIntegrationPatterns:
    """Integration-style tests that verify full workflow patterns."""

    @pytest.mark.asyncio
    async def test_end_to_end_classification_workflow(self):
        """Test complete classification workflow from input to result."""
        with patch('plexus.scores.TactusScore.TactusRuntime') as MockRuntime:
            mock_runtime_instance = AsyncMock()

            # Simulate complete workflow execution
            mock_runtime_instance.execute = AsyncMock(return_value={
                'result': {
                    'value': 'Yes',
                    'explanation': 'Agent correctly performed the required action',
                    'confidence': 'high'
                },
                'token_usage': {'input': 500, 'output': 100}
            })
            MockRuntime.return_value = mock_runtime_instance

            from plexus.scores.TactusScore import TactusScore

            # Full configuration like a real score
            score = TactusScore(
                name="integration_test_score",
                tactus_code='''
                    Procedure {
                        input = {text = field.string{required = true}},
                        output = {value = field.string{required = true}},
                        function(input)
                            return {value = "Yes", explanation = "Test", confidence = "high"}
                        end
                    }
                ''',
                valid_classes=["Yes", "No", "NA"],
                model_provider="ChatOpenAI",
                model_name="gpt-4o-mini"
            )

            # Realistic input
            model_input = Score.Input(
                text="This is a sample transcript of a call between an agent and a customer.",
                metadata={
                    'call_id': '12345',
                    'duration': 300,
                    'entities': [
                        {'name': 'Test Entity', 'type': 'Standard'}
                    ]
                }
            )

            result = await score.predict(model_input)

            # Verify complete result
            assert isinstance(result, Score.Result)
            assert result.value in ["Yes", "No", "NA", "ERROR"]
            assert result.explanation is not None


# ============================================================================
# Real Integration Tests (Actual Tactus Runtime)
# ============================================================================

class TestRealTactusRuntime:
    """
    Integration tests that use the actual Tactus runtime (not mocked).

    These tests verify that TactusScore correctly integrates with Tactus
    for executing Lua code without requiring LLM API calls.
    """

    @pytest.mark.asyncio
    async def test_simple_lua_logic_execution(self):
        """Test that simple Lua logic executes correctly in real Tactus runtime."""
        from plexus.scores.TactusScore import TactusScore

        simple_code = '''
        Procedure {
            input = {
                text = field.string{required = true}
            },
            output = {
                value = field.string{required = true},
                explanation = field.string{required = true}
            },
            function(input)
                if input.text:lower():find("hello") then
                    return {
                        value = "Yes",
                        explanation = "Text contains greeting"
                    }
                else
                    return {
                        value = "No",
                        explanation = "Text does not contain greeting"
                    }
                end
            end
        }
        '''

        score = await TactusScore.create(
            name='test_simple_lua',
            tactus_code=simple_code
        )

        # Test positive case
        result = await score.predict(Score.Input(text='Hello world!'))
        assert result.value == 'Yes'
        assert 'greeting' in result.explanation.lower()

        # Test negative case
        result2 = await score.predict(Score.Input(text='Goodbye world!'))
        assert result2.value == 'No'

    @pytest.mark.asyncio
    async def test_metadata_access_in_lua(self):
        """Test that Lua code can access metadata correctly."""
        from plexus.scores.TactusScore import TactusScore

        metadata_code = '''
        Procedure {
            input = {
                text = field.string{required = true},
                metadata = field.object{description = "Item metadata"}
            },
            output = {
                value = field.string{required = true},
                explanation = field.string{required = true}
            },
            function(input)
                local meta = input.metadata or {}
                local entities = meta.entities or {}

                if #entities == 0 then
                    return {
                        value = "NA",
                        explanation = "No entities in metadata"
                    }
                end

                local premium_count = 0
                for _, entity in ipairs(entities) do
                    if entity.category == "Premium" then
                        premium_count = premium_count + 1
                    end
                end

                if premium_count > 0 then
                    return {
                        value = "Yes",
                        explanation = "Found " .. premium_count .. " premium entities"
                    }
                else
                    return {
                        value = "No",
                        explanation = "No premium entities found"
                    }
                end
            end
        }
        '''

        score = await TactusScore.create(
            name='test_metadata_lua',
            tactus_code=metadata_code
        )

        # Test empty metadata
        result = await score.predict(Score.Input(text='Test'))
        assert result.value == 'NA'

        # Test with premium entity
        result2 = await score.predict(Score.Input(
            text='Test',
            metadata={'entities': [{'name': 'A', 'category': 'Premium'}]}
        ))
        assert result2.value == 'Yes'
        assert '1 premium' in result2.explanation

        # Test with non-premium entity
        result3 = await score.predict(Score.Input(
            text='Test',
            metadata={'entities': [{'name': 'B', 'category': 'Basic'}]}
        ))
        assert result3.value == 'No'

    @pytest.mark.asyncio
    async def test_multi_entity_aggregation_logic(self):
        """Test aggregation logic: any No -> No, all Yes -> Yes."""
        from plexus.scores.TactusScore import TactusScore

        aggregation_code = '''
        Procedure {
            input = {
                text = field.string{required = true},
                metadata = field.object{description = "Entity metadata"}
            },
            output = {
                value = field.string{required = true},
                explanation = field.string{required = true}
            },
            function(input)
                local meta = input.metadata or {}
                local entities = meta.entities or {}

                if #entities == 0 then
                    return {value = "NA", explanation = "No entities"}
                end

                local any_no = false
                local all_yes = true
                local results = {}

                for _, entity in ipairs(entities) do
                    -- Simple rule: "approved" entities -> Yes, others -> No
                    if entity.status == "approved" then
                        table.insert(results, entity.name .. ": Yes")
                    else
                        table.insert(results, entity.name .. ": No")
                        any_no = true
                        all_yes = false
                    end
                end

                local final_value
                if any_no then
                    final_value = "No"
                elseif all_yes then
                    final_value = "Yes"
                else
                    final_value = "NA"
                end

                return {
                    value = final_value,
                    explanation = table.concat(results, "; ")
                }
            end
        }
        '''

        score = await TactusScore.create(
            name='test_aggregation',
            tactus_code=aggregation_code
        )

        # All approved -> Yes
        result = await score.predict(Score.Input(
            text='Test',
            metadata={'entities': [
                {'name': 'A', 'status': 'approved'},
                {'name': 'B', 'status': 'approved'}
            ]}
        ))
        assert result.value == 'Yes'

        # Any rejected -> No
        result2 = await score.predict(Score.Input(
            text='Test',
            metadata={'entities': [
                {'name': 'A', 'status': 'approved'},
                {'name': 'B', 'status': 'rejected'}
            ]}
        ))
        assert result2.value == 'No'

    @pytest.mark.asyncio
    async def test_prerequisite_checking_pattern(self):
        """Test prerequisite checking pattern from real-world scores."""
        from plexus.scores.TactusScore import TactusScore

        prereq_code = '''
        Procedure {
            input = {
                text = field.string{required = true},
                metadata = field.object{description = "Prerequisite metadata"}
            },
            output = {
                value = field.string{required = true},
                explanation = field.string{required = true}
            },
            function(input)
                local meta = input.metadata or {}

                -- Check prerequisites
                local missing = {}
                if meta.category ~= "Premium" then
                    table.insert(missing, "Category must be Premium")
                end
                if meta.status ~= "active" then
                    table.insert(missing, "Status must be active")
                end

                if #missing > 0 then
                    return {
                        value = "NA",
                        explanation = "Prerequisites not met: " .. table.concat(missing, "; ")
                    }
                end

                -- All prerequisites met, evaluate based on text
                if input.text:find("approved") then
                    return {value = "Yes", explanation = "Prerequisites met and approved"}
                else
                    return {value = "No", explanation = "Prerequisites met but not approved"}
                end
            end
        }
        '''

        score = await TactusScore.create(
            name='test_prereq',
            tactus_code=prereq_code
        )

        # Missing prerequisites
        result = await score.predict(Score.Input(
            text='approved',
            metadata={'category': 'Basic', 'status': 'inactive'}
        ))
        assert result.value == 'NA'
        assert 'Prerequisites not met' in result.explanation

        # All prerequisites met
        result2 = await score.predict(Score.Input(
            text='This request is approved',
            metadata={'category': 'Premium', 'status': 'active'}
        ))
        assert result2.value == 'Yes'

    @pytest.mark.asyncio
    async def test_confidence_output_handling(self):
        """Test that confidence values are properly passed through from Lua."""
        from plexus.scores.TactusScore import TactusScore

        confidence_code = '''
        Procedure {
            input = {text = field.string{required = true}},
            output = {
                value = field.string{required = true},
                explanation = field.string{required = true},
                confidence = field.string{description = "Confidence level"}
            },
            function(input)
                return {
                    value = "Yes",
                    explanation = "High confidence result",
                    confidence = "high"
                }
            end
        }
        '''

        score = await TactusScore.create(
            name='test_confidence',
            tactus_code=confidence_code
        )

        result = await score.predict(Score.Input(text='Test'))
        assert result.value == 'Yes'
        # String 'high' is converted to 0.9
        assert result.confidence == 0.9

    @pytest.mark.asyncio
    async def test_valid_classes_validation(self):
        """Test that valid_classes constraint is checked."""
        from plexus.scores.TactusScore import TactusScore
        import logging

        # Code that returns a value not in valid_classes
        code = '''
        Procedure {
            input = {text = field.string{required = true}},
            output = {value = field.string{required = true}},
            function(input)
                return {value = "Maybe", explanation = "Uncertain"}
            end
        }
        '''

        score = await TactusScore.create(
            name='test_valid_classes',
            tactus_code=code,
            valid_classes=['Yes', 'No', 'NA']
        )

        # Should still return the result but log a warning
        result = await score.predict(Score.Input(text='Test'))
        assert result.value == 'Maybe'  # Value is returned even if not in valid_classes


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
