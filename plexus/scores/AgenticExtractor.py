from plexus.scores.Score import Score
from plexus.CustomLogging import logging
import pandas as pd
from langchain_aws import ChatBedrock
from langchain_openai import AzureChatOpenAI
from langchain_google_vertexai import ChatVertexAI
from langchain.chains import create_history_aware_retriever, create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from typing import Dict, Any
from langchain.retrievers import TFIDFRetriever
from langchain.schema import Document

class AgenticExtractor(Score):
    def __init__(self, scorecard_name, score_name, model, data, prompt, **kwargs):
        super().__init__(scorecard_name=scorecard_name, score_name=score_name, **kwargs)
        self.scorecard_name = scorecard_name
        self.score_name = score_name
        self.llm = self._initialize_model(model)
        self.data = data
        self.prompt = prompt
        self.processors = self._initialize_processors(data.get('processors', []))
        self.conversation_history = {}
        self.context = self.data.get('context', '')
        self.rag_chain = None  # Initialize to None, we'll set it up later

    def _initialize_model(self, model_name):
        # Initialize the specified LLM model
        if model_name == "AzureChatOpenAI":
            return AzureChatOpenAI()
        elif model_name == "BedrockChat":
            return ChatBedrock(
                model_id="anthropic.claude-3-haiku-20240307-v1:0",
                model_kwargs={"temperature": 0.1},
            )
        elif model_name == "ChatVertexAI":
            return ChatVertexAI(
                model="gemini-1.5-flash-001",
                temperature=0,
                max_tokens=None,
                max_retries=6,
                stop=None,
            )
        else:
            raise ValueError(f"Unsupported model: {model_name}")

    def _initialize_processors(self, processor_configs):
        # Initialize processors based on configuration
        processors = []
        for config in processor_configs:
            if config['class'] == 'KeywordClassifier':
                from plexus.scores.KeywordClassifier import KeywordClassifier
                processors.append(KeywordClassifier(
                    keywords=config['keywords'],
                    scorecard_name=self.scorecard_name,
                    score_name=self.score_name
                ))
        return processors

    def load_context(self, transcript=None):
        if transcript:
            self.context = f"{self.context}\n\nTranscript: {transcript}"
        self._initialize_retriever()  # Reinitialize the retriever with the new context
        self.rag_chain = self._initialize_rag_chain()  # Reinitialize the RAG chain
        logging.info(f"Loaded context: {self.context}")

    def _initialize_retriever(self):
        # Create a simple retriever using the context
        if self.context:
            documents = [Document(page_content=self.context, metadata={"source": "context"})]
            logging.info(f"Documents: {documents}")
            return TFIDFRetriever.from_documents(documents)
        else:
            # If no context is provided, return a dummy retriever that always returns an empty list
            return lambda _: []

    def _initialize_rag_chain(self):
        # Initialize retriever
        retriever = self._initialize_retriever()

        # Contextualize question
        contextualize_q_prompt = ChatPromptTemplate.from_messages([
            ("system", "Given a chat history and the latest user question which might reference context in the chat history, formulate a standalone question which can be understood without the chat history. Do NOT answer the question, just reformulate it if needed and otherwise return it as is."),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
        ])
        history_aware_retriever = create_history_aware_retriever(self.llm, retriever, contextualize_q_prompt)

        # Answer question
        qa_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are an assistant for question-answering tasks. Use the following context to answer the question. If you don't know the answer, just say that you don't know. Use three sentences maximum and keep the answer concise.\n\nContext: {context}"),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
        ])
        question_answer_chain = create_stuff_documents_chain(self.llm, qa_prompt)

        return create_retrieval_chain(history_aware_retriever, question_answer_chain)

    def _get_session_history(self, session_id: str) -> ChatMessageHistory:
        if session_id not in self.conversation_history:
            self.conversation_history[session_id] = ChatMessageHistory()
        return self.conversation_history[session_id]

    def predict(self, model_input):
        if isinstance(model_input, pd.DataFrame) and 'Transcription' in model_input.columns:
            transcript = model_input['Transcription'].iloc[0]
            logging.info(f"Transcript: {transcript}")
            self.load_context(transcript)  # Load the transcript into the context
            return self.process_transcript(transcript)
        else:
            logging.error(f"Invalid input type: {type(model_input)}")
            return None

    def process_transcript(self, transcript):
        relevant_text = transcript
        if self.processors:
            relevant_sentences = [sent for sent in transcript.split('.') if any(p.is_relevant(sent) for p in self.processors)]
            relevant_text = '. '.join(relevant_sentences)

        questions = [task['detect'] if 'detect' in task else task['extract'] for task in self.prompt]
        
        conversational_rag_chain = RunnableWithMessageHistory(
            self.rag_chain,
            self._get_session_history,
            input_messages_key="input",
            history_messages_key="chat_history",
            output_messages_key="answer",
        )

        results = {}
        for question in questions:
            response = conversational_rag_chain.invoke(
                {
                    "input": question,
                    "chat_history": self._get_session_history(self.score_name).messages
                },
                config={"configurable": {"session_id": self.score_name}}
            )
            results[question] = response['answer']

        logging.info(f"Agent results: {results}")
        return results
