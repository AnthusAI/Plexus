from plexus.scores.Score import Score
from plexus.CustomLogging import logging
from plexus.scores.LangGraphScore import LangGraphScore
from typing import Dict, TypedDict, Optional, Literal, Annotated
from langchain.output_parsers import ResponseSchema, StructuredOutputParser
from langchain_core.prompts import PromptTemplate, ChatPromptTemplate
from langchain_core.messages import HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages, AnyMessage

# Logging.
from langchain.globals import set_debug
set_debug(True)

class ExtractorState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    transcript: str
    entity: Optional[str]
    quote: Optional[str]
    validation_error: Optional[str]
    
class AgenticExtractor(LangGraphScore):
    
    class Parameters(LangGraphScore.Parameters):
        ...
        prompt: str

    def __init__(self, scorecard_name, score_name, **kwargs):
        super().__init__(scorecard_name=scorecard_name, score_name=score_name, **kwargs)

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


            template_string = """
{format_instructions}

This is the transcript of a call center phone call that we're reviewing for QA purposes:
{transcript}

{prompt}
"""
            prompt = PromptTemplate(
                template=template_string,
                input_variables=["transcript", "prompt"]
            )
            
            if state["validation_error"] is not None:
                messages = [
                    template_string,
                    state['messages'][-1],
                    HumanMessage(content=state["validation_error"])
                ]
                prompt = ChatPromptTemplate.from_messages(
                    messages=messages
                )

            chain = prompt | self.model
        
            output = chain.invoke({
                "transcript": model_input.transcript, 
                "prompt": self.parameters.prompt,
                "format_instructions": output_parser.get_format_instructions()
            })
            
            result = output_parser.invoke(output)

            return {
                "messages": output,
                "entity":   result["entity"],
                "quote":    result["quote"]
            }
        
        def _verify_entity_node(state: ExtractorState) -> Dict[str, str]:
            entity = state.get("entity", "")
            transcript = state.get("transcript", "")

            if entity and entity.lower() not in transcript.lower():
                return {"validation_error": f"No, that's not possible: The string \"{entity}\" does not exist within the transcript."}
            else:
                return {"validation_error": None}

        def _next_after_verify_entity(state: ExtractorState) -> Dict[str, str]:
            if state["validation_error"] is not None:
                return "extract_entity"
            return END

        workflow = StateGraph(ExtractorState)

        workflow.add_node("extract_entity", _extract_entity_node)
        workflow.set_entry_point("extract_entity")
        workflow.add_edge("extract_entity", "verify_entity")
        
        workflow.add_node("verify_entity", _verify_entity_node)
        workflow.add_conditional_edges("verify_entity", _next_after_verify_entity)

        app = workflow.compile()

        result = app.invoke({"transcript": transcript.lower()})
        logging.info(f"LangGraph result: {result}")

        return [
            LangGraphScore.ModelOutput(
                score_name =  self.parameters.score_name,
                score =       result["entity"],
                explanation = AgenticExtractor.clean_quote(result["quote"])
            )
        ]

    @staticmethod
    def clean_quote(quote: str) -> str:
        quote = ' '.join(quote.split())  # Condense any whitespace into single characters
        if not (quote.startswith('“') and quote.endswith('”')):
            if quote.startswith("'") and quote.endswith("'"):
                quote = f'“{quote[1:-1]}”'
            elif not (quote.startswith('"') and quote.endswith('"')):
                quote = f'“{quote}”'
        return quote
