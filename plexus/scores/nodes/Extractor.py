from typing import Dict, Any, Optional
import nltk
from types import FunctionType
import pydantic
from pydantic import Field
from nltk.tokenize import sent_tokenize
from rapidfuzz import fuzz, process
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import BaseOutputParser
from langgraph.graph import StateGraph
from plexus.scores.nodes.BaseNode import BaseNode
from plexus.CustomLogging import logging
from plexus.LangChainUser import LangChainUser

class Extractor(BaseNode, LangChainUser):
    """
    A node that extracts a chunk from the transcript based on prompt instructions using rapidfuzz.
    """

    def __init__(self, **parameters):
        LangChainUser.__init__(self, **parameters)
        combined_parameters_model = pydantic.create_model(
            "CombinedParameters",
            __base__=(Extractor.Parameters, LangChainUser.Parameters))
        self.parameters = combined_parameters_model(**parameters)
        self.model = self._initialize_model()

    class GraphState(BaseNode.GraphState):
        extracted: Optional[str] = None

    class Parameters(BaseNode.Parameters, LangChainUser.Parameters):
        similarity_threshold: float = Field(default=70.0, description="Minimum similarity score to consider a match")

    class ExtractionOutputParser(BaseOutputParser[dict]):
        FUZZY_MATCH_SCORE_CUTOFF: float = Field(default=70.0)
        text: str = Field(...)

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            nltk.download('punkt', quiet=True)

        @property
        def _type(self) -> str:
            return "extraction_output_parser"
        
        def parse(self, output: str) -> Dict[str, Any]:
            output = output.strip().strip('"')
            
            logging.info(f"Cleaned output: {output}")
            
            sentences = sent_tokenize(self.text)
            
            result = process.extractOne(
                output,
                sentences,
                scorer=fuzz.partial_ratio,
                score_cutoff=self.FUZZY_MATCH_SCORE_CUTOFF
            )
            
            if result:
                match, score, index = result
                logging.info(f"Best match found with score {score} at sentence index {index}")
                extracted_text = match
            else:
                logging.warning(f"No match found for output: '{output}'. Returning None.")
                extracted_text = None

            logging.info(f"Extracted text: {extracted_text}")

            return {"extracted": extracted_text}

    def get_extractor_node(self) -> FunctionType:
        model = self.model

        def extractor_node(state):
            prompts = self.get_prompt_templates()
            prompt = prompts[0] if isinstance(prompts, list) else prompts
            
            if not isinstance(prompt, ChatPromptTemplate):
                prompt = ChatPromptTemplate.from_template(prompt)
            
            chain = prompt | model | self.ExtractionOutputParser(
                text=state.text,
                FUZZY_MATCH_SCORE_CUTOFF=self.parameters.similarity_threshold
            )

            # Create a dictionary from the state and add retry_feedback
            state_dict = state.dict()

            result = chain.invoke(state_dict)
            return {**state.dict(), **result}

        return extractor_node

    def add_core_nodes(self, workflow: StateGraph) -> StateGraph:
        workflow.add_node("extract", self.get_extractor_node())
        return workflow
