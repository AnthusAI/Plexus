from typing import Dict, Optional, Any, Callable
import pydantic
from pydantic import Field
from langgraph.graph import StateGraph, END
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import BaseOutputParser
from plexus.LangChainUser import LangChainUser
from plexus.scores.nodes.BaseNode import BaseNode
from plexus.CustomLogging import logging

class AgenticExtractor(BaseNode, LangChainUser):
    """
    A node that extracts entities and related quotes from text based on the provided prompt.
    """
    
    class Parameters(LangChainUser.Parameters):
        system_message: str
        human_message: str
        input: Optional[dict] = None
        output: Optional[dict] = None

    def __init__(self, **parameters):
        combined_parameters_model = pydantic.create_model(
            "CombinedParameters",
            __base__=(AgenticExtractor.Parameters, LangChainUser.Parameters))
        self.parameters = combined_parameters_model(**parameters)
        self.openai_callback = None
        self.model = self._initialize_model()

    class GraphState(BaseNode.GraphState):
        entity: Optional[str] = None
        quote: Optional[str] = None
        text: Optional[str] = None

    class ExtractionOutputParser(BaseOutputParser[dict]):
        @property
        def _type(self) -> str:
            return "extraction_output_parser"
        
        def parse(self, output: str) -> Dict[str, Any]:
            output = output.strip().strip('"')
            lines = output.split('\n')
            entity = ""
            quote = ""
            
            for line in lines:
                if line.startswith("Entity:"):
                    entity = line.split(":", 1)[1].strip()
                elif line.startswith("Quote:"):
                    quote = line.split(":", 1)[1].strip()
            
            logging.info(f"Extracted entity: {entity}")
            logging.info(f"Extracted quote: {quote}")
            
            return {
                "entity": entity,
                "quote": AgenticExtractor.clean_quote(quote)
            }

    def get_extractor_node(self) -> Callable:
        model = self.model
        system_message = self.parameters.system_message
        human_message = self.parameters.human_message

        def extractor_node(state):
            logging.info(f"Extractor node received state: {state}")
            logging.info(f"Text in extractor node: {state.text[:100] if state.text else 'None'}")
            
            if not state.text:
                logging.warning("Text is empty in extractor node")
                return state  # Return early if text is empty

            prompt = ChatPromptTemplate.from_messages([
                ("system", system_message),
                ("human", human_message)
            ])
            chain = prompt | model | self.ExtractionOutputParser()
            
            result = chain.invoke({"text": state.text})
            logging.info(f"Extraction result: {result}")
            
            state.entity = result.get("entity", "")
            state.quote = result.get("quote", "")
            
            return state

        return extractor_node

    def add_core_nodes(self, workflow: StateGraph) -> StateGraph:
        workflow.add_node("extract_entity", self.get_extractor_node())
        return workflow

    @staticmethod
    def clean_quote(quote: str) -> str:
        quote = ' '.join(quote.split())
        if not (quote.startswith('"') and quote.endswith('"')):
            if quote.startswith("'") and quote.endswith("'"):
                quote = f'"{quote[1:-1]}"'
            elif not (quote.startswith('"') and quote.endswith('"')):
                quote = f'"{quote}"'
        return quote