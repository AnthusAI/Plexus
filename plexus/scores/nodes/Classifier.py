from typing import List, Dict, Any, Optional, Tuple, Annotated, Union
from pydantic import Field, BaseModel, ConfigDict
from langgraph.graph import StateGraph, END
from langgraph.errors import NodeInterrupt
from langchain_core.output_parsers import BaseOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage, SystemMessage
from plexus.scores.nodes.BaseNode import BaseNode
from plexus.CustomLogging import logging
from plexus.scores.LangGraphScore import BatchProcessingPause
import traceback
import os
from plexus_dashboard.api.client import PlexusDashboardClient

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
                logging.info("Found existing messages in state - skipping message creation")
                truncated_messages = [
                    {k: (v[:80] + '...') if isinstance(v, str) and len(v) > 80 else v 
                     for k, v in msg.items()} for msg in state['messages']
                ]
                logging.info(f"Using existing messages: {truncated_messages}")
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
            
            final_state = {**state.model_dump(), 
                    "chat_history": [*state.chat_history, retry_message],
                    "retry_count": state.retry_count + 1}
            logging.info(f"Final state after retry preparation: {final_state}")
            return final_state

        return prepare_retry

    def should_retry(self, state):
        """Determines whether to retry, end, or proceed based on state."""
        logging.info("<*> Evaluating should_retry")
        if isinstance(state, dict):
            state = self.GraphState(**state)
        
        if state.classification is not None:
            logging.info(f"Classification found: {state.classification}, ending")
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
            final_state = {**state.model_dump(), 
                    "classification": "unknown",
                    "explanation": "Maximum retries reached"}
            logging.info(f"Final state after max retries: {final_state}")
            return final_state

        return handle_max_retries

    def get_llm_call_node(self):
        """Node that makes the actual LLM API call."""
        model = self.model

        async def llm_call(state):
            logging.info("<*> Entering llm_call node")
            
            # Convert to dict if needed
            if not isinstance(state, dict):
                state = state.model_dump()

            # Check if completion already exists
            if 'completion' in state and state['completion'] is not None:
                logging.info("Found existing completion in state - skipping LLM call")
                return {
                    **state,
                    'messages': None,  # Clear messages after use
                    'at_llm_breakpoint': False
                }

            # Check if we should break before making the API call
            batch_mode = os.getenv('PLEXUS_ENABLE_BATCH_MODE', '').lower() == 'true'
            breakpoints_enabled = os.getenv('PLEXUS_ENABLE_LLM_BREAKPOINTS', '').lower() == 'true'
            
            if batch_mode and breakpoints_enabled:
                logging.info("Breaking before LLM API call with messages in state")
                # Set flags in state for batch processing
                state['at_llm_breakpoint'] = True
                state['next_node'] = 'parse'  # Explicitly set next node
                
                # Create batch job here
                metadata = state.get('metadata', {})
                if not metadata:
                    logging.error("No metadata found in state")
                    logging.error(f"State keys: {state.keys()}")
                    raise ValueError("No metadata found in state")
                    
                account_key = metadata.get('account_key')
                if not account_key:
                    logging.error("No account_key found in metadata")
                    logging.error(f"Metadata keys: {metadata.keys()}")
                    logging.error(f"Full metadata: {metadata}")
                    raise ValueError("No account_key found in metadata")
                    
                client = PlexusDashboardClient.for_scorecard(
                    account_key=account_key,
                    scorecard_key=metadata.get('scorecard_key'),
                    score_name=metadata.get('score_name')
                )
                
                thread_id = metadata.get('content_id', 'unknown')
                try:
                    score_id = client._resolve_score_id()
                    scorecard_id = client._resolve_scorecard_id()
                    account_id = client._resolve_account_id()
                except Exception as e:
                    logging.error(f"Error resolving IDs: {str(e)}")
                    logging.error(f"Account key: {account_key}")
                    logging.error(f"Scorecard key: {metadata.get('scorecard_key')}")
                    logging.error(f"Score name: {metadata.get('score_name')}")
                    logging.error(f"Full metadata: {metadata}")
                    raise
                
                # Create a serializable copy of the state
                serializable_state = {}
                logging.info(f"Creating serializable state from keys: {state.keys()}")

                # First copy all primitive fields directly
                for key, value in state.items():
                    if isinstance(value, (str, int, float, bool, type(None))):
                        serializable_state[key] = value
                        logging.info(f"Copied primitive field {key}: {value}")

                # Handle messages list specially
                if 'messages' in state:
                    if isinstance(state['messages'], list):
                        serializable_state['messages'] = [
                            {
                                'type': msg.get('type', ''),
                                'content': msg.get('content', ''),
                                '_type': msg.get('_type', '')
                            } if isinstance(msg, dict) else
                            {
                                'type': msg.__class__.__name__.lower().replace('message', ''),
                                'content': msg.content,
                                '_type': msg.__class__.__name__
                            }
                            for msg in state['messages']
                        ]
                        logging.info(f"Serialized messages: {serializable_state['messages']}")

                # Handle chat_history list specially
                if 'chat_history' in state:
                    if isinstance(state['chat_history'], list):
                        serializable_state['chat_history'] = [
                            {
                                'type': msg.__class__.__name__.lower().replace('message', ''),
                                'content': msg.content,
                                '_type': msg.__class__.__name__
                            }
                            for msg in state['chat_history']
                        ]
                        logging.info(f"Serialized chat_history: {serializable_state['chat_history']}")

                # Handle metadata specially to ensure it's included
                if 'metadata' in state:
                    serializable_state['metadata'] = state['metadata']
                    logging.info(f"Copied metadata: {serializable_state['metadata']}")

                # Handle any remaining fields by converting to string representation
                for key, value in state.items():
                    if key not in serializable_state:
                        try:
                            serializable_state[key] = str(value)
                            logging.info(f"Converted field {key} to string: {serializable_state[key]}")
                        except Exception as e:
                            logging.warning(f"Could not serialize field {key}: {str(e)}")

                logging.info(f"Final serializable state: {serializable_state}")
                
                # Create batch job with serializable state
                logging.info(f"Creating batch job with state: {serializable_state}")
                logging.info(f"State type: {type(serializable_state)}")

                client = PlexusDashboardClient.for_scorecard(
                    account_key=state.get('metadata', {}).get('account_key'),
                    scorecard_key=state.get('metadata', {}).get('scorecard_key'),
                    score_name=state.get('metadata', {}).get('score_name')
                )

                logging.info(f"Creating batch job with metadata: {{'state': serializable_state}}")
                logging.info(f"Score ID: {score_id}")
                logging.info(f"Scorecard ID: {scorecard_id}")
                logging.info(f"Account ID: {account_id}")

                scoring_job, batch_job = client.batch_scoring_job(
                    itemId=thread_id,
                    scorecardId=scorecard_id,
                    accountId=account_id,
                    model_provider='ChatOpenAI',
                    model_name='gpt-4o-mini',
                    scoreId=score_id,
                    status='PENDING',
                    metadata={'state': serializable_state},
                    parameters={
                        'thread_id': thread_id,
                        'breakpoint': True
                    }
                )

                if batch_job:
                    logging.info(f"Created batch job with ID: {batch_job.id}")
                else:
                    logging.info(f"Using existing scoring job with ID: {scoring_job.id}")

                raise BatchProcessingPause(
                    thread_id=thread_id,
                    state=state,
                    batch_job_id=batch_job.id if batch_job else None,
                    message=f"Execution paused for batch processing. Scoring job ID: {scoring_job.id}"
                )
            
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

    def add_core_nodes(self, workflow: StateGraph) -> StateGraph:
        """Add core nodes to the workflow."""
        logging.info("Adding core nodes to workflow...")
        
        # Add all nodes
        workflow.add_node("llm_prompt", self.get_llm_prompt_node())
        logging.info("Added llm_prompt node")
        
        workflow.add_node("llm_call", self.get_llm_call_node())
        logging.info("Added llm_call node")
        
        workflow.add_node("parse", self.get_parser_node())
        logging.info("Added parse node")
        
        workflow.add_node("retry", self.get_retry_node())
        logging.info("Added retry node")
        
        workflow.add_node("max_retries", self.get_max_retries_node())
        logging.info("Added max_retries node")

        # Add conditional edges for parse
        logging.info("Adding conditional edges for parse...")
        workflow.add_conditional_edges(
            "parse",
            self.should_retry,
            {
                "retry": "retry",
                "end": END,
                "max_retries": "max_retries"
            }
        )
        logging.info("Added parse edges")
        
        # Add regular edges
        workflow.add_edge("llm_prompt", "llm_call")
        workflow.add_edge("llm_call", "parse")
        workflow.add_edge("retry", "llm_prompt")
        workflow.add_edge("max_retries", END)
        logging.info("Added regular edges")
        
        # Set entry point
        workflow.set_entry_point("llm_prompt")
        logging.info("Set entry point to llm_prompt")
        
        return workflow