from typing import Dict, Optional, Any, Callable
import pydantic
from pydantic import Field
from langgraph.graph import StateGraph, END
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import BaseOutputParser
from plexus.LangChainUser import LangChainUser
from plexus.scores.nodes.BaseNode import BaseNode
from plexus.CustomLogging import logging
from rapidfuzz import fuzz, process
import nltk
from nltk.tokenize import sent_tokenize

class ContextExtractor(BaseNode, LangChainUser):
    """
    A node that extracts text chunks with configurable context windows around a matched sequence.
    """
    
    class Parameters(BaseNode.Parameters):
        system_message: str
        user_message: str
        context_before: int = Field(
            default=100,
            description="Number of characters to include before the matched sequence"
        )
        context_after: int = Field(
            default=100,
            description="Number of characters to include after the matched sequence"
        )
        use_sentence_boundaries: bool = Field(
            default=True,
            description="Whether to expand context to complete sentences"
        )
        fuzzy_match_threshold: int = Field(
            default=70,
            description="Threshold for fuzzy matching (0-100)"
        )

    def __init__(self, **parameters):
        super().__init__(**parameters)
        self.model = self._initialize_model()
        if self.parameters.use_sentence_boundaries:
            nltk.download('punkt', quiet=True)

    class GraphState(BaseNode.GraphState):
        matched_sequence: Optional[str] = None
        context_chunk: Optional[str] = None
        match_start_index: Optional[int] = None
        match_end_index: Optional[int] = None

    class ExtractionOutputParser(BaseOutputParser[dict]):
        """Parser that extracts the target sequence and adds surrounding context."""
        
        FUZZY_MATCH_THRESHOLD: int = Field(...)
        text: str = Field(...)
        context_before: int = Field(...)
        context_after: int = Field(...)
        use_sentence_boundaries: bool = Field(...)

        def parse(self, output: str) -> Dict[str, Any]:
            # Clean the output
            output = output.strip().strip('"')
            if output.startswith("Quote:"):
                output = output[len("Quote:"):].strip()
            output = output.strip('"\'')
            
            logging.info(f"Searching for sequence: {output}")
            
            # Handle "No clear example found" case
            if "no clear example" in output.lower():
                return {
                    "matched_sequence": None,
                    "context_chunk": None,
                    "match_start_index": None,
                    "match_end_index": None
                }
            
            # Use fuzzy matching to find the best match in the text
            # Create overlapping chunks for better matching
            chunk_size = len(output)
            overlap = chunk_size // 2
            text_chunks = []
            for i in range(0, len(self.text) - chunk_size + 1, overlap):
                text_chunks.append(self.text[i:i + chunk_size])

            # Normalize the output for comparison
            normalized_output = ' '.join(output.lower().split())
            
            # Find best matching chunk
            result = process.extractOne(
                normalized_output,
                text_chunks,
                scorer=fuzz.token_sort_ratio,
                score_cutoff=self.FUZZY_MATCH_THRESHOLD
            )
            
            if not result:
                logging.warning(f"No match found for: {output}")
                return {
                    "matched_sequence": None,
                    "context_chunk": None,
                    "match_start_index": None,
                    "match_end_index": None
                }
            
            # Get the matched chunk and its index
            matched_chunk, match_score, chunk_index = result
            chunk_start = chunk_index * overlap
            
            # Use the chunk start position directly
            match_start = chunk_start
            matched_sequence = matched_chunk
            
            # Calculate the end position
            match_end = match_start + len(matched_sequence)
            
            # Calculate initial context boundaries
            context_start = max(0, match_start - self.context_before)
            context_end = min(len(self.text), match_end + self.context_after)
            
            if self.use_sentence_boundaries:
                # Tokenize the relevant portion of text into sentences
                sentences = sent_tokenize(self.text)
                
                # Find sentences that contain our boundaries
                current_pos = 0
                for i, sentence in enumerate(sentences):
                    sentence_start = current_pos
                    sentence_end = current_pos + len(sentence)
                    
                    # Expand context_start to sentence boundary
                    if sentence_start <= context_start <= sentence_end:
                        context_start = sentence_start
                    
                    # Expand context_end to sentence boundary
                    if sentence_start <= context_end <= sentence_end:
                        context_end = sentence_end
                    
                    current_pos = sentence_end + 1
            
            context_chunk = self.text[context_start:context_end]
            
            logging.info(f"Extracted context chunk of length {len(context_chunk)}")
            logging.info(f"Match found at positions {match_start}:{match_end}")
            
            # Ensure the context chunk contains the matched sequence
            if matched_sequence not in context_chunk:
                logging.warning("Matched sequence not found in context chunk, adjusting boundaries")
                context_start = max(0, match_start - self.context_before)
                context_end = min(len(self.text), match_end + self.context_after)
                context_chunk = self.text[context_start:context_end]
            
            return {
                "explanation": output,
                "matched_sequence": matched_sequence,
                "context_chunk": context_chunk,
                "match_start_index": match_start,
                "match_end_index": match_end
            }

    def get_extractor_node(self) -> Callable:
        model = self.model
        prompts = self.get_prompt_templates()

        def extractor_node(state):
            if not state.text:
                logging.warning("Text is empty in extractor node")
                return state

            # Convert state to dict if it isn't already
            if not isinstance(state, dict):
                state = state.dict()

            prompt = prompts[0]
            
            chain = prompt | model | self.ExtractionOutputParser(
                FUZZY_MATCH_THRESHOLD=self.parameters.fuzzy_match_threshold,
                text=state["text"],
                context_before=self.parameters.context_before,
                context_after=self.parameters.context_after,
                use_sentence_boundaries=self.parameters.use_sentence_boundaries
            )
            
            result = chain.invoke(state)
            logging.info(f"Extraction result: {result}")
            
            return {
                **state,
                "explanation": result.get("explanation", ""),
                "matched_sequence": result.get("matched_sequence", ""),
                "context_chunk": result.get("context_chunk", ""),
                "match_start_index": result.get("match_start_index"),
                "match_end_index": result.get("match_end_index")
            }

        return extractor_node

    def add_core_nodes(self, workflow: StateGraph) -> StateGraph:
        workflow.add_node("extract_with_context", self.get_extractor_node())
        return workflow 