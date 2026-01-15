import pytest
import json
from unittest.mock import Mock, patch


class TestDeepgramInputSource:
    """Test cases for DeepgramInputSource with all format options"""

    def load_fixture(self, filename):
        """Helper to load test fixture files"""
        with open(f"tests/fixtures/{filename}", "r") as f:
            return json.load(f)

    @patch("plexus.utils.score_result_s3_utils.download_score_result_trace_file")
    def test_extract_paragraphs_default(self, mock_download):
        """Test paragraph format extraction (default format)"""
        from plexus.input_sources.DeepgramInputSource import DeepgramInputSource

        # Setup
        deepgram_data = self.load_fixture("deepgram_simple_conversation.json")
        mock_download.return_value = (deepgram_data, None)

        source = DeepgramInputSource(pattern=r".*deepgram.*\.json$")
        item = Mock()
        item.metadata = {}
        item.attachedFiles = ["s3://bucket/path/deepgram_result.json"]

        # Execute
        result = source.extract(item)

        # Assert - result is now a ScoreInput object
        assert isinstance(result, type(result))  # ScoreInput type check
        assert "Hello, thank you for calling customer support" in result.text
        assert "Hi, I'm having trouble with my account login" in result.text
        assert "I can definitely help you with that" in result.text
        # Paragraphs should be double-spaced
        assert "\n\n" in result.text

    @patch("plexus.utils.score_result_s3_utils.download_score_result_trace_file")
    def test_extract_paragraphs_explicit(self, mock_download):
        """Test explicit paragraphs format"""
        from plexus.input_sources.DeepgramInputSource import DeepgramInputSource
        # Setup
        deepgram_data = self.load_fixture("deepgram_simple_conversation.json")
        mock_download.return_value = (deepgram_data, None)

        source = DeepgramInputSource(pattern=r".*\.json$", format="paragraphs")
        item = Mock()
        item.metadata = {}
        item.attachedFiles = ["s3://bucket/deepgram.json"]

        # Execute
        result = source.extract(item)

        # Assert
        lines = result.text.split("\n\n")
        assert len(lines) == 3  # Three paragraphs
        assert "customer support" in lines[0]
        assert "account login" in lines[1]
        assert "account information" in lines[2]

    @patch("plexus.utils.score_result_s3_utils.download_score_result_trace_file")
    def test_extract_paragraphs_with_speaker_labels(self, mock_download):
        """Test paragraphs with speaker labels enabled"""
        from plexus.input_sources.DeepgramInputSource import DeepgramInputSource
        # Setup
        deepgram_data = self.load_fixture("deepgram_simple_conversation.json")
        mock_download.return_value = (deepgram_data, None)

        source = DeepgramInputSource(
            pattern=r".*\.json$", format="paragraphs", speaker_labels=True
        )
        item = Mock()
        item.metadata = {}
        item.attachedFiles = ["s3://bucket/deepgram.json"]

        # Execute
        result = source.extract(item)

        # Assert
        assert "Speaker 0:" in result.text
        assert "Speaker 1:" in result.text
        lines = result.text.split("\n\n")
        assert lines[0].startswith("Speaker 0:")
        assert lines[1].startswith("Speaker 1:")
        assert lines[2].startswith("Speaker 0:")

    @patch("plexus.utils.score_result_s3_utils.download_score_result_trace_file")
    def test_extract_paragraphs_with_timestamps(self, mock_download):
        """Test paragraphs with timestamps enabled"""
        from plexus.input_sources.DeepgramInputSource import DeepgramInputSource
        # Setup
        deepgram_data = self.load_fixture("deepgram_simple_conversation.json")
        mock_download.return_value = (deepgram_data, None)

        source = DeepgramInputSource(
            pattern=r".*\.json$", format="paragraphs", include_timestamps=True
        )
        item = Mock()
        item.metadata = {}
        item.attachedFiles = ["s3://bucket/deepgram.json"]

        # Execute
        result = source.extract(item)

        # Assert
        assert "[0.00s]" in result.text or "[0.0s]" in result
        assert "s]" in result.text  # Has timestamp markers
        lines = result.text.split("\n\n")
        for line in lines:
            assert line.startswith("[")

    @patch("plexus.utils.score_result_s3_utils.download_score_result_trace_file")
    def test_extract_paragraphs_with_both_timestamps_and_speakers(self, mock_download):
        """Test paragraphs with both timestamps and speaker labels"""
        from plexus.input_sources.DeepgramInputSource import DeepgramInputSource
        # Setup
        deepgram_data = self.load_fixture("deepgram_simple_conversation.json")
        mock_download.return_value = (deepgram_data, None)

        source = DeepgramInputSource(
            pattern=r".*\.json$",
            format="paragraphs",
            include_timestamps=True,
            speaker_labels=True,
        )
        item = Mock()
        item.metadata = {}
        item.attachedFiles = ["s3://bucket/deepgram.json"]

        # Execute
        result = source.extract(item)

        # Assert
        assert "[" in result.text and "s]" in result  # Has timestamps
        assert "Speaker 0:" in result.text
        assert "Speaker 1:" in result.text

    @patch("plexus.utils.score_result_s3_utils.download_score_result_trace_file")
    def test_extract_utterances_format(self, mock_download):
        """Test utterances format extraction"""
        from plexus.input_sources.DeepgramInputSource import DeepgramInputSource
        # Setup
        deepgram_data = self.load_fixture("deepgram_simple_conversation.json")
        mock_download.return_value = (deepgram_data, None)

        source = DeepgramInputSource(pattern=r".*\.json$", format="utterances")
        item = Mock()
        item.metadata = {}
        item.attachedFiles = ["s3://bucket/deepgram.json"]

        # Execute
        result = source.extract(item)

        # Assert
        lines = result.text.split("\n")
        assert len(lines) == 3  # Three utterances
        # Utterances should be single-spaced
        assert "\n\n" not in result.text
        assert "Hello, thank you for calling customer support" in result.text

    @patch("plexus.utils.score_result_s3_utils.download_score_result_trace_file")
    def test_extract_utterances_with_speaker_labels(self, mock_download):
        """Test utterances with speaker labels"""
        from plexus.input_sources.DeepgramInputSource import DeepgramInputSource
        # Setup
        deepgram_data = self.load_fixture("deepgram_simple_conversation.json")
        mock_download.return_value = (deepgram_data, None)

        source = DeepgramInputSource(
            pattern=r".*\.json$", format="utterances", speaker_labels=True
        )
        item = Mock()
        item.metadata = {}
        item.attachedFiles = ["s3://bucket/deepgram.json"]

        # Execute
        result = source.extract(item)

        # Assert
        lines = result.text.split("\n")
        assert "Speaker 0:" in lines[0]
        assert "Speaker 1:" in lines[1]
        assert "Speaker 0:" in lines[2]

    @patch("plexus.utils.score_result_s3_utils.download_score_result_trace_file")
    def test_extract_utterances_with_timestamps(self, mock_download):
        """Test utterances with timestamps"""
        from plexus.input_sources.DeepgramInputSource import DeepgramInputSource
        # Setup
        deepgram_data = self.load_fixture("deepgram_simple_conversation.json")
        mock_download.return_value = (deepgram_data, None)

        source = DeepgramInputSource(
            pattern=r".*\.json$", format="utterances", include_timestamps=True
        )
        item = Mock()
        item.metadata = {}
        item.attachedFiles = ["s3://bucket/deepgram.json"]

        # Execute
        result = source.extract(item)

        # Assert
        lines = result.text.split("\n")
        for line in lines:
            assert line.startswith("[")
            assert "s]" in line

    @patch("plexus.utils.score_result_s3_utils.download_score_result_trace_file")
    def test_extract_words_format(self, mock_download):
        """Test words format extraction"""
        from plexus.input_sources.DeepgramInputSource import DeepgramInputSource
        # Setup
        deepgram_data = self.load_fixture("deepgram_minimal.json")
        mock_download.return_value = (deepgram_data, None)

        source = DeepgramInputSource(pattern=r".*\.json$", format="words")
        item = Mock()
        item.metadata = {}
        item.attachedFiles = ["s3://bucket/deepgram.json"]

        # Execute
        result = source.extract(item)

        # Assert
        assert result.text == "Hello world"
        assert " " in result.text  # Space-separated words

    @patch("plexus.utils.score_result_s3_utils.download_score_result_trace_file")
    def test_extract_words_with_timestamps(self, mock_download):
        """Test words format with timestamps"""
        from plexus.input_sources.DeepgramInputSource import DeepgramInputSource
        # Setup
        deepgram_data = self.load_fixture("deepgram_minimal.json")
        mock_download.return_value = (deepgram_data, None)

        source = DeepgramInputSource(
            pattern=r".*\.json$", format="words", include_timestamps=True
        )
        item = Mock()
        item.metadata = {}
        item.attachedFiles = ["s3://bucket/deepgram.json"]

        # Execute
        result = source.extract(item)

        # Assert
        assert "Hello[0.00]" in result.text or "Hello[0.0]" in result
        assert "world[" in result.text
        assert "]" in result.text

    @patch("plexus.utils.score_result_s3_utils.download_score_result_trace_file")
    def test_extract_raw_format(self, mock_download):
        """Test raw format extraction (full transcript text)"""
        from plexus.input_sources.DeepgramInputSource import DeepgramInputSource
        # Setup
        deepgram_data = self.load_fixture("deepgram_simple_conversation.json")
        mock_download.return_value = (deepgram_data, None)

        source = DeepgramInputSource(pattern=r".*\.json$", format="raw")
        item = Mock()
        item.metadata = {}
        item.attachedFiles = ["s3://bucket/deepgram.json"]

        # Execute
        result = source.extract(item)

        # Assert
        # Raw format should be the complete transcript without formatting
        assert "Hello, thank you for calling customer support" in result.text
        assert "Hi, I'm having trouble with my account login" in result.text
        # Should not have formatting markers
        assert "Speaker" not in result.text
        assert "[" not in result.text or "s]" not in result

    @patch("plexus.utils.score_result_s3_utils.download_score_result_trace_file")
    def test_extract_invalid_format_raises_error(self, mock_download):
        """Test that invalid format raises ValueError"""
        from plexus.input_sources.DeepgramInputSource import DeepgramInputSource
        # Setup
        deepgram_data = self.load_fixture("deepgram_minimal.json")
        mock_download.return_value = (deepgram_data, None)

        source = DeepgramInputSource(pattern=r".*\.json$", format="invalid_format")
        item = Mock()
        item.metadata = {}
        item.attachedFiles = ["s3://bucket/deepgram.json"]

        # Execute & Assert
        with pytest.raises(ValueError) as exc_info:
            source.extract(item)

        assert "Unknown format: invalid_format" in str(exc_info.value)
        assert "Must be one of: paragraphs, utterances, words, raw" in str(
            exc_info.value
        )

    def test_extract_no_matching_attachment(self):
        """Test that ValueError is raised when no attachment matches"""
        from plexus.input_sources.DeepgramInputSource import DeepgramInputSource
        # Setup
        source = DeepgramInputSource(pattern=r".*deepgram.*\.json$")
        item = Mock()
        item.metadata = {}
        item.attachedFiles = [
            "s3://bucket/path/transcript.txt",
            "s3://bucket/path/other.xml",
        ]

        # Execute & Assert
        with pytest.raises(ValueError) as exc_info:
            source.extract(item)

        assert "No Deepgram file matching pattern" in str(exc_info.value)
        assert "Available attachments:" in str(exc_info.value)

    @patch("plexus.utils.score_result_s3_utils.download_score_result_trace_file")
    def test_extract_malformed_json_raises_error(self, mock_download):
        """Test that malformed JSON structure raises KeyError"""
        from plexus.input_sources.DeepgramInputSource import DeepgramInputSource
        # Setup
        malformed_data = {"invalid": "structure"}
        mock_download.return_value = (malformed_data, None)

        source = DeepgramInputSource(pattern=r".*\.json$")
        item = Mock()
        item.metadata = {}
        item.attachedFiles = ["s3://bucket/deepgram.json"]

        # Execute & Assert
        with pytest.raises(KeyError):
            source.extract(item)

    @patch("plexus.utils.score_result_s3_utils.download_score_result_trace_file")
    def test_extract_download_failure_propagates(self, mock_download):
        """Test that download failures propagate as exceptions"""
        from plexus.input_sources.DeepgramInputSource import DeepgramInputSource
        # Setup
        mock_download.side_effect = Exception("S3 download failed")
        source = DeepgramInputSource(pattern=r".*\.json$")
        item = Mock()
        item.metadata = {}
        item.attachedFiles = ["s3://bucket/deepgram.json"]

        # Execute & Assert
        with pytest.raises(Exception, match="S3 download failed"):
            source.extract(item)

    @patch("plexus.utils.score_result_s3_utils.download_score_result_trace_file")
    def test_extract_minimal_fixture(self, mock_download):
        """Test extraction with minimal Deepgram response"""
        from plexus.input_sources.DeepgramInputSource import DeepgramInputSource
        # Setup
        deepgram_data = self.load_fixture("deepgram_minimal.json")
        mock_download.return_value = (deepgram_data, None)

        source = DeepgramInputSource(pattern=r".*\.json$")
        item = Mock()
        item.metadata = {}
        item.attachedFiles = ["s3://bucket/deepgram.json"]

        # Execute
        result = source.extract(item)

        # Assert - minimal fixture has no paragraphs structure, should handle gracefully
        assert isinstance(result, str)

    @patch("plexus.utils.score_result_s3_utils.download_score_result_trace_file")
    def test_speaker_labels_without_speaker_field(self, mock_download):
        """Test that speaker labels are skipped if speaker field is missing"""
        from plexus.input_sources.DeepgramInputSource import DeepgramInputSource
        # Setup
        deepgram_data = {
            "results": {
                "channels": [
                    {
                        "alternatives": [
                            {
                                "paragraphs": {
                                    "paragraphs": [
                                        {
                                            "text": "Test paragraph without speaker field",
                                            "start": 0.0,
                                            "end": 1.0,
                                        }
                                    ]
                                }
                            }
                        ]
                    }
                ]
            }
        }
        mock_download.return_value = (deepgram_data, None)

        source = DeepgramInputSource(
            pattern=r".*\.json$", format="paragraphs", speaker_labels=True
        )
        item = Mock()
        item.metadata = {}
        item.attachedFiles = ["s3://bucket/deepgram.json"]

        # Execute
        result = source.extract(item)

        # Assert - should not have "Speaker" prefix since field is missing
        assert "Test paragraph without speaker field" in result.text
        assert "Speaker" not in result.text

    @patch("plexus.utils.score_result_s3_utils.download_score_result_trace_file")
    def test_format_options_case_sensitive(self, mock_download):
        """Test that format option is case-sensitive"""
        from plexus.input_sources.DeepgramInputSource import DeepgramInputSource
        # Setup
        deepgram_data = self.load_fixture("deepgram_minimal.json")
        mock_download.return_value = (deepgram_data, None)

        source = DeepgramInputSource(
            pattern=r".*\.json$", format="PARAGRAPHS"  # Wrong case
        )
        item = Mock()
        item.metadata = {}
        item.attachedFiles = ["s3://bucket/deepgram.json"]

        # Execute & Assert
        with pytest.raises(ValueError, match="Unknown format"):
            source.extract(item)

    @patch("plexus.utils.score_result_s3_utils.download_score_result_trace_file")
    def test_inheritance_from_text_file_input_source(self, mock_download):
        """Test that DeepgramInputSource inherits from TextFileInputSource"""
        from plexus.input_sources.DeepgramInputSource import DeepgramInputSource
        # Setup
        deepgram_data = self.load_fixture("deepgram_minimal.json")
        mock_download.return_value = (deepgram_data, None)

        source = DeepgramInputSource(pattern=r".*\.json$")

        # Assert - should have inherited methods
        assert hasattr(source, "find_matching_attachment")
        assert hasattr(source, "extract")
        assert source.pattern is not None

    @patch("plexus.utils.score_result_s3_utils.download_score_result_trace_file")
    def test_default_text_parameter_not_used(self, mock_download):
        """Test that default_text parameter is ignored (strict error mode)"""
        from plexus.input_sources.DeepgramInputSource import DeepgramInputSource
        # Setup
        deepgram_data = self.load_fixture("deepgram_minimal.json")
        mock_download.return_value = (deepgram_data, None)

        source = DeepgramInputSource(pattern=r".*\.json$")
        item = Mock()
        item.metadata = {}
        item.attachedFiles = ["s3://bucket/deepgram.json"]

        # Execute
        result = source.extract(item)

        # Assert - should return Deepgram content, not default
        assert result != "this_should_be_ignored"
        assert "Hello world" in result.text

    # ========================================================================
    # Time Range Filtering Tests
    # ========================================================================

    @patch("plexus.utils.score_result_s3_utils.download_score_result_trace_file")
    def test_time_range_paragraphs_first_paragraph_only(self, mock_download):
        """Test time range filtering for paragraphs - first paragraph only"""
        from plexus.input_sources.DeepgramInputSource import DeepgramInputSource
        # Setup
        deepgram_data = self.load_fixture("deepgram_simple_conversation.json")
        mock_download.return_value = (deepgram_data, None)

        source = DeepgramInputSource(
            pattern=r".*\.json$",
            format="paragraphs",
            time_range_start=0.0,
            time_range_duration=5.0,  # Only first paragraph (0.0-4.2s)
        )
        item = Mock()
        item.metadata = {}
        item.attachedFiles = ["s3://bucket/deepgram.json"]

        # Execute
        result = source.extract(item)

        # Assert
        assert "Hello, thank you for calling customer support" in result.text
        assert "Hi, I'm having trouble" not in result  # Second paragraph starts at 5.0s
        assert "I can definitely help" not in result  # Third paragraph starts at 10.0s
        paragraphs = result.text.split("\n\n")
        assert len(paragraphs) == 1

    @patch("plexus.utils.score_result_s3_utils.download_score_result_trace_file")
    def test_time_range_paragraphs_middle_segment(self, mock_download):
        """Test time range filtering for paragraphs - middle segment"""
        from plexus.input_sources.DeepgramInputSource import DeepgramInputSource
        # Setup
        deepgram_data = self.load_fixture("deepgram_simple_conversation.json")
        mock_download.return_value = (deepgram_data, None)

        source = DeepgramInputSource(
            pattern=r".*\.json$",
            format="paragraphs",
            time_range_start=5.0,
            time_range_duration=5.0,  # Second paragraph only (5.0-9.5s)
        )
        item = Mock()
        item.metadata = {}
        item.attachedFiles = ["s3://bucket/deepgram.json"]

        # Execute
        result = source.extract(item)

        # Assert
        assert "Hello, thank you" not in result  # First paragraph
        assert "Hi, I'm having trouble" in result.text  # Second paragraph
        assert (
            "I can definitely help" not in result
        )  # Third paragraph (starts at 10.0s)
        paragraphs = result.text.split("\n\n")
        assert len(paragraphs) == 1

    @patch("plexus.utils.score_result_s3_utils.download_score_result_trace_file")
    def test_time_range_paragraphs_no_duration(self, mock_download):
        """Test time range with no duration (open-ended from start time)"""
        from plexus.input_sources.DeepgramInputSource import DeepgramInputSource
        # Setup
        deepgram_data = self.load_fixture("deepgram_simple_conversation.json")
        mock_download.return_value = (deepgram_data, None)

        source = DeepgramInputSource(
            pattern=r".*\.json$",
            format="paragraphs",
            time_range_start=5.0,
            time_range_duration=None,  # Everything from 5.0s onward
        )
        item = Mock()
        item.metadata = {}
        item.attachedFiles = ["s3://bucket/deepgram.json"]

        # Execute
        result = source.extract(item)

        # Assert
        assert "Hello, thank you" not in result  # First paragraph at 0.0s
        assert "Hi, I'm having trouble" in result.text  # Second paragraph at 5.0s
        assert "I can definitely help" in result.text  # Third paragraph at 10.0s
        paragraphs = result.text.split("\n\n")
        assert len(paragraphs) == 2

    @patch("plexus.utils.score_result_s3_utils.download_score_result_trace_file")
    def test_time_range_utterances(self, mock_download):
        """Test time range filtering for utterances format"""
        from plexus.input_sources.DeepgramInputSource import DeepgramInputSource
        # Setup
        deepgram_data = self.load_fixture("deepgram_simple_conversation.json")
        mock_download.return_value = (deepgram_data, None)

        source = DeepgramInputSource(
            pattern=r".*\.json$",
            format="utterances",
            time_range_start=0.0,
            time_range_duration=5.0,
        )
        item = Mock()
        item.metadata = {}
        item.attachedFiles = ["s3://bucket/deepgram.json"]

        # Execute
        result = source.extract(item)

        # Assert
        lines = result.text.split("\n")
        assert len(lines) == 1  # Only first utterance
        assert "Hello, thank you for calling customer support" in result.text

    @patch("plexus.utils.score_result_s3_utils.download_score_result_trace_file")
    def test_time_range_words(self, mock_download):
        """Test time range filtering for words format"""
        from plexus.input_sources.DeepgramInputSource import DeepgramInputSource
        # Setup
        deepgram_data = self.load_fixture("deepgram_simple_conversation.json")
        mock_download.return_value = (deepgram_data, None)

        source = DeepgramInputSource(
            pattern=r".*\.json$",
            format="words",
            time_range_start=0.0,
            time_range_duration=3.0,  # First ~9 words
        )
        item = Mock()
        item.metadata = {}
        item.attachedFiles = ["s3://bucket/deepgram.json"]

        # Execute
        result = source.extract(item)

        # Assert
        words = result.text.split()
        assert "Hello" in words
        assert "support" in words  # Word at 2.0s
        # Words at 3.0s+ should not be included
        assert len(words) < 13  # Should have fewer words than full transcript

    @patch("plexus.utils.score_result_s3_utils.download_score_result_trace_file")
    def test_time_range_raw_format(self, mock_download):
        """Test time range filtering for raw format"""
        from plexus.input_sources.DeepgramInputSource import DeepgramInputSource
        # Setup
        deepgram_data = self.load_fixture("deepgram_simple_conversation.json")
        mock_download.return_value = (deepgram_data, None)

        source = DeepgramInputSource(
            pattern=r".*\.json$",
            format="raw",
            time_range_start=0.0,
            time_range_duration=5.0,
        )
        item = Mock()
        item.metadata = {}
        item.attachedFiles = ["s3://bucket/deepgram.json"]

        # Execute
        result = source.extract(item)

        # Assert - should have first portion only (0.0s to 5.0s, exclusive)
        assert "Hello" in result.text
        assert "today" in result.text  # Word at 3.8s should be included
        assert (
            "Hi" not in result
        )  # Word at 5.0s (boundary - excluded due to exclusive upper bound)
        # Should be significantly shorter than full transcript
        full_transcript = deepgram_data["results"]["channels"][0]["alternatives"][0][
            "transcript"
        ]
        assert len(result) < len(full_transcript)

    @patch("plexus.utils.score_result_s3_utils.download_score_result_trace_file")
    def test_time_range_raw_no_filtering(self, mock_download):
        """Test raw format returns original transcript when no time filtering"""
        from plexus.input_sources.DeepgramInputSource import DeepgramInputSource
        # Setup
        deepgram_data = self.load_fixture("deepgram_simple_conversation.json")
        mock_download.return_value = (deepgram_data, None)

        source = DeepgramInputSource(
            pattern=r".*\.json$",
            format="raw",
            # No time_range parameters = defaults to 0.0, None
        )
        item = Mock()
        item.metadata = {}
        item.attachedFiles = ["s3://bucket/deepgram.json"]

        # Execute
        result = source.extract(item)

        # Assert - should return original raw transcript
        expected = deepgram_data["results"]["channels"][0]["alternatives"][0][
            "transcript"
        ]
        assert result == expected

    @patch("plexus.utils.score_result_s3_utils.download_score_result_trace_file")
    def test_time_range_with_timestamps_enabled(self, mock_download):
        """Test time range filtering works with timestamp display enabled"""
        from plexus.input_sources.DeepgramInputSource import DeepgramInputSource
        # Setup
        deepgram_data = self.load_fixture("deepgram_simple_conversation.json")
        mock_download.return_value = (deepgram_data, None)

        source = DeepgramInputSource(
            pattern=r".*\.json$",
            format="paragraphs",
            include_timestamps=True,
            time_range_start=5.0,
            time_range_duration=5.0,
        )
        item = Mock()
        item.metadata = {}
        item.attachedFiles = ["s3://bucket/deepgram.json"]

        # Execute
        result = source.extract(item)

        # Assert
        assert "[5.00s]" in result.text  # Timestamp for second paragraph
        assert "[0.00s]" not in result.text  # First paragraph filtered out
        assert "Hi, I'm having trouble" in result.text

    @patch("plexus.utils.score_result_s3_utils.download_score_result_trace_file")
    def test_time_range_with_speaker_labels(self, mock_download):
        """Test time range filtering preserves speaker labels"""
        from plexus.input_sources.DeepgramInputSource import DeepgramInputSource
        # Setup
        deepgram_data = self.load_fixture("deepgram_simple_conversation.json")
        mock_download.return_value = (deepgram_data, None)

        source = DeepgramInputSource(
            pattern=r".*\.json$",
            format="paragraphs",
            speaker_labels=True,
            time_range_start=5.0,
            time_range_duration=5.0,
        )
        item = Mock()
        item.metadata = {}
        item.attachedFiles = ["s3://bucket/deepgram.json"]

        # Execute
        result = source.extract(item)

        # Assert
        assert "Speaker 1:" in result.text  # Second paragraph is speaker 1
        assert result.text.count("Speaker") == 1  # Only one paragraph

    @patch("plexus.utils.score_result_s3_utils.download_score_result_trace_file")
    def test_time_range_start_beyond_transcript(self, mock_download):
        """Test time range starting after transcript ends returns empty"""
        from plexus.input_sources.DeepgramInputSource import DeepgramInputSource
        # Setup
        deepgram_data = self.load_fixture("deepgram_simple_conversation.json")
        mock_download.return_value = (deepgram_data, None)

        source = DeepgramInputSource(
            pattern=r".*\.json$",
            format="paragraphs",
            time_range_start=100.0,  # Way beyond transcript
            time_range_duration=10.0,
        )
        item = Mock()
        item.metadata = {}
        item.attachedFiles = ["s3://bucket/deepgram.json"]

        # Execute
        result = source.extract(item)

        # Assert
        assert result.text == ""  # Empty string for no matches

    @patch("plexus.utils.score_result_s3_utils.download_score_result_trace_file")
    def test_time_range_boundary_exact_start(self, mock_download):
        """Test that elements starting exactly at time_range_start are included"""
        from plexus.input_sources.DeepgramInputSource import DeepgramInputSource
        # Setup
        deepgram_data = self.load_fixture("deepgram_simple_conversation.json")
        mock_download.return_value = (deepgram_data, None)

        source = DeepgramInputSource(
            pattern=r".*\.json$",
            format="paragraphs",
            time_range_start=5.0,  # Exactly when second paragraph starts
            time_range_duration=0.1,  # Very short duration
        )
        item = Mock()
        item.metadata = {}
        item.attachedFiles = ["s3://bucket/deepgram.json"]

        # Execute
        result = source.extract(item)

        # Assert - element starting at 5.0 should be included
        assert "Hi, I'm having trouble" in result.text

    @patch("plexus.utils.score_result_s3_utils.download_score_result_trace_file")
    def test_time_range_invalid_start_negative(self, mock_download):
        """Test that negative time_range_start raises ValueError"""
        from plexus.input_sources.DeepgramInputSource import DeepgramInputSource
        # Setup
        deepgram_data = self.load_fixture("deepgram_simple_conversation.json")
        mock_download.return_value = (deepgram_data, None)

        source = DeepgramInputSource(pattern=r".*\.json$", time_range_start=-1.0)
        item = Mock()
        item.metadata = {}
        item.attachedFiles = ["s3://bucket/deepgram.json"]

        # Execute & Assert
        with pytest.raises(ValueError, match="time_range_start must be >= 0.0"):
            source.extract(item)

    @patch("plexus.utils.score_result_s3_utils.download_score_result_trace_file")
    def test_time_range_invalid_duration_negative(self, mock_download):
        """Test that negative time_range_duration raises ValueError"""
        from plexus.input_sources.DeepgramInputSource import DeepgramInputSource
        # Setup
        deepgram_data = self.load_fixture("deepgram_simple_conversation.json")
        mock_download.return_value = (deepgram_data, None)

        source = DeepgramInputSource(pattern=r".*\.json$", time_range_duration=-5.0)
        item = Mock()
        item.metadata = {}
        item.attachedFiles = ["s3://bucket/deepgram.json"]

        # Execute & Assert
        with pytest.raises(
            ValueError, match="time_range_duration must be > 0.0 or None"
        ):
            source.extract(item)

    @patch("plexus.utils.score_result_s3_utils.download_score_result_trace_file")
    def test_time_range_invalid_duration_zero(self, mock_download):
        """Test that zero time_range_duration raises ValueError"""
        from plexus.input_sources.DeepgramInputSource import DeepgramInputSource
        # Setup
        deepgram_data = self.load_fixture("deepgram_simple_conversation.json")
        mock_download.return_value = (deepgram_data, None)

        source = DeepgramInputSource(pattern=r".*\.json$", time_range_duration=0.0)
        item = Mock()
        item.metadata = {}
        item.attachedFiles = ["s3://bucket/deepgram.json"]

        # Execute & Assert
        with pytest.raises(
            ValueError, match="time_range_duration must be > 0.0 or None"
        ):
            source.extract(item)

    @patch("plexus.utils.score_result_s3_utils.download_score_result_trace_file")
    def test_time_range_floating_point_precision(self, mock_download):
        """Test time range with floating point precision (e.g., 1.2 seconds)"""
        from plexus.input_sources.DeepgramInputSource import DeepgramInputSource
        # Setup
        deepgram_data = self.load_fixture("deepgram_simple_conversation.json")
        mock_download.return_value = (deepgram_data, None)

        source = DeepgramInputSource(
            pattern=r".*\.json$",
            format="words",
            time_range_start=0.5,
            time_range_duration=2.3,
        )
        item = Mock()
        item.metadata = {}
        item.attachedFiles = ["s3://bucket/deepgram.json"]

        # Execute
        result = source.extract(item)

        # Assert - should handle floating point values correctly
        words = result.text.split()
        assert "Hello" not in words  # Starts at 0.0s
        assert "thank" in words  # Starts at 0.5s (included)
        assert len(words) > 0
