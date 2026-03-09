import json
import sys
from unittest.mock import Mock, patch

import pytest

import plexus.input_sources.DeepgramInputSource  # noqa: F401


class TestDeepgramInputSource:
    def load_fixture(self, filename):
        with open(f"tests/fixtures/{filename}", "r") as f:
            return json.load(f)

    @patch.object(
        sys.modules["plexus.input_sources.DeepgramInputSource"],
        "download_score_result_trace_file",
    )
    def test_extract_returns_raw_transcript_text_and_deepgram_metadata(self, mock_download):
        from plexus.input_sources.DeepgramInputSource import DeepgramInputSource

        deepgram_data = self.load_fixture("deepgram_simple_conversation.json")
        mock_download.return_value = (deepgram_data, None)

        source = DeepgramInputSource(pattern=r".*deepgram.*\.json$")
        item = Mock()
        item.metadata = {}
        item.attachedFiles = ["s3://bucket/path/deepgram_result.json"]

        result = source.extract(item)

        expected_text = deepgram_data["results"]["channels"][0]["alternatives"][0][
            "transcript"
        ]
        assert result.text == expected_text
        assert result.metadata["input_source"] == "DeepgramInputSource"
        assert result.metadata["attachment_key"] == "s3://bucket/path/deepgram_result.json"
        assert result.metadata["deepgram"] == deepgram_data

    @patch.object(
        sys.modules["plexus.input_sources.DeepgramInputSource"],
        "download_score_result_trace_file",
    )
    def test_extract_ignores_formatting_options(self, mock_download):
        from plexus.input_sources.DeepgramInputSource import DeepgramInputSource

        deepgram_data = self.load_fixture("deepgram_simple_conversation.json")
        mock_download.return_value = (deepgram_data, None)

        source = DeepgramInputSource(
            pattern=r".*\.json$",
            format="utterances",
            include_timestamps=True,
            speaker_labels=True,
            time_range_start=10,
            time_range_duration=5,
        )
        item = Mock()
        item.metadata = {}
        item.attachedFiles = ["s3://bucket/deepgram.json"]

        result = source.extract(item)

        expected_text = deepgram_data["results"]["channels"][0]["alternatives"][0][
            "transcript"
        ]
        assert result.text == expected_text
        assert result.metadata["deepgram"] == deepgram_data

    def test_extract_no_matching_attachment(self):
        from plexus.input_sources.DeepgramInputSource import DeepgramInputSource

        source = DeepgramInputSource(pattern=r".*deepgram.*\.json$")
        item = Mock()
        item.metadata = {}
        item.attachedFiles = ["s3://bucket/path/transcript.txt", "s3://bucket/path/other.xml"]

        with pytest.raises(ValueError) as exc_info:
            source.extract(item)

        assert "No Deepgram file matching pattern" in str(exc_info.value)
        assert "Available attachments:" in str(exc_info.value)

    @patch.object(
        sys.modules["plexus.input_sources.DeepgramInputSource"],
        "download_score_result_trace_file",
    )
    def test_extract_download_failure_propagates(self, mock_download):
        from plexus.input_sources.DeepgramInputSource import DeepgramInputSource

        mock_download.side_effect = Exception("S3 download failed")

        source = DeepgramInputSource(pattern=r".*\.json$")
        item = Mock()
        item.metadata = {}
        item.attachedFiles = ["s3://bucket/deepgram.json"]

        with pytest.raises(Exception, match="S3 download failed"):
            source.extract(item)

    @patch.object(
        sys.modules["plexus.input_sources.DeepgramInputSource"],
        "download_score_result_trace_file",
    )
    def test_extract_malformed_json_raises_key_error(self, mock_download):
        from plexus.input_sources.DeepgramInputSource import DeepgramInputSource

        mock_download.return_value = ({"invalid": "structure"}, None)

        source = DeepgramInputSource(pattern=r".*\.json$")
        item = Mock()
        item.metadata = {}
        item.attachedFiles = ["s3://bucket/deepgram.json"]

        with pytest.raises(KeyError):
            source.extract(item)

    @patch.object(
        sys.modules["plexus.input_sources.DeepgramInputSource"],
        "download_score_result_trace_file",
    )
    def test_extract_merges_existing_item_metadata(self, mock_download):
        from plexus.input_sources.DeepgramInputSource import DeepgramInputSource

        deepgram_data = self.load_fixture("deepgram_minimal.json")
        mock_download.return_value = (deepgram_data, None)

        source = DeepgramInputSource(pattern=r".*\.json$")
        item = Mock()
        item.metadata = {"existing": "value"}
        item.attachedFiles = ["s3://bucket/deepgram.json"]

        result = source.extract(item)

        assert result.metadata["existing"] == "value"
        assert result.metadata["deepgram"] == deepgram_data

    @patch.object(
        sys.modules["plexus.input_sources.DeepgramInputSource"],
        "download_score_result_trace_file",
    )
    def test_extract_parses_string_metadata(self, mock_download):
        from plexus.input_sources.DeepgramInputSource import DeepgramInputSource

        deepgram_data = self.load_fixture("deepgram_minimal.json")
        mock_download.return_value = (deepgram_data, None)

        source = DeepgramInputSource(pattern=r".*\.json$")
        item = Mock()
        item.metadata = '{"existing":"value"}'
        item.attachedFiles = ["s3://bucket/deepgram.json"]

        result = source.extract(item)

        assert result.metadata["existing"] == "value"
        assert result.metadata["deepgram"] == deepgram_data
