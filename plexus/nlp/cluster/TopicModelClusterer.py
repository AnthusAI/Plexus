import os
import numpy as np
from gensim import corpora
from gensim.models import LdaMulticore, CoherenceModel
from gensim.parsing.preprocessing import STOPWORDS
from gensim.utils import simple_preprocess
from tqdm.auto import tqdm
from typing import List, Tuple
import openai

class TopicModelClusterer:
    def __init__(self, explanations: List[str]):
        self.explanations = explanations
        self.processed_docs = self._preprocess_documents(explanations)
        self.dictionary = self._create_dictionary()
        self.corpus = self._create_corpus()
        self.optimal_model = None
        self.optimal_num_topics = None
        self.topic_counts = None
        self.prominent_topics = None
        self.llm_explanations = {}
        self.summary = ""
        openai.api_key = os.environ.get("OPENAI_API_KEY")

    def _preprocess_documents(self, documents: List[str]) -> List[List[str]]:
        return [[word for word in simple_preprocess(doc) if word not in STOPWORDS] for doc in documents]

    def _create_dictionary(self) -> corpora.Dictionary:
        return corpora.Dictionary(self.processed_docs)

    def _create_corpus(self) -> List[List[Tuple[int, int]]]:
        return [self.dictionary.doc2bow(doc) for doc in self.processed_docs]

    def _compute_coherence_values(self, limit: int, start: int = 2, step: int = 3) -> Tuple[List[LdaMulticore], List[float]]:
        coherence_values = []
        model_list = []
        for num_topics in tqdm(range(start, limit, step)):
            try:
                model = LdaMulticore(corpus=self.corpus, id2word=self.dictionary, num_topics=num_topics, random_state=100)
                model_list.append(model)
                # Explicitly call get_topics() here
                topics = model.get_topics()
                coherence_model = CoherenceModel(topics=topics, texts=self.processed_docs, dictionary=self.dictionary, coherence='c_v')
                coherence_values.append(coherence_model.get_coherence())
            except Exception as e:
                print(f"Error computing coherence for {num_topics} topics: {str(e)}")
                coherence_values.append(0.0)  # Append a default value
        
        return model_list, coherence_values

    def determine_optimal_topics(self, limit: int = 50, start: int = 5, step: int = 5):
        model_list, coherence_values = self._compute_coherence_values(limit=limit, start=start, step=step)
        if coherence_values:
            self.optimal_model = model_list[np.argmax(coherence_values)]
            self.optimal_coherence = max(coherence_values)
            self.optimal_num_topics = start + step * np.argmax(coherence_values)
        else:
            print("No coherence values were computed.")
        return coherence_values

    def analyze_topic_distributions(self):
        if not self.optimal_model:
            raise ValueError("Optimal model not determined. Call determine_optimal_topics first.")
        topic_distributions = [self.optimal_model.get_document_topics(doc) for doc in self.corpus]
        topic_prominence = [max(dist, key=lambda x: x[1])[0] for dist in topic_distributions]
        self.topic_counts = np.bincount(topic_prominence, minlength=self.optimal_model.num_topics)
        self.prominent_topics = [
            (idx, topic) for idx, topic in enumerate(self.optimal_model.print_topics(-1)) if self.topic_counts[idx] > 1
        ]

    def get_lda_topics(self) -> List[Tuple[int, str]]:
        if not self.prominent_topics:
            raise ValueError("Topic distributions not analyzed. Call analyze_topic_distributions first.")
        return self.prominent_topics

    def _get_top_words(self, topic, n: int = 10) -> str:
        return ", ".join([word for word, _ in topic[:n]])

    def _get_explanation(self, topic_words: str) -> str:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": f"Given the following words representing a topic in call center QA for qualified buyers: {topic_words}\n\nProvide a concise one-sentence explanation of what this topic represents in the context of AI vs. human evaluation mismatches:"
                }
            ]
        )
        return response.choices[0].message['content']

    def generate_llm_explanations(self):
        if not self.prominent_topics:
            raise ValueError("Prominent topics not available. Call analyze_topic_distributions first.")
        for idx, topic in self.prominent_topics:
            top_words = self._get_top_words(self.optimal_model.show_topic(idx, topn=10))
            explanation = self._get_explanation(top_words)
            self.llm_explanations[idx] = {"top_words": top_words, "explanation": explanation, "prominence": self.topic_counts[idx]}

    def get_llm_explanations(self) -> dict:
        if not self.llm_explanations:
            raise ValueError("LLM explanations not generated. Call generate_llm_explanations first.")
        return self.llm_explanations

    def generate_summary(self):
        if not self.optimal_num_topics:
            raise ValueError("Optimal number of topics not determined. Call determine_optimal_topics first.")
        prompt = (
            f"I have analyzed {len(self.explanations)} explanations of mismatches between AI and human evaluations in call center QA for qualified buyers. "
            f"The analysis revealed {self.optimal_num_topics} main topics. "
            "Please provide a brief summary of what this might indicate about the nature of AI vs. human evaluation mismatches in this context."
        )
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        self.summary = response.choices[0].message['content']

    def get_summary(self) -> str:
        if not self.summary:
            raise ValueError("Summary not generated. Call generate_summary first.")
        return self.summary