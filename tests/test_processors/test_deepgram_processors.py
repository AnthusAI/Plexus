"""Tests for DeepgramTimeSliceProcessor and DeepgramFormatProcessor."""

import copy
import json
import os
import unittest

from plexus.scores.Score import Score


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), '..', 'fixtures')


def load_fixture(name):
    with open(os.path.join(FIXTURES_DIR, name)) as f:
        return json.load(f)


def make_input(deepgram_data, text="placeholder"):
    """Create a Score.Input with Deepgram data in metadata."""
    return Score.Input(
        text=text,
        metadata={'deepgram': deepgram_data, 'format': 'paragraphs'},
    )


# ---------------------------------------------------------------------------
# DeepgramTimeSliceProcessor
# ---------------------------------------------------------------------------
class TestDeepgramTimeSliceProcessor(unittest.TestCase):

    def setUp(self):
        self.mono = load_fixture('deepgram_simple_conversation.json')
        self.stereo = load_fixture('deepgram_stereo_conversation.json')

    def _make_processor(self, **params):
        from plexus.processors.DeepgramTimeSliceProcessor import DeepgramTimeSliceProcessor
        return DeepgramTimeSliceProcessor(**params)

    # --- basic start/end filtering ---

    def test_end_filters_to_first_n_seconds(self):
        proc = self._make_processor(end=5.0)
        inp = make_input(self.mono)
        result = proc.process(inp)

        # Only the first paragraph (0.0–4.2s) should survive
        paras = result.metadata['deepgram']['results']['channels'][0]['alternatives'][0]['paragraphs']['paragraphs']
        self.assertEqual(len(paras), 1)
        self.assertIn('Hello', paras[0]['sentences'][0]['text'])

        # Words should be filtered too
        words = result.metadata['deepgram']['results']['channels'][0]['alternatives'][0]['words']
        self.assertTrue(all(w['start'] < 5.0 for w in words))

        # Utterances filtered
        utts = result.metadata['deepgram']['results']['utterances']
        self.assertEqual(len(utts), 1)

    def test_start_filters_after_timestamp(self):
        proc = self._make_processor(start=8.0)
        inp = make_input(self.mono)
        result = proc.process(inp)

        # Paragraphs starting at 5.0 should be excluded (its sentences start < 8.0 except one at 8.0)
        paras = result.metadata['deepgram']['results']['channels'][0]['alternatives'][0]['paragraphs']['paragraphs']
        # First paragraph (0.0) excluded, second paragraph has sentence at 8.0 (included) and 5.0 (excluded)
        # Third paragraph (10.0) fully included
        for para in paras:
            for s in para.get('sentences', []):
                self.assertGreaterEqual(s['start'], 8.0)

    def test_start_and_end_window(self):
        proc = self._make_processor(start=5.0, end=10.0)
        inp = make_input(self.mono)
        result = proc.process(inp)

        paras = result.metadata['deepgram']['results']['channels'][0]['alternatives'][0]['paragraphs']['paragraphs']
        # Only the customer paragraph (5.0–9.5) should survive
        self.assertEqual(len(paras), 1)
        self.assertEqual(paras[0]['speaker'], 1)

    # --- "last" parameter ---

    def test_last_n_seconds(self):
        # mono fixture has duration=15.5, so last=6 means start=9.5
        proc = self._make_processor(last=6.0)
        inp = make_input(self.mono)
        result = proc.process(inp)

        # Only the third paragraph (10.0–13.5) should survive
        paras = result.metadata['deepgram']['results']['channels'][0]['alternatives'][0]['paragraphs']['paragraphs']
        self.assertEqual(len(paras), 1)
        self.assertGreaterEqual(paras[0]['start'], 9.5)

    def test_last_without_duration_passes_through(self):
        data = copy.deepcopy(self.mono)
        del data['metadata']['duration']
        proc = self._make_processor(last=5.0)
        inp = make_input(data)
        result = proc.process(inp)

        # Should pass through unchanged
        self.assertEqual(
            len(result.metadata['deepgram']['results']['channels'][0]['alternatives'][0]['paragraphs']['paragraphs']),
            3,
        )

    # --- passthrough ---

    def test_passthrough_without_deepgram(self):
        proc = self._make_processor(end=60)
        inp = Score.Input(text="hello world", metadata={'other': 'data'})
        result = proc.process(inp)
        self.assertEqual(result.text, "hello world")
        self.assertEqual(result.metadata, {'other': 'data'})

    # --- does not mutate original ---

    def test_does_not_mutate_original(self):
        proc = self._make_processor(end=5.0)
        original = copy.deepcopy(self.mono)
        inp = make_input(self.mono)
        proc.process(inp)

        # Original fixture data should be unchanged
        self.assertEqual(
            len(self.mono['results']['channels'][0]['alternatives'][0]['paragraphs']['paragraphs']),
            3,
        )
        self.assertEqual(self.mono, original)

    # --- text regeneration ---

    def test_text_is_regenerated(self):
        proc = self._make_processor(end=5.0)
        inp = make_input(self.mono, text="original text")
        result = proc.process(inp)

        # Text should be regenerated, not "original text"
        self.assertNotEqual(result.text, "original text")
        self.assertIn("Hello", result.text)
        # Should not contain content from after 5.0s
        self.assertNotIn("trouble", result.text)

    # --- stereo filtering ---

    def test_stereo_time_slice(self):
        proc = self._make_processor(end=10.0)
        inp = make_input(self.stereo)
        result = proc.process(inp)

        # Channel 0: first paragraph (0.0–4.2) survives, second (12.0–15.4) does not
        ch0_paras = result.metadata['deepgram']['results']['channels'][0]['alternatives'][0]['paragraphs']['paragraphs']
        self.assertEqual(len(ch0_paras), 1)

        # Channel 1: first paragraph (5.0–9.8) survives, second (16.0) does not
        ch1_paras = result.metadata['deepgram']['results']['channels'][1]['alternatives'][0]['paragraphs']['paragraphs']
        self.assertEqual(len(ch1_paras), 1)

    # --- sentence-level filtering within paragraphs ---

    def test_sentence_level_filtering(self):
        """Time slice should filter individual sentences, not just whole paragraphs."""
        proc = self._make_processor(start=3.0, end=8.0)
        inp = make_input(self.mono)
        result = proc.process(inp)

        paras = result.metadata['deepgram']['results']['channels'][0]['alternatives'][0]['paragraphs']['paragraphs']
        # First paragraph originally has sentences at 0.0 and 3.0
        # Only the 3.0 sentence should survive
        first_para = paras[0]
        self.assertEqual(len(first_para['sentences']), 1)
        self.assertAlmostEqual(first_para['sentences'][0]['start'], 3.0)

        # Second paragraph has sentences at 5.0 and 8.0
        # Only the 5.0 sentence survives (8.0 is >= end)
        if len(paras) > 1:
            second_para = paras[1]
            for s in second_para['sentences']:
                self.assertLess(s['start'], 8.0)


# ---------------------------------------------------------------------------
# DeepgramFormatProcessor
# ---------------------------------------------------------------------------
class TestDeepgramFormatProcessor(unittest.TestCase):

    def setUp(self):
        self.mono = load_fixture('deepgram_simple_conversation.json')
        self.stereo = load_fixture('deepgram_stereo_conversation.json')

    def _make_processor(self, **params):
        from plexus.processors.DeepgramFormatProcessor import DeepgramFormatProcessor
        return DeepgramFormatProcessor(**params)

    # --- paragraphs format ---

    def test_paragraphs_default(self):
        proc = self._make_processor(format='paragraphs')
        result = proc.process(make_input(self.mono))

        # Should have paragraph text separated by blank lines
        self.assertIn('Hello, thank you for calling customer support.', result.text)
        self.assertIn("I'm having trouble", result.text)
        # Paragraphs separated by double newline
        self.assertIn('\n\n', result.text)

    def test_paragraphs_with_speaker_labels(self):
        proc = self._make_processor(format='paragraphs', speaker_labels=True)
        result = proc.process(make_input(self.mono))

        self.assertIn('Speaker 0:', result.text)
        self.assertIn('Speaker 1:', result.text)

    def test_paragraphs_with_timestamps(self):
        proc = self._make_processor(format='paragraphs', include_timestamps=True)
        result = proc.process(make_input(self.mono))

        self.assertIn('[0.00s]', result.text)
        self.assertIn('[5.00s]', result.text)

    # --- sentences format ---

    def test_sentences_format(self):
        proc = self._make_processor(format='sentences')
        result = proc.process(make_input(self.mono))

        lines = result.text.split('\n')
        # Should have individual sentences, one per line
        self.assertGreater(len(lines), 3)
        self.assertIn('Hello, thank you for calling customer support.', lines[0])
        self.assertIn('How can I help you today?', lines[1])

    def test_sentences_with_speaker_labels(self):
        proc = self._make_processor(format='sentences', speaker_labels=True)
        result = proc.process(make_input(self.mono))

        lines = result.text.split('\n')
        self.assertTrue(lines[0].startswith('Speaker 0:'))
        # Customer sentence
        customer_lines = [l for l in lines if l.startswith('Speaker 1:')]
        self.assertGreater(len(customer_lines), 0)

    def test_sentences_with_timestamps(self):
        proc = self._make_processor(format='sentences', include_timestamps=True)
        result = proc.process(make_input(self.mono))

        self.assertIn('[0.00s]', result.text)
        self.assertIn('[3.00s]', result.text)

    # --- words format ---

    def test_words_format(self):
        proc = self._make_processor(format='words')
        result = proc.process(make_input(self.mono))

        # Should be space-separated words
        self.assertTrue(result.text.startswith('Hello'))
        self.assertNotIn('\n', result.text)
        self.assertIn('login', result.text)

    def test_words_with_timestamps(self):
        proc = self._make_processor(format='words', include_timestamps=True)
        result = proc.process(make_input(self.mono))

        self.assertIn('Hello[0.00]', result.text)

    # --- channel filtering ---

    def test_channel_filter_mono(self):
        """In mono data, everything is channel 0. Filtering to channel 1 should give empty text."""
        proc = self._make_processor(format='paragraphs', channel=1)
        result = proc.process(make_input(self.mono))
        self.assertEqual(result.text, '')

    def test_channel_filter_stereo_channel_0(self):
        proc = self._make_processor(format='paragraphs', speaker_labels=True, channel=0)
        result = proc.process(make_input(self.stereo))

        # Should only have agent (speaker 0) content
        self.assertIn('ACME support', result.text)
        self.assertNotIn('trouble', result.text)

    def test_channel_filter_stereo_channel_1(self):
        proc = self._make_processor(format='paragraphs', speaker_labels=True, channel=1)
        result = proc.process(make_input(self.stereo))

        # Should only have customer (speaker 1) content
        self.assertIn('trouble', result.text)
        self.assertNotIn('ACME support', result.text)

    # --- multi-channel merging ---

    def test_stereo_merges_channels_by_time(self):
        proc = self._make_processor(format='paragraphs', speaker_labels=True)
        result = proc.process(make_input(self.stereo))

        # All content from both channels, merged by time
        self.assertIn('ACME support', result.text)
        self.assertIn('trouble', result.text)
        self.assertIn('thanks for helping', result.text)

        # Verify time ordering: agent greeting before customer complaint
        agent_pos = result.text.index('ACME support')
        customer_pos = result.text.index('trouble')
        self.assertLess(agent_pos, customer_pos)

    def test_stereo_words_merged(self):
        proc = self._make_processor(format='words')
        result = proc.process(make_input(self.stereo))

        words = result.text.split()
        # First word should be "Hello" (agent, 0.0s)
        self.assertEqual(words[0], 'Hello')
        # "Hi" (customer, 5.0s) should come after agent greeting
        hello_idx = words.index('Hello')
        hi_idx = words.index('Hi')
        self.assertLess(hello_idx, hi_idx)

    # --- passthrough ---

    def test_passthrough_without_deepgram(self):
        proc = self._make_processor(format='sentences')
        inp = Score.Input(text="original text", metadata={})
        result = proc.process(inp)
        self.assertEqual(result.text, "original text")

    # --- invalid format ---

    def test_invalid_format_raises(self):
        proc = self._make_processor(format='invalid')
        inp = make_input(self.mono)
        with self.assertRaises(ValueError):
            proc.process(inp)

    # --- metadata preserved ---

    def test_metadata_preserved(self):
        proc = self._make_processor(format='paragraphs')
        inp = Score.Input(
            text="x",
            metadata={'deepgram': self.mono, 'other_key': 'preserved'},
        )
        result = proc.process(inp)
        self.assertEqual(result.metadata['other_key'], 'preserved')
        self.assertIs(result.metadata['deepgram'], self.mono)


# ---------------------------------------------------------------------------
# Pipeline integration: TimeSlice -> Format
# ---------------------------------------------------------------------------
class TestProcessorPipeline(unittest.TestCase):

    def setUp(self):
        self.mono = load_fixture('deepgram_simple_conversation.json')
        self.stereo = load_fixture('deepgram_stereo_conversation.json')

    def test_time_slice_then_format(self):
        from plexus.processors.DeepgramTimeSliceProcessor import DeepgramTimeSliceProcessor
        from plexus.processors.DeepgramFormatProcessor import DeepgramFormatProcessor

        # Slice to first 5 seconds, then format as sentences with speaker labels
        slicer = DeepgramTimeSliceProcessor(end=5.0)
        formatter = DeepgramFormatProcessor(format='sentences', speaker_labels=True)

        inp = make_input(self.mono)
        sliced = slicer.process(inp)
        result = formatter.process(sliced)

        # Should only have sentences from first 5 seconds
        self.assertIn('Speaker 0:', result.text)
        self.assertNotIn('Speaker 1:', result.text)
        self.assertIn('Hello, thank you for calling customer support.', result.text)
        self.assertNotIn('trouble', result.text)

    def test_time_slice_then_format_stereo(self):
        from plexus.processors.DeepgramTimeSliceProcessor import DeepgramTimeSliceProcessor
        from plexus.processors.DeepgramFormatProcessor import DeepgramFormatProcessor

        # Slice to 0-10s, format as sentences, customer channel only
        slicer = DeepgramTimeSliceProcessor(end=10.0)
        formatter = DeepgramFormatProcessor(
            format='sentences', speaker_labels=True, channel=1
        )

        inp = make_input(self.stereo)
        sliced = slicer.process(inp)
        result = formatter.process(sliced)

        # Should have customer content from first 10 seconds only
        self.assertIn('trouble', result.text)
        self.assertNotIn('thanks for helping', result.text)  # 16.0s, excluded by slicer
        self.assertNotIn('ACME', result.text)  # channel 0, excluded by formatter


if __name__ == '__main__':
    unittest.main()
