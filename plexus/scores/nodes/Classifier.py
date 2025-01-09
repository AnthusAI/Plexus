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
from plexus.dashboard.api.client import PlexusDashboardClient

class Classifier(BaseNode):
    """
    A node that performs binary classification using a LangGraph subgraph to separate
    LLM calls from parsing and retry logic.
    """
    
    batch: bool = False  # Class-level attribute for batch configuration
    
    class Parameters(BaseNode.Parameters):
        valid_classes: List[str] = Field(description="List of valid classification labels")
        explanation_message: Optional[str] = None
        maximum_retry_count: int = Field(
            default=3,
            description="Maximum number of retries for classification"
        )
        parse_from_start: Optional[bool] = False

    class GraphState(BaseNode.GraphState):
        pass

    def __init__(self, **parameters):
        # Extract batch parameter before passing to super
        self.batch = parameters.pop('batch', False)
        super().__init__(**parameters)
        self.parameters = Classifier.Parameters(**parameters)
        self.model = self._initialize_model()

    class ClassificationOutputParser(BaseOutputParser):
        """Parser that identifies one of the valid classifications."""
        valid_classes: List[str] = Field(description="List of valid classification labels")
        parse_from_start: bool = Field(default=False, description="Whether to parse from start (True) or end (False)")

        def __init__(self, **data):
            super().__init__(**data)
            if not self.valid_classes:
                self.valid_classes = ["Yes", "No"]

        def normalize_text(self, text: str) -> str:
            """Normalize text by converting to lowercase and handling special characters."""
            # Replace underscores and multiple spaces with a single space
            text = text.replace("_", " ")
            text = " ".join(text.split())
            # Remove all non-alphanumeric characters except spaces
            return ''.join(c.lower() for c in text if c.isalnum() or c.isspace())

        def find_matches_in_text(self, text: str) -> List[Tuple[str, int, int]]:
            """Find all matches in text with their line and position.
            Returns list of tuples: (valid_class, line_number, position)
            """
            matches = []
            lines = text.strip().split('\n')
            
            # First normalize all valid classes (do this once)
            normalized_classes = [(vc, self.normalize_text(vc), i) for i, vc in enumerate(self.valid_classes)]
            
            # When parsing from end, sort by length to handle overlapping terms
            # When parsing from start, keep original order
            if not self.parse_from_start:
                normalized_classes.sort(key=lambda x: len(x[1]), reverse=True)
            
            # Process each line
            for line_idx, line in enumerate(lines):
                normalized_line = self.normalize_text(line)
                
                # Find all matches in this line
                for original_class, normalized_class, original_idx in normalized_classes:
                    pos = 0
                    while True:
                        pos = normalized_line.find(normalized_class, pos)
                        if pos == -1:
                            break
                            
                        # Check word boundaries
                        before = pos == 0 or normalized_line[pos - 1].isspace()
                        after = (pos + len(normalized_class) == len(normalized_line) or 
                                normalized_line[pos + len(normalized_class)].isspace())
                        
                        if before and after:
                            # Store original index to maintain order
                            matches.append((original_class, line_idx, pos, original_idx))
                            # When parsing from start, return first match immediately
                            if self.parse_from_start:
                                return [(original_class, line_idx, pos, original_idx)]
                            # Skip past this match
                            pos += len(normalized_class)
                        else:
                            # Move past this position
                            pos += 1
            
            return matches

        def select_match(self, matches: List[Tuple[str, int, int, int]], text: str) -> Optional[str]:
            """Select the appropriate match based on parse_from_start setting."""
            if not matches:
                return None
                
            if self.parse_from_start:
                # When parsing from start, we already have the first match
                return matches[0][0]
            else:
                # When parsing from end, sort by line and position in reverse
                matches.sort(key=lambda x: (x[1], x[2]), reverse=True)
                return matches[0][0]  # Return the original class name

        def parse(self, output: str) -> Dict[str, Any]:
            # Find all matches in the text
            matches = self.find_matches_in_text(output)
            
            # Select the appropriate match
            selected_class = self.select_match(matches, output)
            
            return {
                "classification": selected_class,
                "explanation": output.strip()
            }

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
            
            # Get messages from state or create new ones
            if hasattr(state, 'messages') and state.messages:
                logging.info("Found existing messages in state")
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
            else:
                # Build messages from chat history or initial prompt if empty
                if not hasattr(state, 'chat_history') or not state.chat_history:
                    logging.info("No chat history or existing messages, building initial messages")
                    try:
                        prompt = prompt_templates[0].format_prompt(**state.model_dump())
                        messages = prompt.to_messages()
                        logging.info(f"Built new messages: {[type(m).__name__ for m in messages]}")
                    except Exception as e:
                        logging.error(f"Error building messages: {e}")
                        raise
                else:
                    logging.info(f"Using existing chat history with {len(state.chat_history)} messages")
                    messages = state.chat_history

            # Convert messages to dicts for state storage
            message_dicts = [{
                'type': msg.__class__.__name__.lower().replace('message', ''),
                'content': msg.content,
                '_type': msg.__class__.__name__
            } for msg in messages]

            # Store messages as dicts in state - they'll be converted back to objects when needed
            return self.GraphState(
                **{k: v for k, v in state.model_dump().items() if k != 'messages'},
                messages=message_dicts
            )

        return llm_request

    def get_parser_node(self):
        """Node that handles parsing the completion."""
        parser = self.ClassificationOutputParser(
            valid_classes=self.parameters.valid_classes,
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
            
            return self.GraphState(
                **{k: v for k, v in state.model_dump().items() if k not in ['classification', 'explanation']},
                classification=result['classification'],
                explanation=result['explanation']
            )

        return parse_completion

    def get_retry_node(self):
        """Node that prepares for retry by updating chat history."""
        async def prepare_retry(state):
            logging.info("<*> Entering prepare_retry node")
            if isinstance(state, dict):
                state = self.GraphState(**state)
            
            valid_classes_str = "', '".join(self.parameters.valid_classes)
            retry_message = HumanMessage(content=(
                f"You responded with an invalid classification. "
                f"Please classify as one of: '{valid_classes_str}'. "
                f"This is attempt {state.retry_count + 1} "
                f"of {self.parameters.maximum_retry_count}."
            ))
            
            logging.info(f"Preparing retry attempt {state.retry_count + 1}")
            logging.debug(f"Retry message: {retry_message}")
            
            chat_history = state.chat_history if state.chat_history else []
            
            # Convert existing chat history to LangChain objects if needed
            converted_history = []
            for msg in chat_history:
                if isinstance(msg, dict):
                    msg_type = msg.get('type', '').lower()
                    if msg_type == 'human':
                        converted_history.append(HumanMessage(content=msg['content']))
                    elif msg_type == 'ai':
                        converted_history.append(AIMessage(content=msg['content']))
                    elif msg_type == 'system':
                        converted_history.append(SystemMessage(content=msg['content']))
                    else:
                        converted_history.append(BaseMessage(content=msg['content']))
                else:
                    converted_history.append(msg)
            
            # Convert all messages back to dictionaries for state storage
            message_dicts = [{
                'type': msg.__class__.__name__.lower().replace('message', ''),
                'content': msg.content,
                '_type': msg.__class__.__name__
            } for msg in [*converted_history, retry_message]]
            
            # Store messages as dicts in state
            new_state = self.GraphState(
                chat_history=message_dicts,
                retry_count=state.retry_count + 1,
                **{k: v for k, v in state.model_dump().items() 
                   if k not in ['chat_history', 'retry_count']}
            )
            
            logging.info(f"Final state after retry preparation: {new_state}")
            return new_state

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
        async def handle_max_retries(state: self.GraphState) -> self.GraphState:
            logging.info("<*> Entering handle_max_retries node")
            logging.info("Setting classification to 'unknown' due to max retries")
            state_dict = state.model_dump()
            state_dict['classification'] = 'unknown'
            state_dict['explanation'] = 'Maximum retries reached'
            logging.info(f"Final state after max retries: {state_dict}")
            return self.GraphState(**state_dict)
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
                return state

            # Check if batching is enabled globally and for this score
            batching_enabled = os.getenv('PLEXUS_ENABLE_BATCHING', '').lower() == 'true'
            score_batch_enabled = self.batch
            
            if batching_enabled and score_batch_enabled:
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
                
                # Convert dict messages back to LangChain objects if needed
                messages = state['messages']
                if messages and isinstance(messages[0], dict):
                    messages = []
                    for msg in state['messages']:
                        msg_type = msg.get('type', '').lower()
                        if msg_type == 'human':
                            messages.append(HumanMessage(content=msg['content']))
                        elif msg_type == 'ai':
                            messages.append(AIMessage(content=msg['content']))
                        elif msg_type == 'system':
                            messages.append(SystemMessage(content=msg['content']))
                        else:
                            messages.append(BaseMessage(content=msg['content']))
                
                logging.info("Preparing to make LLM API call")
                completion = await model.ainvoke(messages)
                logging.info("LLM call completed")
                logging.info(f"LLM response: {completion.content}")
                
                # Return state with messages preserved
                return self.GraphState(
                    **{k: v for k, v in state.items() if k not in ['messages', 'completion', 'at_llm_breakpoint']},
                    messages=[{
                        'type': msg.__class__.__name__.lower().replace('message', ''),
                        'content': msg.content,
                        '_type': msg.__class__.__name__
                    } for msg in messages],
                    completion=completion.content,
                    at_llm_breakpoint=False
                )
                
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

    def llm_request(self, state):
        prompt_templates = self.get_prompt_templates()
        if not prompt_templates:
            return state

        initial_prompt = prompt_templates[0]
        messages = initial_prompt.format_prompt().to_messages()
        
        # Convert LangChain messages to dictionaries for state storage
        message_dicts = [{
            'type': msg.__class__.__name__.lower().replace('message', ''),
            'content': msg.content,
            '_type': msg.__class__.__name__
        } for msg in messages]
        
        return {
            **state.dict(),
            "messages": message_dicts
        }

    def llm_call(self, state):
        if not state.messages:
            return state

        model = self.model
        response = model.invoke(state.messages)
        
        return {
            **state.dict(),
            "completion": response.content,
            "messages": state.messages  # Keep messages for retry scenarios
        }

    async def handle_max_retries(self, state: GraphState) -> GraphState:
        self.logger.info("<*> Entering handle_max_retries node")
        self.logger.info("Setting classification to 'unknown' due to max retries")
        state_dict = state.model_dump()
        state_dict['classification'] = 'unknown'
        state_dict['explanation'] = 'Maximum retries reached'
        self.logger.info(f"Final state after max retries: {state_dict}")
        return self.GraphState(**state_dict)