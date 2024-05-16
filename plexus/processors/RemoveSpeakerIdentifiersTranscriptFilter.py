import re
from plexus.processors.TranscriptFilter import TranscriptFilter

class RemoveSpeakerIdentifiersTranscriptFilter(TranscriptFilter):

    def process(self, *, transcript):
        return re.sub(r'^\w+:\s*', '', transcript, flags=re.MULTILINE)
