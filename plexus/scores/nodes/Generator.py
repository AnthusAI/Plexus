from typing import List, Dict, Any, Optional, Tuple, Annotated, Union
from pydantic import Field, BaseModel, ConfigDict
from langgraph.graph import StateGraph, END
from langgraph.errors import NodeInterrupt
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import AIMessage, HumanMessage, BaseMessage, SystemMessage
from plexus.scores.nodes.BaseNode import BaseNode
from plexus.CustomLogging import logging
from plexus.scores.LangGraphScore import BatchProcessingPause
import traceback
import os
from plexus.dashboard.api.client import PlexusDashboardClient
import uuid

class Generator(BaseNode):
    """
    A node that simply generates completions from LLM calls using a LangGraph subgraph.
    This is a simplified version of Classifier without classification logic.
    It just focuses on generating content to be aliased via output configuration.
    """
    
    batch: bool = False  # Class-level attribute for batch configuration
    
    class Parameters(BaseNode.Parameters):
        maximum_retry_count: int = Field(
            default=1,
            description="Maximum number of retries for LLM generation"
        )

    class GraphState(BaseNode.GraphState):
        completion: Optional[str] = None
        explanation: Optional[str] = None
        retry_count: int = 0

    def __init__(self, **parameters):
        # Extract batch parameter before passing to super
        self.batch = parameters.pop('batch', False)
        super().__init__(**parameters)
        self.parameters = Generator.Parameters(**parameters)
        self.model = self._initialize_model()

    def get_llm_prompt_node(self):
        """Node that only handles the LLM request."""
        model = self.model
        prompt_templates = self.get_prompt_templates()

        async def llm_request(state):
            logging.info("<*> Entering llm_request node")
            logging.debug(f"Initial state: {state}")
            
            # Keep state as GraphState object to preserve Message types
            if isinstance(state, dict):
                state = self.GraphState(**state)
            
            # Add detailed logging
            logging.info("Message details:")
            if hasattr(state, 'messages') and state.messages:
                for i, msg in enumerate(state.messages):
                    logging.info(f"Message {i}: type={type(msg)}, content={msg}")
            if hasattr(state, 'chat_history') and state.chat_history:
                for i, msg in enumerate(state.chat_history):
                    logging.info(f"Message type: {type(msg)}, content={msg}")
            
            # If we have chat history from a retry, use that
            if hasattr(state, 'chat_history') and state.chat_history:
                logging.info(f"Using existing chat history with {len(state.chat_history)} messages")
                
                # Convert dict messages back to LangChain objects if needed
                chat_messages = []
                for msg in state.chat_history:
                    if isinstance(msg, dict):
                        msg_type = msg.get('type', '').lower()
                        if msg_type == 'human':
                            chat_messages.append(HumanMessage(content=msg['content']))
                        elif msg_type == 'ai':
                            chat_messages.append(AIMessage(content=msg['content']))
                        elif msg_type == 'system':
                            chat_messages.append(SystemMessage(content=msg['content']))
                        else:
                            chat_messages.append(BaseMessage(content=msg['content']))
                    else:
                        chat_messages.append(msg)
                
                # Get the initial system and human messages from prompt template
                prompt = prompt_templates[0].format_prompt(**state.model_dump())
                initial_messages = prompt.to_messages()[:2]  # Only take system and first human message
                
                # Combine messages in the correct order:
                # 1. System message from initial_messages[0]
                # 2. Original human message from initial_messages[1]
                # 3. All chat history messages in order
                messages = initial_messages + chat_messages
                
                # Log the final message sequence
                logging.info("Final message sequence:")
                for i, msg in enumerate(messages):
                    logging.info(f"Message {i}: type={type(msg)}, content={msg.content}")
            # Otherwise build new messages from prompt template
            else:
                logging.info("Building new messages from prompt template")
                try:
                    prompt = prompt_templates[0].format_prompt(**state.model_dump())
                    messages = prompt.to_messages()
                    logging.info(f"Built new messages: {[type(m).__name__ for m in messages]}")
                except Exception as e:
                    logging.error(f"Error building messages: {e}")
                    raise

            # Convert messages to dicts for state storage
            message_dicts = [{
                'type': msg.__class__.__name__.lower().replace('message', ''),
                'content': msg.content,
                '_type': msg.__class__.__name__
            } for msg in messages]

            # Store messages as dicts in state - they'll be converted back to objects when needed
            return self.GraphState(
                **{k: v for k, v in state.model_dump().items() if k not in ['messages', 'completion', 'explanation', 'chat_history']},
                messages=message_dicts,
                chat_history=state.chat_history if hasattr(state, 'chat_history') else [],
                completion=None,  # Always start with no completion
                explanation=None  # Always start with no explanation
            )

        return llm_request

    def get_retry_node(self):
        """Node that prepares for retry by updating chat history."""
        async def prepare_retry(state):
            logging.info("<*> Entering prepare_retry node")
            if isinstance(state, dict):
                state = self.GraphState(**state)
            
            retry_message = HumanMessage(content=(
                f"Please try generating a response again. "
                f"This is attempt {state.retry_count + 1} "
                f"of {self.parameters.maximum_retry_count}."
            ))
            
            logging.info(f"Preparing retry attempt {state.retry_count + 1}")
            logging.debug(f"Retry message: {retry_message}")
            
            # Get the initial system and human messages
            initial_messages = []
            if hasattr(state, 'messages') and state.messages:
                for msg in state.messages[:2]:  # Only take the first two messages (system and initial human)
                    if isinstance(msg, dict):
                        initial_messages.append(msg)
                    else:
                        initial_messages.append({
                            'type': msg.__class__.__name__.lower().replace('message', ''),
                            'content': msg.content,
                            '_type': msg.__class__.__name__
                        })

            # Initialize or update chat history
            chat_history = []
            if state.chat_history:
                chat_history.extend(state.chat_history)
            
            # Add the last completion to chat history if it exists
            if state.completion is not None:
                chat_history.append({
                    'type': 'ai',
                    'content': state.completion,
                    '_type': 'AIMessage'
                })
            
            # Add the retry message
            chat_history.append({
                'type': 'human',
                'content': retry_message.content,
                '_type': 'HumanMessage'
            })
            
            # Store messages as dicts in state and explicitly clear completion
            new_state = self.GraphState(
                chat_history=chat_history,
                messages=initial_messages + chat_history,  # Combine initial messages with chat history
                retry_count=state.retry_count + 1,
                completion=None,  # Explicitly clear completion for next LLM call
                explanation=None,  # Also clear explanation for next LLM call
                **{k: v for k, v in state.model_dump().items() 
                   if k not in ['chat_history', 'retry_count', 'completion', 'explanation', 'messages']}
            )
            
            logging.info(f"Final state after retry preparation: {new_state}")
            return new_state

        return prepare_retry

    def should_retry(self, state):
        """Determines whether to retry, end, or proceed based on state."""
        logging.info("<*> Evaluating should_retry")
        if isinstance(state, dict):
            state = self.GraphState(**state)
        
        # Check if either completion or explanation has content
        has_completion = state.completion is not None and state.completion.strip()
        has_explanation = state.explanation is not None and state.explanation.strip()
        
        if has_completion or has_explanation:
            logging.info(f"Content generated, ending")
            return "end"
        if state.retry_count >= self.parameters.maximum_retry_count:
            logging.info("Maximum retries reached")
            return "max_retries"
            
        # Clear completion and explanation when we need to retry
        logging.info("No valid content, clearing completion/explanation and retrying")
        state.completion = None
        state.explanation = None
        return "retry"

    def get_max_retries_node(self):
        """Node that handles the case when max retries are reached."""
        async def handle_max_retries(state: self.GraphState) -> self.GraphState:
            logging.info("<*> Entering handle_max_retries node")
            logging.info("Setting empty completion due to max retries")
            error_message = "Failed to generate a valid completion after maximum retry attempts."
            state_dict = state.model_dump()
            state_dict['completion'] = error_message
            state_dict['explanation'] = error_message  # Also set explanation for backward compatibility
            logging.info(f"Final state after max retries: {state_dict}")
            return self.GraphState(**state_dict)
        return handle_max_retries

    def get_llm_call_node(self):
        """Node that handles the LLM call."""
        model = self.model

        async def llm_call(state):
            try:
                if isinstance(state, dict):
                    state = self.GraphState(**state)

                if not state.messages:
                    logging.error("No messages found in state")
                    logging.info(f"Available keys: {state.keys()}")
                    raise ValueError("No messages found in state")

                # If batch mode is enabled, use batch processing
                if self.batch:
                    # Create a serializable copy of the state
                    serializable_state = {}
                    state_dict = state.model_dump()
                    logging.info(f"Creating serializable state from keys: {state_dict.keys()}")

                    # First copy all primitive fields directly
                    for key, value in state_dict.items():
                        if isinstance(value, (str, int, float, bool, type(None))):
                            serializable_state[key] = value
                            logging.debug(f"Copied primitive field {key}: {value}")

                    # Handle messages list specially - handle both dict and Message objects
                    if 'messages' in state_dict:
                        serializable_state['messages'] = [
                            msg if isinstance(msg, dict) else {
                                'type': msg.__class__.__name__.lower().replace('message', ''),
                                'content': msg.content,
                                '_type': msg.__class__.__name__
                            }
                            for msg in state_dict['messages']
                        ]
                        logging.info("Serialized messages prepared")

                    # Handle chat_history list specially
                    if 'chat_history' in state_dict:
                        if isinstance(state_dict['chat_history'], list):
                            serializable_state['chat_history'] = [
                                {
                                    'type': msg.__class__.__name__.lower().replace('message', ''),
                                    'content': msg.content,
                                    '_type': msg.__class__.__name__
                                }
                                for msg in state_dict['chat_history']
                            ]
                            logging.info("Chat history serialized")

                    # Handle metadata specially to ensure it's included
                    if 'metadata' in state_dict:
                        serializable_state['metadata'] = state_dict['metadata']
                        logging.info("Metadata copied")

                    # Handle any remaining fields by converting to string representation
                    for key, value in state_dict.items():
                        if key not in serializable_state:
                            try:
                                serializable_state[key] = str(value)
                                logging.info(f"Converted field {key}")
                            except Exception as e:
                                logging.warning(f"Could not serialize field {key}: {str(e)}")

                    logging.info("State serialization complete")
                    
                    try:
                        # Create batch job with serializable state
                        logging.info("Creating batch job...")

                        client = PlexusDashboardClient.for_scorecard(
                            account_key=state.metadata.get('account_key'),
                            scorecard_key=state.metadata.get('scorecard_key'),
                            score_name=state.metadata.get('score_name')
                        )

                        # Extract required IDs from metadata
                        thread_id = state.metadata.get('content_id', 'unknown')
                        score_id = client._resolve_score_id()
                        scorecard_id = client._resolve_scorecard_id()
                        account_id = client._resolve_account_id()

                        # Create batch job with metadata
                        logging.info(f"Creating batch job for thread_id: {thread_id}")
                        logging.info(f"Score ID: {score_id}")
                        logging.info(f"Scorecard ID: {scorecard_id}")
                        logging.info(f"Account ID: {account_id}")

                        scoring_job, batch_job = client.batch_scoring_job(
                            itemId=thread_id,
                            scorecardId=scorecard_id,
                            accountId=account_id,
                            model_provider='ChatOpenAI',
                            model_name='gpt-4',
                            scoreId=score_id,
                            status='PENDING',
                            metadata={'state': serializable_state},
                            parameters={
                                'thread_id': thread_id,
                                'breakpoint': True
                            }
                        )

                        if not batch_job or not scoring_job:
                            raise ValueError("Failed to find or create batch job")

                        logging.info(f"Created batch job with ID: {batch_job.id}")
                        logging.info(f"Created scoring job with ID: {scoring_job.id}")

                        raise BatchProcessingPause(
                            thread_id=thread_id,
                            state=serializable_state,
                            batch_job_id=batch_job.id,
                            message=f"Execution paused for batch processing. Scoring job ID: {scoring_job.id}"
                        )
                    except BatchProcessingPause:
                        raise  # Re-raise BatchProcessingPause as it's expected
                    except Exception as e:
                        logging.error(f"Error creating batch job: {str(e)}")
                        logging.error(f"Stack trace: {traceback.format_exc()}")
                        raise BatchProcessingPause(
                            thread_id=state.metadata.get('content_id', 'unknown'),
                            state=serializable_state,
                            batch_job_id=str(uuid.uuid4()),  # Generate a temporary ID
                            message=f"Batch processing initiated despite error: {str(e)}"
                        )
                else:
                    # Non-batch mode - direct LLM call
                    # Convert dict messages back to LangChain objects if needed
                    messages = []
                    for msg in state.messages:
                        if isinstance(msg, dict):
                            msg_type = msg.get('type', '').lower()
                            if msg_type == 'human':
                                messages.append(HumanMessage(content=msg['content']))
                            elif msg_type == 'ai':
                                messages.append(AIMessage(content=msg['content']))
                            elif msg_type == 'system':
                                messages.append(SystemMessage(content=msg['content']))
                            else:
                                messages.append(BaseMessage(content=msg['content']))
                        else:
                            messages.append(msg)

                    response = await model.ainvoke(messages)
                    
                    # Create the initial result state
                    result_state = self.GraphState(
                        **{k: v for k, v in state.model_dump().items() if k not in ['completion']},
                        completion=response.content
                    )
                    
                    output_state = {
                        "explanation": response.content
                    }
                    
                    # Log the state and get a new state object with updated node_results
                    updated_state = self.log_state(result_state, None, output_state)
                    
                    return updated_state

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
        
        workflow.add_node("retry", self.get_retry_node())
        logging.info("Added retry node")
        
        workflow.add_node("max_retries", self.get_max_retries_node())
        logging.info("Added max_retries node")

        # Add conditional edges for should_retry
        logging.info("Adding conditional edges for should_retry...")
        workflow.add_conditional_edges(
            "llm_call",
            self.should_retry,
            {
                "retry": "retry",
                "end": END,
                "max_retries": "max_retries"
            }
        )
        logging.info("Added should_retry edges")
        
        # Add regular edges
        workflow.add_edge("llm_prompt", "llm_call")
        workflow.add_edge("retry", "llm_prompt")
        workflow.add_edge("max_retries", END)
        logging.info("Added regular edges")
        
        # Set entry point
        workflow.set_entry_point("llm_prompt")
        logging.info("Set entry point to llm_prompt")
        
        return workflow 