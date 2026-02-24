import copy
from typing import Optional, TYPE_CHECKING
from plexus.processors.DataframeProcessor import Processor

if TYPE_CHECKING:
    from plexus.scores.Score import Score


class DeepgramTimeSliceProcessor(Processor):
    """
    Processor that filters Deepgram data in metadata to a time window.

    Filters both the structured Deepgram JSON in metadata['deepgram'] and
    regenerates ScoreInput.text from the filtered data. This enables
    composable time-based slicing in the processor pipeline.

    Parameters:
        start: Start time in seconds (default: 0.0)
        end: End time in seconds (default: None = no limit)
        last: Last N seconds of the call. Reads total duration from
              deepgram metadata. Overrides start/end if set.

    Example usage in YAML:
        item:
          class: DeepgramInputSource
          options:
            pattern: '.*deepgram.*\\.json$'
            format: paragraphs
            include_raw_data: true
          processors:
            - class: DeepgramTimeSliceProcessor
              parameters:
                end: 60          # First 60 seconds
            - class: DeepgramFormatProcessor
              parameters:
                format: sentences
                speaker_labels: true
    """

    def process(self, score_input: 'Score.Input') -> 'Score.Input':
        from plexus.scores.Score import Score

        deepgram = score_input.metadata.get('deepgram')
        if not deepgram:
            return score_input

        start = float(self.parameters.get('start', 0.0))
        end = self.parameters.get('end')
        last = self.parameters.get('last')

        if end is not None:
            end = float(end)
        if last is not None:
            last = float(last)

        # "last N seconds" mode: compute start from total duration
        if last is not None:
            duration = deepgram.get('metadata', {}).get('duration')
            if duration is not None:
                start = max(0.0, float(duration) - last)
                end = None  # through end of call
            else:
                # Can't compute "last" without duration; pass through
                return score_input

        # Deep copy to avoid mutating original
        filtered = copy.deepcopy(deepgram)

        # Filter all channels
        for channel in filtered.get('results', {}).get('channels', []):
            for alt in channel.get('alternatives', []):
                # Filter words
                if 'words' in alt:
                    alt['words'] = [
                        w for w in alt['words']
                        if self._in_range(w['start'], start, end)
                    ]
                    # Regenerate transcript from filtered words
                    alt['transcript'] = ' '.join(
                        w['word'] for w in alt['words']
                    )

                # Filter paragraphs and sentences within them
                if 'paragraphs' in alt and 'paragraphs' in alt['paragraphs']:
                    filtered_paras = []
                    for para in alt['paragraphs']['paragraphs']:
                        # Filter sentences within paragraph
                        if 'sentences' in para:
                            para['sentences'] = [
                                s for s in para['sentences']
                                if self._in_range(s['start'], start, end)
                            ]
                            if not para['sentences']:
                                continue
                            # Update paragraph text from remaining sentences
                            para['text'] = ' '.join(
                                s['text'] for s in para['sentences']
                            )
                        elif not self._in_range(para.get('start', 0), start, end):
                            continue
                        filtered_paras.append(para)

                    alt['paragraphs']['paragraphs'] = filtered_paras
                    # Regenerate paragraphs transcript
                    alt['paragraphs']['transcript'] = ' '.join(
                        p.get('text', '') for p in filtered_paras
                    )

        # Filter utterances (top-level, if present)
        if 'utterances' in filtered.get('results', {}):
            filtered['results']['utterances'] = [
                u for u in filtered['results']['utterances']
                if self._in_range(u['start'], start, end)
            ]

        # Regenerate text from filtered paragraphs
        text = self._rebuild_text(filtered)

        # Build new metadata with filtered deepgram data
        new_metadata = score_input.metadata.copy()
        new_metadata['deepgram'] = filtered

        return Score.Input(
            text=text,
            metadata=new_metadata,
            results=score_input.results,
        )

    @staticmethod
    def _in_range(t: float, start: float, end: Optional[float]) -> bool:
        if t < start:
            return False
        if end is not None and t >= end:
            return False
        return True

    @staticmethod
    def _rebuild_text(deepgram: dict) -> str:
        """Rebuild text from filtered paragraphs with speaker labels."""
        lines = []
        for ch_idx, channel in enumerate(
            deepgram.get('results', {}).get('channels', [])
        ):
            for alt in channel.get('alternatives', []):
                paras = (
                    alt.get('paragraphs', {}).get('paragraphs', [])
                    if 'paragraphs' in alt
                    else []
                )
                for para in paras:
                    text = para.get('text', '')
                    if not text and 'sentences' in para:
                        text = ' '.join(
                            s['text'] for s in para['sentences']
                        )
                    if not text:
                        continue
                    speaker = para.get('speaker', ch_idx)
                    lines.append((para.get('start', 0), f"Speaker {speaker}: {text}"))

        # Sort by start time (important for multi-channel)
        lines.sort(key=lambda x: x[0])
        return '\n\n'.join(line for _, line in lines)
