from plexus.scores.Score import Score
from plexus.CustomLogging import logging
import pandas as pd

from langgraph.graph import StateGraph, END
from typing import Dict, TypedDict, Optional, Literal

class GraphState(TypedDict):
    init_input: Optional[str]
    recruiter_name: Optional[str]
    final_result: Optional[str]

class AgenticExtractor(Score):
    def __init__(self, scorecard_name, score_name, **kwargs):
        super().__init__(scorecard_name=scorecard_name, score_name=score_name, **kwargs)

    transcript_df = pd.DataFrame({"Transcription": ["Hello, this is recruiter Johnny Bravo speaking."]})

    def load_context(self, context):
        # Implement any context loading logic here
        pass

    def predict(self, model_input):
        #self.model_input = self.transcript_df
        if isinstance(model_input, pd.DataFrame) and 'Transcription' in model_input.columns:
            logging.info(f"Transcription: {model_input['Transcription']}")
            return self.process_transcript(model_input['Transcription'].iloc[0])
        else:
            logging.error(f"Invalid input type: {type(model_input)}")
            return None

    def process_transcript(self, transcript):
        def input_first(state: GraphState) -> Dict[str, str]:
            logging.info("start input_first()")
            words = transcript.split()
            try:
                recruiter_index = words.index("recruiter")
                recruiter_name = words[recruiter_index + 1] + " " + words[recruiter_index + 2]
                return {"recruiter_name": recruiter_name}
            except (ValueError, IndexError):
                return {"recruiter_name": "error"}

        def complete_word(state: GraphState) -> Dict[str, str]:
            logging.info("start complete_word()")
            if state.get("recruiter_name") == "error":
                return {"final_result": "error"}
            return {"final_result": f"Recruiter name: {state['recruiter_name']}"}

        def error(state: GraphState) -> Dict[str, str]:
            logging.info("start error()")
            return {"final_result": "error", "recruiter_name": "error"}

        def continue_next(state: GraphState) -> Literal["to_complete_word", "to_error"]:
            logging.info(f"continue_next: state: {state}")
            if state.get("recruiter_name") != "error":
                logging.info("- continue to_complete_word")
                return "to_complete_word"
            else:
                logging.info("- continue to_error")
                return "to_error"

        # Create a state graph
        workflow = StateGraph(GraphState)

        # Add nodes to the state graph
        workflow.add_node("input_first", input_first)
        workflow.add_node("complete_word", complete_word)
        workflow.add_node("error", error)

        # Set entry point
        workflow.set_entry_point("input_first")

        # Add edges to the state graph
        workflow.add_edge("complete_word", END)
        workflow.add_edge("error", END)

        # Add conditional edges
        workflow.add_conditional_edges(
            "input_first",  # start node name
            continue_next,  # decision of what to do next AFTER start-node
            {  # keys: return of continue_next, values: next node to continue
                "to_complete_word": "complete_word",
                "to_error": "error",
            },
        )

        # Compile the workflow
        app = workflow.compile()

        # Process the transcript
        result = app.invoke({"init_input": transcript.lower()})
        logging.info(f"LangGraph result: {result}")
        return result
