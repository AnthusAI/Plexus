import os
import random
import logging
from openai import OpenAI
import tiktoken

class LLMGenerator:
    def __init__(self):
        
        self.model_name = "gpt-4-0125-preview"
        self.maximum_line_count = 10

        self.client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        self.relevant_history = []
        self.irrelevant_history = []
        logging.basicConfig(level=logging.INFO)

    def generate_data(self, context, relevant_examples, irrelevant_examples, filename='generated_data.txt', sample_count=100):
        # Count the existing samples in the file
        existing_sample_count = self._count_existing_samples(filename)
        
        # Calculate the number of new samples needed
        samples_to_generate = sample_count - existing_sample_count
        
        # If the target number of samples is already met or exceeded, do nothing
        if samples_to_generate <= 0:
            logging.info("Target number of samples already reached. No new samples needed.")
            return
        
        # Generate only the remaining samples needed
        with open(filename, 'a', encoding='utf-8') as file:
            for i in range(samples_to_generate):
                # Generate relevant samples
                relevant_context = self._format_context(context, relevant_examples, relevant=True)
                relevant_texts = self._generate_sample(relevant_context)
                for relevant_text in relevant_texts.split('\n'):
                    self._write_sample(file, "relevant", relevant_text)
                    self.relevant_history.append(relevant_text)

                # Generate irrelevant samples
                irrelevant_context = self._format_context(context, irrelevant_examples, relevant=False)
                irrelevant_texts = self._generate_sample(irrelevant_context)
                for irrelevant_text in irrelevant_texts.split('\n'):
                    self._write_sample(file, "irrelevant", irrelevant_text)
                    self.irrelevant_history.append(irrelevant_text)

    def _count_existing_samples(self, filename):
        try:
            with open(filename, 'r', encoding='utf-8') as file:
                return sum(1 for line in file if line.strip())
        except FileNotFoundError:
            # If the file does not exist, return 0
            return 0

    def _format_context(self, context, examples, relevant):

        # Randomly select examples and shuffle the order.
        sentences = examples.split('\n')
        selected_sentences = random.sample([s for s in sentences if s], 10)
        random.shuffle(selected_sentences)
        random_examples = '\n'.join(selected_sentences)

        prompt_type = "be relevant" if relevant else "NOT be relevant"

        context_prompt = (
            f"\n\nProvide an imaginary new example of a sentence that would {prompt_type} to these words and concepts:\n\n"
            f"\"\"\"\n{context}\n\"\"\"\n\n"
        )

        prompt = (
            "You're part of a system for synthesizing sentences as training data for a text classification model.\n"
            "Your task is to provide diverse examples of utterances with a lot of variety in the concepts they cover.\n"
            "Many utterances will be complete sentences, but not all.  Note from the examples that some are just words or exclamations or interjections or sentence fragments.\n"
            "Give me 20 of those at a time.  Each utterance should be on a separate line, and each should be all on one line.\n"
            "Don't introduce the utterances in any way, just list them.\n"
            "Don't include any blank lines between utterances.  Don't include any extra spaces at the beginning or end of the sentence.\n"
            "Do not include anything other than the actual utterance.  No headers, item numbers, prefixes, line numbers or quotes or anything extra.\n"
            "Do not wrap one utterance across more than one line.  Give me the entire utterance, don't truncate anything with \"...\"\n"
            "Use a variety of sentence structures and verb forms.  There should be some questions, exclamations, etc, and not just statements.\n"
            "Only about a quarter of the utterances should be questions.  The rest should be statements, interjections, sentence fragments, etc.\n"
            "Most of the utterances should not be questions.  Include sentence fragments and incomplete sentences.  Simulate what will be included in a call transcript.\n"
            "Mimic the lengths of the sentences in the examples.  Vary the lengths.  Some sentences should be very short and some should be long, like in the examples.\n"
            "The sentences are extracted from transcripts of phone calls between a call center agent and a customer, so stay in that theme.\n"
            f"{context_prompt}"
            f"Here are some examples:\n\n"
            f"\"\"\"\n{random_examples}\n\"\"\"\n\n"
            "Try to generate sentences and questions similar to the examples.\n\n"
            "This is a history of the synthetic samples so far.  Don't repeat the same concepts.  Try to cover a wide range of concepts.\n"
        )
        # Compute the history context considering the current prompt
        history_context = self._compute_history_context(relevant)
        combined_prompt = f"{prompt}\n{history_context}"
        logging.info(f"\n+---\nCombined prompt:\n{combined_prompt[:10000]}...\n+---\n")  # Log the beginning of the prompt for brevity
        return combined_prompt

    def _compute_history_context(self, relevant):
        history = self.relevant_history if relevant else self.irrelevant_history
        selected_history = (history if len(history) < self.maximum_line_count 
                            else random.sample(history, self.maximum_line_count))
        random.shuffle(selected_history)
        return "\n".join(selected_history).strip()

    def _generate_sample(self, context):
        logging.info(f"Generating sample with context: {context[:50]}...")  # Log the beginning of the context for brevity
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": context}],
            max_tokens=1000,
            temperature=1
        )
        generated_text = response.choices[0].message.content.strip()
        logging.info(f"Generated text: {generated_text}")  # Log the generated text
        return generated_text

    def _write_sample(self, file, label, text):
        file.write(f"__label__{label} {text}\n")
        file.flush()

    def _count_tokens(self, text):
        encoding = tiktoken.encoding_for_model(self.model_name)
        num_tokens = len(encoding.encode(text))
        return num_tokens