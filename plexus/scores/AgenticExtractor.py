from plexus.scores.Score import Score
from plexus.CustomLogging import logging
from plexus.scores.LangGraphScore import LangGraphScore
from typing import Dict, TypedDict, Optional, Literal, Annotated
from langchain.output_parsers import ResponseSchema, StructuredOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class ExtractorState(TypedDict):
    transcript: str
    entity: Optional[str]
    quote: Optional[str]
    
class AgenticExtractor(LangGraphScore):
    
    class Parameters(LangGraphScore.Parameters):
        ...
        prompt: str

    def __init__(self, scorecard_name, score_name, **kwargs):
        super().__init__(scorecard_name=scorecard_name, score_name=score_name, **kwargs)
        
        # Logging.
        from langchain.globals import set_debug
        set_debug(True)

    def load_context(self, context):
        pass

    def predict(self, context, model_input: Score.ModelInput):
        transcript = model_input.transcript

        def _extract_entity_node(state: ExtractorState) -> Dict[str, str]:
            logging.info("start _extract_entity_node()")
            logging.info(f"Transcript: {state['transcript']}")
            
            response_schemas = [
                ResponseSchema(name="entity", description="entity in the transcript"),
                ResponseSchema(name="quote", description="related quote(s) from the transcript that include the entity"),
            ]
            output_parser = StructuredOutputParser.from_response_schemas(response_schemas)

            format_instructions = output_parser.get_format_instructions()
            prompt = PromptTemplate(
                template="""
{format_instructions}

This is the transcript of a call center phone call that we're reviewing for QA purposes:
{transcript}

{prompt}
""",
                input_variables=["transcript", "prompt"],
                partial_variables={"format_instructions": format_instructions},
            )

            model = ChatOpenAI(temperature=0)
            chain = prompt | model | output_parser
            
            result = chain.invoke({
                "transcript": model_input.transcript, 
                "prompt": self.parameters.prompt
            })

            return {
                "entity": result["entity"],
                "quote": result["quote"]
            }

        def clean_quote(quote: str) -> str:
            quote = ' '.join(quote.split())  # Condense any whitespace into single characters
            if not (quote.startswith('“') and quote.endswith('”')):
                if quote.startswith("'") and quote.endswith("'"):
                    quote = f'“{quote[1:-1]}”'
                elif not (quote.startswith('"') and quote.endswith('"')):
                    quote = f'“{quote}”'
            return quote

        workflow = StateGraph(ExtractorState)

        workflow.add_node("extract_entity", _extract_entity_node)
        
        workflow.set_entry_point("extract_entity")

        workflow.add_edge("extract_entity", END)

        app = workflow.compile()

        result = app.invoke({"transcript": transcript.lower()})
        logging.info(f"LangGraph result: {result}")

        return [
            LangGraphScore.ModelOutput(
                score_name =  self.parameters.score_name,
                score =       result["entity"],
                explanation = clean_quote(result["quote"])
            )
        ]