import unittest

from plexus.processors.RemoveSpeakerIdentifiersTranscriptFilter import (
    RemoveSpeakerIdentifiersTranscriptFilter,
)
from plexus.scores.Score import Score


def _process_text(text: str) -> str:
    processor = RemoveSpeakerIdentifiersTranscriptFilter()
    score_input = Score.Input(text=text, metadata={})
    result = processor.process(score_input)
    return result.text


class TestRemoveSpeakerIdentifiersTranscriptFilter(unittest.TestCase):
    def test_removes_deepgram_speaker_number_labels(self):
        text = (
            "Speaker 0: felicia Speaker 1: who Speaker 0: hi "
            "Speaker 0: felicia Speaker 0: this Speaker 0: is Speaker 0: miss"
        )

        result = _process_text(text)

        self.assertEqual(result, "felicia who hi felicia this is miss")
        self.assertNotIn("Speaker", result)
        self.assertNotIn("0:", result)
        self.assertNotIn("1:", result)

    def test_removes_generic_speaker_labels_without_ids(self):
        text = (
            "Speaker: hello Speaker: hello Speaker: tasha "
            "Speaker: yes Speaker: tasha Speaker: yes Speaker: hey"
        )

        result = _process_text(text)

        self.assertEqual(result, "hello hello tasha yes tasha yes hey")
        self.assertNotIn("Speaker ", result)

    def test_removes_agent_and_customer_labels(self):
        text = "Agent: Hello. Customer: Hi there. Representative: How can I help?"

        result = _process_text(text)

        self.assertEqual(result, "Hello. Hi there. How can I help?")
        self.assertNotIn("Agent:", result)
        self.assertNotIn("Customer:", result)
        self.assertNotIn("Representative:", result)


if __name__ == "__main__":
    unittest.main()
