from typing import Optional
from plexus.input_sources.TextFileInputSource import TextFileInputSource
from plexus.utils.score_result_s3_utils import download_score_result_trace_file


class DeepgramInputSource(TextFileInputSource):
    """
    Extracts and formats text from Deepgram JSON transcription files.
    Supports multiple output formats: paragraphs, utterances, words, raw.
    """

    def extract(self, item) -> 'Score.Input':
        """
        Parse Deepgram JSON and format transcript into Score.Input.

        Options:
            format: "paragraphs" (default), "utterances", "words", "raw"
            include_timestamps: bool (default False)
            speaker_labels: bool (default False)
            time_range_start: float (default 0.0) - Start time in seconds
            time_range_duration: float or None (default None) - Duration in seconds, None = no end limit

        Returns:
            Score.Input with formatted transcript text and Deepgram metadata

        Raises:
            ValueError: If no matching attachment, invalid format, or invalid time range parameters
            KeyError: If Deepgram JSON structure is invalid
            Exception: If file download or parsing fails
        """
        from plexus.scores.Score import Score

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

        # Extract time range options
        time_range_start = self.options.get("time_range_start", 0.0)
        time_range_duration = self.options.get("time_range_duration", None)

        # Validate time range parameters
        if time_range_start < 0.0:
            raise ValueError(f"time_range_start must be >= 0.0, got {time_range_start}")
        if time_range_duration is not None and time_range_duration <= 0.0:
            raise ValueError(
                f"time_range_duration must be > 0.0 or None, got {time_range_duration}"
            )

        # Format based on selected type (exceptions propagate)
        if format_type == "paragraphs":
            formatted_text = self._format_paragraphs(
                deepgram_result,
                include_timestamps,
                speaker_labels,
                time_range_start,
                time_range_duration,
            )
        elif format_type == "utterances":
            formatted_text = self._format_utterances(
                deepgram_result,
                include_timestamps,
                speaker_labels,
                time_range_start,
                time_range_duration,
            )
        elif format_type == "words":
            formatted_text = self._format_words(
                deepgram_result,
                include_timestamps,
                time_range_start,
                time_range_duration,
            )
        elif format_type == "raw":
            formatted_text = self._format_raw(
                deepgram_result, time_range_start, time_range_duration
            )
        else:
            raise ValueError(
                f"Unknown format: {format_type}. Must be one of: paragraphs, utterances, words, raw"
            )

        # Build metadata with Deepgram-specific information
        metadata = item.metadata.copy() if item.metadata else {}
        metadata['input_source'] = 'DeepgramInputSource'
        metadata['format'] = format_type
        metadata['attachment_key'] = attachment_key

        # Add time range info if used
        if time_range_start != 0.0 or time_range_duration is not None:
            metadata['time_range_start'] = time_range_start
            if time_range_duration is not None:
                metadata['time_range_duration'] = time_range_duration

        # Return Score.Input
        return Score.Input(text=formatted_text, metadata=metadata)

    def _is_in_time_range(
        self,
        start_time: float,
        time_range_start: float,
        time_range_duration: Optional[float],
    ) -> bool:
        """
        Check if element's start time falls within the configured time range.

        Args:
            start_time: The start time of the element (paragraph/utterance/word) in seconds
            time_range_start: The start of the time range filter in seconds
            time_range_duration: The duration of the time range in seconds, or None for no end limit

        Returns:
            True if the element starts within the time range, False otherwise
        """
        if time_range_duration is None:
            return start_time >= time_range_start
        end_time = time_range_start + time_range_duration
        return time_range_start <= start_time < end_time

    def _format_paragraphs(
        self,
        deepgram_result: dict,
        timestamps: bool,
        speakers: bool,
        time_range_start: float = 0.0,
        time_range_duration: Optional[float] = None,
    ) -> str:
        """Format using Deepgram's paragraph structure with optional time range filtering"""
        try:
            paragraphs = deepgram_result["results"]["channels"][0]["alternatives"][0][
                "paragraphs"
            ]["paragraphs"]
        except KeyError:
            # Fallback to raw transcript if paragraphs structure is missing
            return deepgram_result["results"]["channels"][0]["alternatives"][0][
                "transcript"
            ]

        # Filter paragraphs by time range
        filtered_paragraphs = [
            p
            for p in paragraphs
            if self._is_in_time_range(p["start"], time_range_start, time_range_duration)
        ]

        lines = []
        for para in filtered_paragraphs:
            text = para["text"]

            if speakers and "speaker" in para:
                text = f"Speaker {para['speaker']}: {text}"

            if timestamps:
                text = f"[{para['start']:.2f}s] {text}"

            lines.append(text)

        return "\n\n".join(lines)

    def _format_utterances(
        self,
        deepgram_result: dict,
        timestamps: bool,
        speakers: bool,
        time_range_start: float = 0.0,
        time_range_duration: Optional[float] = None,
    ) -> str:
        """Format using Deepgram's utterance structure with optional time range filtering"""
        utterances = deepgram_result["results"]["utterances"]

        # Filter utterances by time range
        filtered_utterances = [
            u
            for u in utterances
            if self._is_in_time_range(u["start"], time_range_start, time_range_duration)
        ]

        lines = []
        for utt in filtered_utterances:
            text = utt["transcript"]

            if speakers:
                text = f"Speaker {utt['speaker']}: {text}"

            if timestamps:
                text = f"[{utt['start']:.2f}s] {text}"

            lines.append(text)

        return "\n".join(lines)

    def _format_words(
        self,
        deepgram_result: dict,
        timestamps: bool,
        time_range_start: float = 0.0,
        time_range_duration: Optional[float] = None,
    ) -> str:
        """Format word-by-word with optional timestamps and time range filtering"""
        words = deepgram_result["results"]["channels"][0]["alternatives"][0]["words"]

        # Filter words by time range
        filtered_words = [
            w
            for w in words
            if self._is_in_time_range(w["start"], time_range_start, time_range_duration)
        ]

        if timestamps:
            return " ".join([f"{w['word']}[{w['start']:.2f}]" for w in filtered_words])
        else:
            return " ".join([w["word"] for w in filtered_words])

    def _format_raw(
        self,
        deepgram_result: dict,
        time_range_start: float = 0.0,
        time_range_duration: Optional[float] = None,
    ) -> str:
        """
        Format as raw transcript text with optional time range filtering.

        When time filtering is needed, reconstructs the transcript from filtered words.
        Otherwise returns the original raw transcript for optimal performance.
        """
        # If no time filtering needed, return original raw transcript
        if time_range_start == 0.0 and time_range_duration is None:
            return deepgram_result["results"]["channels"][0]["alternatives"][0][
                "transcript"
            ]

        # Time filtering requires word-level reconstruction
        words = deepgram_result["results"]["channels"][0]["alternatives"][0]["words"]
        filtered_words = [
            w["word"]
            for w in words
            if self._is_in_time_range(w["start"], time_range_start, time_range_duration)
        ]
        return " ".join(filtered_words)
