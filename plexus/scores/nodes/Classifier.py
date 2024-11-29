from typing import List, Dict, Any, Optional, Tuple, Annotated, Union
from pydantic import Field, BaseModel, ConfigDict
from langgraph.graph import StateGraph, END
from langgraph.errors import NodeInterrupt
from langchain_core.output_parsers import BaseOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage, SystemMessage
from plexus.scores.nodes.BaseNode import BaseNode
from plexus.CustomLogging import logging
import traceback
import os

class Classifier(BaseNode):
    """
    A node that performs binary classification using a LangGraph subgraph to separate
    LLM calls from parsing and retry logic.
    """
    
    class Parameters(BaseNode.Parameters):
        positive_class: str = Field(description="The label for the positive class")
        negative_class: str = Field(description="The label for the negative class")
        explanation_message: Optional[str] = None
        maximum_retry_count: int = Field(
            default=3,
            description="Maximum number of retries for classification"
        )
        parse_from_start: Optional[bool] = False

    class GraphState(BaseNode.GraphState):
        pass

    def __init__(self, **parameters):
        super().__init__(**parameters)
        self.parameters = Classifier.Parameters(**parameters)
        self.model = self._initialize_model()

    class ClassificationOutputParser(BaseOutputParser):
        """Parser that identifies one of two possible classifications."""
        positive_class: str = Field(...)
        negative_class: str = Field(...)
        parse_from_start: bool = Field(default=False)

        def parse(self, output: str) -> Dict[str, Any]:
            cleaned_output = ''.join(
                char.lower() 
                for char in output 
                if char.isalnum() or char.isspace()
            )
            words = cleaned_output.split()
            
            word_iterator = words if self.parse_from_start else reversed(words)
            classification = None
            
            for word in word_iterator:
                if word.lower() == self.positive_class.lower():
                    classification = self.positive_class
                    break
                elif word.lower() == self.negative_class.lower():
                    classification = self.negative_class
                    break
            
            return {
                "classification": classification,
                "explanation": output
            }

    def get_llm_prompt_node(self):
        """Node that only handles the LLM request."""
        model = self.model
        prompt_templates = self.get_prompt_templates()

        async def llm_request(state):
            logging.info("<*> Entering llm_request node")
            logging.debug(f"Initial state: {state}")
            
            # Convert to dict if needed
            if not isinstance(state, dict):
                state = state.model_dump()
            
            # Check if messages already exist in state
            if state.get('messages'):
                logging.info("Found existing messages in state - using these instead of building new ones")
                logging.info(f"Existing messages: {state['messages']}")
                return state
            
            # Build messages from chat history or initial prompt if empty
            if not state.get('chat_history'):
                logging.info("No chat history or existing messages, building initial messages")
                try:
                    prompt = prompt_templates[0].format_prompt(**state)
                    messages = prompt.to_messages()
                    logging.info(f"Built new messages: {[type(m).__name__ for m in messages]}")
                except Exception as e:
                    logging.error(f"Error building messages: {e}")
                    raise
            else:
                logging.info(f"Using existing chat history with {len(state['chat_history'])} messages")
                messages = state['chat_history']

            # Serialize messages to dict format
            serialized_messages = []
            for msg in messages:
                msg_dict = {
                    "type": msg.__class__.__name__.lower().replace("message", ""),
                    "content": msg.content,
                    "_type": type(msg).__name__
                }
                serialized_messages.append(msg_dict)
                truncated_msg = {
                    k: f"{str(v)[:80]}..." if isinstance(v, str) and len(str(v)) > 80 else v
                    for k, v in msg_dict.items()
                }
                logging.info(f"Serialized new message: {truncated_msg}")
            
            # Return state with messages
            new_state = {
                **state,
                "messages": serialized_messages
            }
            logging.info("Returning state with newly built messages")
            return new_state

        return llm_request

    def get_parser_node(self):
        """Node that handles parsing the completion."""
        parser = self.ClassificationOutputParser(
            positive_class=self.parameters.positive_class,
            negative_class=self.parameters.negative_class,
            parse_from_start=self.parameters.parse_from_start
        )

        async def parse_completion(state):
            logging.info("<*> Entering parse_completion node")
            if isinstance(state, dict):
                state = self.GraphState(**state)
            
            logging.info("Parsing completion")
            logging.debug(f"State before parsing: {state}")
            logging.debug(f"Completion to parse: {state.completion}")
            
            # Add check for None completion
            if state.completion is None:
                logging.info("No completion to parse - workflow likely interrupted")
                return state
            
            result = parser.parse(state.completion)
            logging.info(f"Parsed result: {result}")
            
            final_state = {**state.model_dump(), **result}
            logging.info(f"Final state after parsing: {final_state}")
            
            return final_state

        return parse_completion

    def get_retry_node(self):
        """Node that prepares for retry by updating chat history."""
        async def prepare_retry(state):
            logging.info("<*> Entering prepare_retry node")
            if isinstance(state, dict):
                state = self.GraphState(**state)
            
            retry_message = HumanMessage(content=(
                f"You responded with an invalid classification. "
                f"Please classify as either '{self.parameters.positive_class}' or "
                f"'{self.parameters.negative_class}'. This is attempt {state.retry_count + 1} "
                f"of {self.parameters.maximum_retry_count}."
            ))
            
            logging.info(f"Preparing retry attempt {state.retry_count + 1}")
            logging.debug(f"Retry message: {retry_message.content}")
            
            return {**state.model_dump(), 
                    "chat_history": [*state.chat_history, retry_message],
                    "retry_count": state.retry_count + 1}

        return prepare_retry

    def should_retry(self, state):
        """Determines whether to retry, end, or proceed based on state."""
        if state.classification is not None:
            logging.info("Classification found, ending")
            return "end"
        if state.retry_count >= self.parameters.maximum_retry_count:
            logging.info("Maximum retries reached")
            return "max_retries"
        logging.info("No valid classification, retrying")
        return "retry"

    def get_max_retries_node(self):
        """Node that handles the case when max retries are reached."""
        async def handle_max_retries(state):
            logging.info("<*> Entering handle_max_retries node")
            if isinstance(state, dict):
                state = self.GraphState(**state)
            
            logging.info("Setting classification to 'unknown' due to max retries")
            return {**state.model_dump(), 
                    "classification": "unknown",
                    "explanation": "Maximum retries reached"}

        return handle_max_retries

    def get_llm_call_node(self):
        """Node that makes the actual LLM API call."""
        model = self.model

        async def llm_call(state):
            logging.info("<*> Entering llm_call node")
            
            # Convert to dict if needed
            if not isinstance(state, dict):
                state = state.model_dump()

            # Check if we should break before making the API call
            batch_mode = os.getenv('PLEXUS_ENABLE_BATCH_MODE', '').lower() == 'true'
            breakpoints_enabled = os.getenv('PLEXUS_ENABLE_LLM_BREAKPOINTS', '').lower() == 'true'
            
            if batch_mode and breakpoints_enabled:
                logging.info("Breaking before LLM API call with messages in state")
                # Return state with breakpoint flag
                return {
                    **state,
                    "at_llm_breakpoint": True,
                    "should_end": True  # Signal that we want to end
                }
            
            try:
                if 'messages' not in state or not state['messages']:
                    logging.error("No messages found in state")
                    logging.info(f"Available keys: {state.keys()}")
                    raise ValueError("No messages found in state")
                
                # Deserialize messages back to BaseMessage objects
                deserialized_messages = []
                for msg in state['messages']:
                    msg_type = msg.get('type', '').lower()
                    explicit_type = msg.get('_type')
                    logging.info(f"Deserializing message - type: {msg_type}, explicit: {explicit_type}")
                    
                    try:
                        if msg_type == 'human':
                            msg_obj = HumanMessage(content=msg['content'])
                        elif msg_type == 'ai':
                            msg_obj = AIMessage(content=msg['content'])
                        elif msg_type == 'system':
                            msg_obj = SystemMessage(content=msg['content'])
                        else:
                            msg_obj = BaseMessage(content=msg['content'])
                        
                        deserialized_messages.append(msg_obj)
                        logging.info(f"Successfully deserialized message: {type(msg_obj).__name__}")
                    except Exception as e:
                        logging.error(f"Error deserializing message {msg}: {e}")
                        raise
                
                logging.info("Preparing to make LLM API call")
                chat_prompt = ChatPromptTemplate.from_messages(deserialized_messages)
                formatted_messages = chat_prompt.format_prompt().to_messages()
                logging.info(f"Formatted prompt messages: {[type(m).__name__ for m in formatted_messages]}")
                
                completion = await model.ainvoke(formatted_messages)
                logging.info("LLM call completed")
                logging.info(f"LLM response: {completion.content}")
                
                # Return state as dict
                result_state = {**state}  # Make a copy
                result_state.update({
                    'completion': completion.content,
                    'messages': None,  # Clear messages after use
                    'at_llm_breakpoint': False
                })
                
                logging.info(f"Final state keys: {result_state.keys()}")
                return result_state
                
            except Exception as e:
                logging.error(f"Error in llm_call: {e}")
                logging.error(f"Stack trace: {traceback.format_exc()}")
                raise

        return llm_call

    def should_continue(self, state):
        """Determines whether to continue or end based on state."""
        if isinstance(state, dict) and state.get("should_end"):
            logging.info("Found should_end flag, ending workflow")
            return "end"
        return "continue"

    def add_core_nodes(self, workflow: StateGraph) -> StateGraph:
        # Add all nodes
        workflow.add_node("llm_prompt", self.get_llm_prompt_node())
        workflow.add_node("llm_call", self.get_llm_call_node())
        workflow.add_node("parse", self.get_parser_node())
        workflow.add_node("retry", self.get_retry_node())
        workflow.add_node("max_retries", self.get_max_retries_node())

        # Add conditional edges for llm_call
        workflow.add_conditional_edges(
            "llm_call",
            self.should_continue,
            {
                "continue": "parse",
                "end": END
            }
        )

        # Add conditional edges for parse
        workflow.add_conditional_edges(
            "parse",
            self.should_retry,
            {
                "retry": "retry",
                "end": END,
                "max_retries": "max_retries"
            }
        )
        
        # Add regular edges
        workflow.add_edge("llm_prompt", "llm_call")
        workflow.add_edge("retry", "llm_prompt")
        workflow.add_edge("max_retries", END)
        
        # Set entry point
        workflow.set_entry_point("llm_prompt")
        
        return workflow