from plexus.input_sources.TextFileInputSource import TextFileInputSource
from plexus.utils.score_result_s3_utils import download_score_result_trace_file


class DeepgramInputSource(TextFileInputSource):
    """
    Extracts and formats text from Deepgram JSON transcription files.
    Supports multiple output formats: paragraphs, utterances, words, raw.
    """

    def extract(self, item, default_text: str) -> str:
        """
        Parse Deepgram JSON and format transcript.

        Options:
            format: "paragraphs" (default), "utterances", "words", "raw"
            include_timestamps: bool (default False)
            speaker_labels: bool (default False)

        Returns:
            Formatted transcript text

        Raises:
            ValueError: If no matching attachment or invalid format specified
            KeyError: If Deepgram JSON structure is invalid
            Exception: If file download or parsing fails
        """
        # Find matching attachment (raises ValueError if not found)
        attachment_key = self.find_matching_attachment(item)

        if not attachment_key:
            available = (
                item.attachedFiles
                if item and hasattr(item, "attachedFiles")
                else "None"
            )
            raise ValueError(
                f"No Deepgram file matching pattern '{self.pattern.pattern}' "
                f"found. Available attachments: {available}"
            )

        # Download and parse JSON (exceptions propagate)
        deepgram_result, _ = download_score_result_trace_file(attachment_key)

        # Extract formatting options
        format_type = self.options.get("format", "paragraphs")
        include_timestamps = self.options.get("include_timestamps", False)
        speaker_labels = self.options.get("speaker_labels", False)

        # Format based on selected type (exceptions propagate)
        if format_type == "paragraphs":
            return self._format_paragraphs(
                deepgram_result, include_timestamps, speaker_labels
            )
        elif format_type == "utterances":
            return self._format_utterances(
                deepgram_result, include_timestamps, speaker_labels
            )
        elif format_type == "words":
            return self._format_words(deepgram_result, include_timestamps)
        elif format_type == "raw":
            # Just the full transcript text
            return deepgram_result["results"]["channels"][0]["alternatives"][0][
                "transcript"
            ]
        else:
            raise ValueError(
                f"Unknown format: {format_type}. Must be one of: paragraphs, utterances, words, raw"
            )

    def _format_paragraphs(
        self, deepgram_result: dict, timestamps: bool, speakers: bool
    ) -> str:
        """Format using Deepgram's paragraph structure"""
        try:
            paragraphs = deepgram_result["results"]["channels"][0]["alternatives"][0][
                "paragraphs"
            ]["paragraphs"]
        except KeyError:
            # Fallback to raw transcript if paragraphs structure is missing
            return deepgram_result["results"]["channels"][0]["alternatives"][0][
                "transcript"
            ]

        lines = []
        for para in paragraphs:
            text = para["text"]

            if speakers and "speaker" in para:
                text = f"Speaker {para['speaker']}: {text}"

            if timestamps:
                text = f"[{para['start']:.2f}s] {text}"

            lines.append(text)

        return "\n\n".join(lines)

    def _format_utterances(
        self, deepgram_result: dict, timestamps: bool, speakers: bool
    ) -> str:
        """Format using Deepgram's utterance structure"""
        utterances = deepgram_result["results"]["utterances"]

        lines = []
        for utt in utterances:
            text = utt["transcript"]

            if speakers:
                text = f"Speaker {utt['speaker']}: {text}"

            if timestamps:
                text = f"[{utt['start']:.2f}s] {text}"

            lines.append(text)

        return "\n".join(lines)

    def _format_words(self, deepgram_result: dict, timestamps: bool) -> str:
        """Format word-by-word with optional timestamps"""
        words = deepgram_result["results"]["channels"][0]["alternatives"][0]["words"]

        if timestamps:
            return " ".join([f"{w['word']}[{w['start']:.2f}]" for w in words])
        else:
            return " ".join([w["word"] for w in words])
