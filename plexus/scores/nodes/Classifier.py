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
import uuid

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
            default=6,
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

        def find_matches_in_text(self, text: str) -> List[Tuple[str, int, int, int]]:
            """Find all matches in text with their line and position.
            Returns list of tuples: (valid_class, line_number, position, original_index)
            """
            matches = []
            lines = text.strip().split('\n')
            
            # First normalize all valid classes (do this once)
            normalized_classes = [(vc, self.normalize_text(vc), i) for i, vc in enumerate(self.valid_classes)]
            
            # Sort by appropriate strategy:
            # 1. For parse_from_start=True: use original order, but handle exact same match text
            # 2. For parse_from_start=False: sort by length (descending) to prioritize specific classes
            if self.parse_from_start:
                # When parsing from start, maintain original order
                # (Already in original order, so no sorting needed)
                pass
            else:
                # When parsing from end, sort by length to handle overlapping terms
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
                            # Check for already matched terms that completely contain this match
                            conflict = False
                            if not self.parse_from_start:
                                for m_class, m_line, m_pos, m_idx in matches:
                                    m_norm = self.normalize_text(m_class)
                                    # If they're on the same line and there's an overlap
                                    if (m_line == line_idx and 
                                        m_pos <= pos < m_pos + len(m_norm) and 
                                        len(m_norm) > len(normalized_class)):
                                        # Longer match takes precedence
                                        conflict = True
                                        break
                            
                            if not conflict:
                                # Store match
                                matches.append((original_class, line_idx, pos, original_idx))
                            
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
                # When parsing from end, sort by position (line and column) in reverse
                # For substring conflicts, we already handled this in find_matches_in_text
                matches.sort(key=lambda x: (x[1], x[2]), reverse=True)
                return matches[0][0]  # Return the original class name

        def parse(self, output: str) -> Dict[str, Any]:
            # Find all matches in the text
            matches = self.find_matches_in_text(output)
            
            # Select the appropriate match
            selected_class = self.select_match(matches, output)
            
            # Only return a classification if it's actually one of the valid classes
            # This allows the retry logic to work properly when invalid responses are received
            if selected_class is not None and selected_class in self.valid_classes:
                classification = selected_class
            else:
                classification = None
            
            # Extract explanation from the full output text
            # The explanation should be the entire output, not just the classification
            explanation = output.strip() if output else (classification or "No classification found")
            
            return {
                "classification": classification,
                "explanation": explanation
            }

    def get_llm_prompt_node(self):
        """Node that only handles the LLM request."""
        model = self.model
        prompt_templates = self.get_prompt_templates()

        async def llm_request(state):
            logging.info(f"→ {self.node_name}: Preparing LLM request")
            
            # Keep state as GraphState object to preserve Message types
            if isinstance(state, dict):
                state = self.GraphState(**state)
            
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
                **{k: v for k, v in state.model_dump().items() if k not in ['messages', 'completion', 'chat_history']},
                messages=message_dicts,
                chat_history=state.chat_history if hasattr(state, 'chat_history') else [],
                completion=None  # Always start with no completion
            )

        return llm_request

    def get_parser_node(self):
        """Node that handles parsing the completion."""
        parser = self.ClassificationOutputParser(
            valid_classes=self.parameters.valid_classes,
            parse_from_start=self.parameters.parse_from_start
        )

        async def parse_completion(state):
            logging.info(f"→ {self.node_name}: Parsing LLM response")
            if isinstance(state, dict):
                state = self.GraphState(**state)
            
            logging.info(f"  - Input state completion for {self.node_name}: {state.completion!r}")

            if state.completion is None:
                logging.info(f"  ⚠ {self.node_name}: No completion to parse")
                return state
            
            result = parser.parse(state.completion)
            logging.info(f"  - Parser result for {self.node_name}: {result}")

            if result['classification']:
                logging.info(f"  ✓ {self.node_name}: {result['classification']}")
            else:
                logging.info(f"  ⚠ {self.node_name}: Could not parse classification")
            
            new_state = self.GraphState(
                **{k: v for k, v in state.model_dump().items() if k not in ['classification', 'explanation']},
                classification=result['classification'],
                explanation=result['explanation']
            )

            # Enhanced debugging for classification setting
            logging.info(f"🔍 CLASSIFICATION SETTING DEBUG for {self.node_name}:")
            logging.info(f"  - Setting classification to: {result['classification']!r}")
            logging.info(f"  - Setting explanation to: {result['explanation']!r}")
            logging.info(f"  - Output state classification: {new_state.classification!r}")
            logging.info(f"  - Output state type: {type(new_state)}")
            logging.info(f"  - Output state has classification attr: {hasattr(new_state, 'classification')}")
            
            # Also log to trace for debugging
            output_state = {
                "classification": result['classification'],
                "explanation": result['explanation']
            }
            
            # Log the state and get a new state object with updated node_results
            final_state = self.log_state(new_state, None, output_state)
            
            logging.info(f"  - Final state classification: {final_state.classification!r}")
            logging.info(f"  - Final state type: {type(final_state)}")
            
            return final_state

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
                **{k: v for k, v in state.model_dump().items() 
                   if k not in ['chat_history', 'retry_count', 'completion', 'messages']}
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
            
        # Clear completion when we need to retry
        logging.info("No valid classification, clearing completion and retrying")
        state.completion = None
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
        # Add all nodes
        workflow.add_node("llm_prompt", self.get_llm_prompt_node())
        workflow.add_node("llm_call", self.get_llm_call_node())
        workflow.add_node("parse", self.get_parser_node())
        workflow.add_node("retry", self.get_retry_node())
        workflow.add_node("max_retries", self.get_max_retries_node())

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
        workflow.add_edge("llm_call", "parse")
        workflow.add_edge("retry", "llm_prompt")
        workflow.add_edge("max_retries", END)
        
        # Set entry point
        workflow.set_entry_point("llm_prompt")
        
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