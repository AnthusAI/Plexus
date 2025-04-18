from typing import Dict, Any, Optional, Type, ClassVar
import nltk
from types import FunctionType
import pydantic
from pydantic import Field
from nltk.tokenize import PunktSentenceTokenizer
from rapidfuzz import fuzz, process
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import BaseOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END
from plexus.scores.nodes.BaseNode import BaseNode
from plexus.CustomLogging import logging
from plexus.LangChainUser import LangChainUser

class BeforeAfterSlicer(BaseNode, LangChainUser):
    """
    A node that slices text input into 'before' and 'after' based on the provided prompt.
    """

    def __init__(self, **parameters):
        LangChainUser.__init__(self, **parameters)
        # We intentionally override super().__init__() to allow for a carefully-crafted Pydantic model here.
        combined_parameters_model = pydantic.create_model(
            "CombinedParameters",
            __base__=(BeforeAfterSlicer.Parameters, LangChainUser.Parameters))
        self.parameters = combined_parameters_model(**parameters)
        self.openai_callback = None
        self.model = self._initialize_model()

    class GraphState(BaseNode.GraphState):
        before: Optional[str]
        after: Optional[str]

    class SlicingOutputParser(BaseOutputParser[dict]):
        FUZZY_MATCH_SCORE_CUTOFF: ClassVar[int] = 70
        text: str = Field(...)
        __tokenizer: Optional[PunktSentenceTokenizer] = None

        class Config:
            arbitrary_types_allowed = True
            underscore_attrs_are_private = True

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            # Add debug logging
            logging.info(f"NLTK data path: {nltk.data.path}")
            try:
                nltk.data.find('tokenizers/punkt/english.pickle')
                logging.info("Found punkt tokenizer data")
            except LookupError as e:
                logging.error(f"Could not find punkt tokenizer data: {e}")
                # Try downloading with verbose output
                nltk.download('punkt', quiet=False)
            self._initialize_tokenizer()

        def _initialize_tokenizer(self) -> None:
            if self.__tokenizer is None:
                self.__tokenizer = PunktSentenceTokenizer()

        def tokenize(self, text: str) -> list[str]:
            self._initialize_tokenizer()
            return self.__tokenizer.tokenize(text)

        @property
        def _type(self) -> str:
            return "custom_output_parser"
        
        def parse(self, output: str) -> Dict[str, Any]:
            # Remove any leading/trailing whitespace and quotes
            output = output.strip().strip('"')
            
            # Remove the prefix if it exists
            prefix = "Quote:"
            if output.startswith(prefix):
                output = output[len(prefix):].strip()
            
            output = output.strip('"\'')
            
            logging.info(f"Cleaned output: {output}")
            
            # Tokenize the text into sentences using our initialized tokenizer
            sentences = self.tokenize(self.text)
            
            # Use RapidFuzz to find the best match among sentences
            result = process.extractOne(
                output,
                sentences,
                scorer=fuzz.partial_ratio,
                score_cutoff=self.FUZZY_MATCH_SCORE_CUTOFF
            )
            
            if result:
                match, score, index = result
                logging.info(f"Best match found with score {score} at sentence index {index}")
                start_index = self.text.index(match)
                input_text_after_slice = self.text[start_index:]
                input_text_before_slice = self.text[:start_index]
            else:
                logging.warning(f"No exact match found for output: '{output}'. Using the entire remaining text.")
                input_text_after_slice = self.text
                input_text_before_slice = ""

            logging.info(f"Length of input_text_before_slice: {len(input_text_before_slice)}")
            logging.info(f"First 100 characters of input_text_before_slice: {input_text_before_slice[:100]}")
            logging.info(f"Length of input_text_after_slice: {len(input_text_after_slice)}")
            logging.info(f"First 100 characters of input_text_after_slice: {input_text_after_slice[:100]}")

            return {
                "before": input_text_before_slice,
                "after": input_text_after_slice
            }

    def get_slicer_node(self) -> FunctionType:
        model = self.model

        def slicer_node(state):
            prompts = self.get_prompt_templates()
            # Assuming the first prompt in the list is the one we want to use
            prompt = prompts[0] if isinstance(prompts, list) else prompts
            
            # Ensure prompt is a ChatPromptTemplate
            if not isinstance(prompt, ChatPromptTemplate):
                prompt = ChatPromptTemplate.from_template(prompt)
            
            chain = prompt | model | self.SlicingOutputParser(**state.dict())
            return chain.invoke({**state.dict()})

        return slicer_node

    def add_core_nodes(self, workflow: StateGraph) -> StateGraph:
        workflow.add_node("slicer", self.get_slicer_node())
        return workflow