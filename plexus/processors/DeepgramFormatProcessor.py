from typing import Optional, List, Tuple, TYPE_CHECKING
from plexus.processors.DataframeProcessor import Processor

if TYPE_CHECKING:
    from plexus.scores.Score import Score


class DeepgramFormatProcessor(Processor):
    """
    Processor that formats Deepgram structured data into configurable text.

    Reads metadata['deepgram'] and generates formatted text for ScoreInput.text.
    Unlike DeepgramInputSource (which only reads channel 0), this processor
    merges data from ALL channels sorted by time, properly handling stereo
    recordings where channel 0 = agent, channel 1 = customer.

    Parameters:
        format: "paragraphs" | "sentences" | "words" (default: "paragraphs")
            - paragraphs: Groups of sentences, separated by blank lines
            - sentences: Individual sentences, one per line
            - words: Space-separated words
        speaker_labels: bool (default: False) — prefix with "Speaker N: "
        include_timestamps: bool (default: False) — prefix with "[12.50s]"
        channel: int or None (default: None) — filter to a specific channel

    Example usage in YAML:
        item:
          class: DeepgramInputSource
          options:
            pattern: '.*deepgram.*\\.json$'
            format: paragraphs
            include_raw_data: true
          processors:
            - class: DeepgramFormatProcessor
              parameters:
                format: sentences
                speaker_labels: true
                channel: 1        # Customer channel only
    """

    def process(self, score_input: 'Score.Input') -> 'Score.Input':
        from plexus.scores.Score import Score

        deepgram = score_input.metadata.get('deepgram')
        if not deepgram:
            return score_input

        fmt = self.parameters.get('format', 'paragraphs')
        speaker_labels = self.parameters.get('speaker_labels', False)
        include_timestamps = self.parameters.get('include_timestamps', False)
        channel_filter = self.parameters.get('channel')
        if channel_filter is not None:
            channel_filter = int(channel_filter)

        if fmt == 'paragraphs':
            text = self._format_paragraphs(
                deepgram, speaker_labels, include_timestamps, channel_filter
            )
        elif fmt == 'sentences':
            text = self._format_sentences(
                deepgram, speaker_labels, include_timestamps, channel_filter
            )
        elif fmt == 'words':
            text = self._format_words(
                deepgram, speaker_labels, include_timestamps, channel_filter
            )
        else:
            raise ValueError(
                f"Unknown format: {fmt}. "
                "Must be one of: paragraphs, sentences, words"
            )

        return Score.Input(
            text=text,
            metadata=score_input.metadata,
            results=score_input.results,
        )

    def _collect_paragraphs(
        self, deepgram: dict, channel_filter: Optional[int]
    ) -> List[Tuple[float, int, dict]]:
        """
        Collect paragraphs from all channels, each tagged with channel index.

        Returns list of (start_time, channel_index, paragraph_dict) tuples,
        sorted by start time.
        """
        results = []
        channels = deepgram.get('results', {}).get('channels', [])
        for ch_idx, channel in enumerate(channels):
            if channel_filter is not None and ch_idx != channel_filter:
                continue
            for alt in channel.get('alternatives', []):
                paras = alt.get('paragraphs', {}).get('paragraphs', [])
                for para in paras:
                    results.append((para.get('start', 0.0), ch_idx, para))
        results.sort(key=lambda x: x[0])
        return results

    def _collect_words(
        self, deepgram: dict, channel_filter: Optional[int]
    ) -> List[Tuple[float, int, dict]]:
        """
        Collect words from all channels, each tagged with channel index.

        Returns list of (start_time, channel_index, word_dict) tuples,
        sorted by start time.
        """
        results = []
        channels = deepgram.get('results', {}).get('channels', [])
        for ch_idx, channel in enumerate(channels):
            if channel_filter is not None and ch_idx != channel_filter:
                continue
            for alt in channel.get('alternatives', []):
                for word in alt.get('words', []):
                    results.append((word.get('start', 0.0), ch_idx, word))
        results.sort(key=lambda x: x[0])
        return results

    def _get_speaker_label(self, channel_idx: int, para_or_word: dict) -> str:
        """Get speaker label, preferring 'speaker' field, falling back to channel."""
        speaker = para_or_word.get('speaker')
        if speaker is not None:
            return f"Speaker {speaker}"
        return f"Channel {channel_idx}"

    def _format_paragraphs(
        self,
        deepgram: dict,
        speaker_labels: bool,
        include_timestamps: bool,
        channel_filter: Optional[int],
    ) -> str:
        paragraphs = self._collect_paragraphs(deepgram, channel_filter)
        lines = []
        for start_time, ch_idx, para in paragraphs:
            # Build paragraph text from sentences or text field
            if 'sentences' in para:
                text = ' '.join(s['text'] for s in para['sentences'])
            elif 'text' in para:
                text = para['text']
            else:
                continue

            if not text:
                continue

            if speaker_labels:
                label = self._get_speaker_label(ch_idx, para)
                text = f"{label}: {text}"

            if include_timestamps:
                text = f"[{start_time:.2f}s] {text}"

            lines.append(text)

        return '\n\n'.join(lines)

    def _format_sentences(
        self,
        deepgram: dict,
        speaker_labels: bool,
        include_timestamps: bool,
        channel_filter: Optional[int],
    ) -> str:
        paragraphs = self._collect_paragraphs(deepgram, channel_filter)
        lines = []
        for _, ch_idx, para in paragraphs:
            sentences = para.get('sentences', [])
            if not sentences:
                # Fall back to paragraph text as a single "sentence"
                text = para.get('text', '')
                if text:
                    sentences = [{'text': text, 'start': para.get('start', 0.0)}]

            for sentence in sentences:
                text = sentence.get('text', '')
                if not text:
                    continue

                if speaker_labels:
                    label = self._get_speaker_label(ch_idx, para)
                    text = f"{label}: {text}"

                if include_timestamps:
                    text = f"[{sentence.get('start', 0.0):.2f}s] {text}"

                lines.append(text)

        return '\n'.join(lines)

    def _format_words(
        self,
        deepgram: dict,
        speaker_labels: bool,
        include_timestamps: bool,
        channel_filter: Optional[int],
    ) -> str:
        words = self._collect_words(deepgram, channel_filter)

        if not speaker_labels and not include_timestamps:
            return ' '.join(w['word'] for _, _, w in words)

        parts = []
        for start_time, ch_idx, word in words:
            text = word['word']
            if include_timestamps:
                text = f"{text}[{start_time:.2f}]"
            if speaker_labels:
                label = self._get_speaker_label(ch_idx, word)
                text = f"{label}: {text}"
            parts.append(text)

        return ' '.join(parts)
