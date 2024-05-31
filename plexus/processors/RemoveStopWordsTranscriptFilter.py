import nltk
from nltk.corpus import stopwords
from plexus.processors.TranscriptFilter import TranscriptFilter

class RemoveStopWordsTranscriptFilter(TranscriptFilter):

    def __init__(self):
        nltk.download('stopwords')
        self.stop_words = set(stopwords.words('english'))

    def process(self, *, transcript):
        words = transcript.split()
        filtered_words = [word for word in words if word.lower() not in self.stop_words]
        return ' '.join(filtered_words)