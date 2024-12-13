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
from plexus.LangChainUser import LangChainUser
from plexus.CustomLogging import logging
from concurrent.futures import ThreadPoolExecutor
import time

class Extractor(BaseNode, LangChainUser):
    """
    A node that extracts a specific quote from the input text based on the provided prompt.
    """

    def __init__(self, **parameters):
        LangChainUser.__init__(self, **parameters)
        combined_parameters_model = pydantic.create_model(
            "CombinedParameters",
            __base__=(Extractor.Parameters, LangChainUser.Parameters))
        self.parameters = combined_parameters_model(**parameters)
        self.model = self._initialize_model()

    class GraphState(BaseNode.GraphState):
        extracted_text: Optional[str] = None

    class Parameters(BaseNode.Parameters):
        fuzzy_match_score_cutoff: int = Field(default=50, description="Cutoff score for fuzzy matching")
        use_exact_matching: bool = Field(default=False, description="Use exact matching instead of sliding window approach")

    class ExtractionOutputParser(BaseOutputParser[dict]):
        FUZZY_MATCH_SCORE_CUTOFF: int = Field(...)
        text: str = Field(...)
        use_exact_matching: bool = Field(default=False)

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            nltk.download('punkt', quiet=True)  # Download the punkt tokenizer data

        @property
        def _type(self) -> str:
            return "custom_output_parser"

        def parse(self, output: str) -> Dict[str, Any]:
            output = output.strip().strip('"')
            
            prefix = "Quote:"
            if output.startswith(prefix):
                output = output[len(prefix):].strip()
            
            output = output.strip('"\'')
            
            logging.info(f"Cleaned output: {output}")
            
            if "No clear example" in output:
                return {"extracted_text": output}

            if self.use_exact_matching:
                # Exact matching approach
                if output in self.text:
                    return {"extracted_text": output}
                    
                result = process.extractOne(
                    output,
                    [self.text],
                    scorer=fuzz.partial_ratio,
                    score_cutoff=self.FUZZY_MATCH_SCORE_CUTOFF
                )
                
                if result:
                    _, score, _ = result
                    if score >= self.FUZZY_MATCH_SCORE_CUTOFF:
                        extracted_text = output
                    else:
                        logging.warning(f"Low confidence match (score: {score}). Using original output.")
                        extracted_text = output
                else:
                    logging.warning("No match found. Using original output.")
                    extracted_text = output
            else:
                # Sliding window approach (default)
                window_size = len(output.split())
                best_match = None
                best_score = 0
                
                for i in range(len(self.text) - window_size + 1):
                    window = self.text[i:i+len(output)]
                    score = fuzz.ratio(output, window)
                    if score > best_score:
                        best_score = score
                        best_match = window

                if best_match and best_score >= self.FUZZY_MATCH_SCORE_CUTOFF:
                    logging.info(f"Best match found with score {best_score}")
                    extracted_text = best_match
                else:
                    logging.warning(f"No match found for output: '{output}'. Using the entire output.")
                    extracted_text = output

            logging.info(f"Extracted text: {extracted_text}")
            return {"extracted_text": extracted_text}

    def get_extractor_node(self) -> FunctionType:
        model = self.model

        def extractor_node(state):
            prompts = self.get_prompt_templates()
            prompt = prompts[0] if isinstance(prompts, list) else prompts
            
            if not isinstance(prompt, ChatPromptTemplate):
                prompt = ChatPromptTemplate.from_template(prompt)
            
            chain = prompt | model | self.ExtractionOutputParser(
                FUZZY_MATCH_SCORE_CUTOFF=self.parameters.fuzzy_match_score_cutoff,
                text=state.text,
                use_exact_matching=self.parameters.use_exact_matching
            )
            return chain.invoke({
                **state.dict()
            })

        return extractor_node

    def add_core_nodes(self, workflow: StateGraph) -> StateGraph:
        workflow.add_node("extractor", self.get_extractor_node())
        return workflow

    def execute(self, *args, **kwargs):
        try:
            result = super().execute(*args, **kwargs)
            logging.info(f"Extractor execution result: {result}")
            return result
        except Exception as e:
            logging.error(f"Error in Extractor execution: {str(e)}")
            return {"metadata": {"text": "Error occurred during extraction"}}
