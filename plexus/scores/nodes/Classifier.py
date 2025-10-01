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
        confidence: bool = False

    class GraphState(BaseNode.GraphState):
        reasoning: Optional[str] = None  # Store reasoning content from gpt-oss models
        confidence: Optional[float] = None
        raw_logprobs: Optional[Dict] = None

    def __init__(self, **parameters):
        # Store raw parameters for access to calibration config
        self._raw_parameters = dict(parameters)

        # Extract batch parameter before passing to super
        self.batch = parameters.pop('batch', False)
        super().__init__(**parameters)
        self.parameters = Classifier.Parameters(**parameters)
        self.model = self._initialize_model()

        # If confidence is enabled, bind logprobs to OpenAI models
        if self.parameters.confidence:
            self.model = self._configure_model_for_confidence()

    def _is_openai_model(self) -> bool:
        """Check if the current model is an OpenAI model that supports logprobs."""
        from langchain_openai import ChatOpenAI, AzureChatOpenAI
        from langchain_core.runnables import RunnableBinding
        from unittest.mock import Mock, AsyncMock, MagicMock

        def _get_underlying_model(model, max_depth=10):
            """Recursively unwrap RunnableBinding and similar wrappers to find the actual model."""
            if max_depth <= 0:
                # Prevent infinite recursion
                return model

            # Handle mocks - assume they're OpenAI models for testing
            if isinstance(model, (Mock, AsyncMock, MagicMock)):
                return model

            if isinstance(model, RunnableBinding):
                return _get_underlying_model(model.bound, max_depth - 1)
            elif hasattr(model, 'bound') and not isinstance(model, (Mock, AsyncMock, MagicMock)):
                return _get_underlying_model(model.bound, max_depth - 1)
            elif hasattr(model, 'runnable') and not isinstance(model, (Mock, AsyncMock, MagicMock)):
                return _get_underlying_model(model.runnable, max_depth - 1)
            else:
                return model

        underlying_model = _get_underlying_model(self.model)

        # For mocks, assume they're OpenAI models (for testing)
        if isinstance(underlying_model, (Mock, AsyncMock, MagicMock)):
            return True

        return isinstance(underlying_model, (ChatOpenAI, AzureChatOpenAI))

    def _configure_model_for_confidence(self):
        """Configure the model to return logprobs if it's an OpenAI model."""
        if self._is_openai_model():
            logging.info(f"Configuring OpenAI model for confidence with logprobs")
            # Bind logprobs parameters to the model
            return self.model.bind(logprobs=True, top_logprobs=10)
        else:
            logging.info(f"Model {type(self.model)} does not support confidence - feature disabled")
            return self.model

    def _extract_logprobs(self, response) -> Optional[Dict]:
        """Extract logprobs from OpenAI response."""
        try:
            logging.info(f"🔍 EXTRACTING LOGPROBS:")
            logging.info(f"   Response type: {type(response)}")
            logging.info(f"   Response has response_metadata: {hasattr(response, 'response_metadata')}")
            logging.info(f"   Response has additional_kwargs: {hasattr(response, 'additional_kwargs')}")

            # Check response_metadata for logprobs
            if hasattr(response, 'response_metadata') and response.response_metadata:
                logging.info(f"   response_metadata keys: {list(response.response_metadata.keys())}")

                # First check if logprobs are directly in response_metadata
                direct_logprobs = response.response_metadata.get('logprobs')
                logging.info(f"   Direct logprobs in response_metadata: {direct_logprobs is not None}")

                if direct_logprobs:
                    logging.info(f"✅ Extracted logprobs directly from response_metadata: {str(direct_logprobs)[:300]}")
                    return direct_logprobs

                # Fallback: check for choices structure (older format)
                choices = response.response_metadata.get('choices', [])
                logging.info(f"   Found {len(choices)} choices in response_metadata")

                if choices and len(choices) > 0:
                    choice = choices[0]
                    logging.info(f"   First choice keys: {list(choice.keys()) if isinstance(choice, dict) else 'Not a dict'}")
                    logprobs = choice.get('logprobs')
                    logging.info(f"   logprobs in first choice: {logprobs is not None}")

                    if logprobs:
                        logging.info(f"✅ Extracted logprobs from response_metadata choices: {str(logprobs)[:300]}")
                        return logprobs

            # Alternative path - check for logprobs in different structure
            if hasattr(response, 'additional_kwargs'):
                logging.info(f"   additional_kwargs keys: {list(response.additional_kwargs.keys())}")
                logprobs = response.additional_kwargs.get('logprobs')
                if logprobs:
                    logging.info(f"✅ Extracted logprobs from additional_kwargs: {str(logprobs)[:300]}")
                    return logprobs

            # Check if logprobs are directly on the response
            if hasattr(response, 'logprobs'):
                logging.info(f"   Direct logprobs attribute: {response.logprobs is not None}")
                if response.logprobs:
                    logging.info(f"✅ Extracted logprobs from direct attribute: {str(response.logprobs)[:300]}")
                    return response.logprobs

            logging.warning("❌ No logprobs found in any expected location")

            # Debug: Show what's actually in the response
            logging.info(f"🔍 RESPONSE DEBUG:")
            if hasattr(response, '__dict__'):
                response_attrs = [attr for attr in dir(response) if not attr.startswith('_')]
                logging.info(f"   Response attributes: {response_attrs}")

            return None

        except Exception as e:
            logging.error(f"❌ Error extracting logprobs: {e}")
            import traceback
            logging.error(f"   Traceback: {traceback.format_exc()}")
            return None

    def get_confidence_node(self):
        """Node that calculates confidence from token logprobs at the classification position."""
        parser = self.ClassificationOutputParser(
            valid_classes=self.parameters.valid_classes,
            parse_from_start=self.parameters.parse_from_start
        )

        async def calculate_confidence(state):
            logging.info(f"🎯 → {self.node_name}: ENTERING confidence calculation node")
            logging.info(f"   State type: {type(state)}")
            if isinstance(state, dict):
                logging.info(f"   Converting dict state to GraphState")
                state = self.GraphState(**state)

            logging.info(f"   State has raw_logprobs: {state.raw_logprobs is not None}")
            logging.info(f"   Raw logprobs preview: {str(state.raw_logprobs)[:200] if state.raw_logprobs else 'None'}")

            if not state.raw_logprobs:
                logging.warning("❌ No raw_logprobs available for confidence calculation")
                state.confidence = None
                return state

            if not state.classification:
                logging.warning("❌ No classification available for confidence calculation")
                state.confidence = None
                return state

            if not state.completion:
                logging.warning("❌ No completion text available for confidence calculation")
                state.confidence = None
                return state

            try:
                # Find the token position that contains the parsed classification
                token_position = self._find_classification_token_position(
                    state.completion,
                    state.classification,
                    state.raw_logprobs,
                    parser
                )

                if token_position is None:
                    logging.warning(f"❌ Could not find token position for classification '{state.classification}'")
                    state.confidence = None
                    return state

                logging.info(f"   Found classification '{state.classification}' at token position {token_position}")

                # Calculate confidence using logprobs at that specific token position
                confidence_score = self._calculate_confidence_at_token_position(
                    token_position,
                    state.classification,
                    state.raw_logprobs,
                    parser
                )

                logging.info(f"🎯 CONFIDENCE CALCULATION COMPLETE:")
                logging.info(f"   Token position: {token_position}")
                logging.info(f"   Raw confidence score: {confidence_score}")

                # Apply calibration if available in the node configuration
                calibrated_confidence = self._apply_confidence_calibration(confidence_score)

                if calibrated_confidence != confidence_score:
                    logging.info(f"   Applied calibration: {confidence_score:.6f} -> {calibrated_confidence:.6f}")
                    logging.info(f"   Raw confidence preserved, final confidence calibrated")
                else:
                    logging.info(f"   No calibration applied - using raw confidence")

                logging.info(f"   Setting state.confidence = {calibrated_confidence}")
                state.confidence = calibrated_confidence

                # Verify state update
                logging.info(f"   Verified state.confidence = {state.confidence}")
                logging.info(f"   State type: {type(state)}")
                logging.info(f"   State keys: {list(state.model_dump().keys()) if hasattr(state, 'model_dump') else 'No model_dump method'}")

                # Create return state dict to ensure confidence is included
                return_state = state.model_dump() if hasattr(state, 'model_dump') else state
                logging.info(f"🎯 RETURNING STATE WITH CONFIDENCE:")
                logging.info(f"   return_state['confidence'] = {return_state.get('confidence') if isinstance(return_state, dict) else 'N/A'}")
                logging.info(f"   return_state type: {type(return_state)}")

                return return_state

            except Exception as e:
                logging.error(f"Error calculating confidence: {e}")
                state.confidence = None
                return state

        return calculate_confidence

    def _find_classification_token_position(self, completion_text, classification, raw_logprobs, parser) -> Optional[int]:
        """Find which token position contains the parsed classification.

        Args:
            completion_text: The full response text from the LLM
            classification: The classification found by string-based parsing
            raw_logprobs: The raw logprobs data from OpenAI
            parser: The parser instance (for parse_from_start setting)

        Returns:
            Token position (0-based index) or None if not found
        """
        import math

        content = raw_logprobs.get('content', [])
        if not content:
            logging.warning("No content in raw_logprobs for token position search")
            return None

        logging.info(f"   Searching for classification '{classification}' in {len(content)} tokens")
        logging.info(f"   Parse from start: {parser.parse_from_start}")
        logging.info(f"   Completion text: '{completion_text}'")

        # Normalize the classification for comparison
        normalized_classification = parser.normalize_text(classification)

        # Build candidate positions by reconstructing text token by token
        candidate_positions = []
        accumulated_text = ""

        for token_idx, token_data in enumerate(content):
            token = token_data.get('token', '')
            accumulated_text += token

            logging.info(f"   Token {token_idx}: '{token}' -> accumulated: '{accumulated_text}'")

            # Check if any token alternative at this position matches our classification
            top_logprobs = token_data.get('top_logprobs', [])
            for logprob_entry in top_logprobs:
                candidate_token = logprob_entry.get('token', '')
                normalized_candidate = parser.normalize_text(candidate_token)

                if normalized_candidate == normalized_classification:
                    candidate_positions.append(token_idx)
                    logging.info(f"   Found potential match at position {token_idx}: token '{candidate_token}' matches '{classification}'")
                    break  # Found a match at this position, move to next token

        if not candidate_positions:
            logging.warning(f"No token positions found containing classification '{classification}'")
            return None

        # Choose position based on parse_from_start setting
        if parser.parse_from_start:
            chosen_position = candidate_positions[0]  # First occurrence
            logging.info(f"   Using first occurrence at position {chosen_position} (parse_from_start=True)")
        else:
            chosen_position = candidate_positions[-1]  # Last occurrence
            logging.info(f"   Using last occurrence at position {chosen_position} (parse_from_start=False)")

        return chosen_position

    def _calculate_confidence_at_token_position(self, token_position, predicted_class, raw_logprobs, parser) -> Optional[float]:
        """Calculate confidence using logprobs at the specific token position.

        Args:
            token_position: The token index (0-based) containing the classification
            predicted_class: The classification class to calculate confidence for
            raw_logprobs: The raw logprobs data from OpenAI
            parser: The parser instance (for text normalization)

        Returns:
            Confidence score (0.0 to 1.0) or None if calculation fails
        """
        import math

        content = raw_logprobs.get('content', [])
        if token_position >= len(content):
            logging.error(f"Token position {token_position} exceeds content length {len(content)}")
            return None

        token_data = content[token_position]
        top_logprobs = token_data.get('top_logprobs', [])

        if not top_logprobs:
            logging.warning(f"No top_logprobs at token position {token_position}")
            return None

        # Normalize the predicted class for comparison
        normalized_predicted_class = parser.normalize_text(predicted_class)

        logging.info(f"   Calculating confidence at token position {token_position}")
        logging.info(f"   Predicted class: '{predicted_class}' (normalized: '{normalized_predicted_class}')")
        logging.info(f"   Analyzing {len(top_logprobs)} token alternatives")

        # First pass: calculate all probabilities
        token_analysis = []
        for i, logprob_entry in enumerate(top_logprobs):
            token = logprob_entry.get('token', '')
            logprob = logprob_entry.get('logprob', float('-inf'))
            probability = math.exp(logprob) if logprob != float('-inf') else 0.0
            normalized_token = parser.normalize_text(token)

            token_analysis.append({
                'rank': i + 1,
                'token': token,
                'normalized_token': normalized_token,
                'logprob': logprob,
                'probability': probability,
                'percentage': probability * 100
            })

        # Display complete token probability table
        logging.info(f"🔍 COMPLETE TOKEN PROBABILITY BREAKDOWN:")
        logging.info(f"     {'Rank':<4} {'Token':<15} {'Normalized':<15} {'Probability':<15} {'Percentage':<15}")
        logging.info(f"     {'-'*4:<4} {'-'*15:<15} {'-'*15:<15} {'-'*15:<15} {'-'*15:<15}")

        for analysis in token_analysis:
            logging.info(f"     {analysis['rank']:<4} {repr(analysis['token']):<15} {repr(analysis['normalized_token']):<15} {analysis['probability']:<15.12f} {analysis['percentage']:<15.10f}%")

        total_probability = 0.0
        found_matches = False

        # Second pass: find matches and sum probabilities
        for analysis in token_analysis:
            if analysis['normalized_token'] == normalized_predicted_class:
                total_probability += analysis['probability']
                found_matches = True
                logging.info(f"       ✓ MATCH! Token '{analysis['token']}' matches predicted class - adding {analysis['percentage']:.10f}% to confidence")

        if not found_matches:
            logging.warning(f"No token alternatives matched predicted class '{predicted_class}' at position {token_position}")
            return None

        # Ensure probability is between 0 and 1
        total_probability = min(1.0, max(0.0, total_probability))

        logging.info(f"🎯 CONFIDENCE CALCULATION RESULT:")
        logging.info(f"     Token position: {token_position}")
        logging.info(f"     Predicted class: '{predicted_class}'")
        logging.info(f"     Found matching tokens: {found_matches}")
        logging.info(f"     Final confidence score: {total_probability:.15f}")
        logging.info(f"     Final confidence percentage: {total_probability * 100:.12f}%")
        return total_probability

    def _apply_confidence_calibration(self, raw_confidence: float) -> float:
        """
        Apply confidence calibration if available in the node configuration.

        Args:
            raw_confidence: Raw confidence score from logprobs

        Returns:
            Calibrated confidence score, or raw confidence if no calibration available
        """
        try:
            # Check if calibration data is available in the node configuration
            calibration_config = None

            # First check direct attribute
            if hasattr(self, 'confidence_calibration'):
                calibration_config = getattr(self, 'confidence_calibration')

            # Then check in parameters object attributes
            if not calibration_config and hasattr(self, 'parameters'):
                if hasattr(self.parameters, 'confidence_calibration'):
                    calibration_config = getattr(self.parameters, 'confidence_calibration')

            # Finally check in the raw parameters dict passed to __init__
            if not calibration_config and hasattr(self, '_raw_parameters'):
                calibration_config = self._raw_parameters.get('confidence_calibration')

            if not calibration_config:
                logging.debug("No confidence calibration data found - using raw confidence")
                return raw_confidence

            # Apply calibration using the serialized calibration data
            from plexus.confidence_calibration import apply_calibration_from_serialized
            calibrated_confidence = apply_calibration_from_serialized(raw_confidence, calibration_config)

            return calibrated_confidence

        except Exception as e:
            logging.warning(f"Error applying confidence calibration: {e}")
            return raw_confidence

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
                
                # Convert dict messages back to LangChain objects if needed, filtering out empty messages
                chat_messages = []
                for msg in state.chat_history:
                    # Skip messages with empty or whitespace-only content
                    if isinstance(msg, dict):
                        content = msg.get('content', '')
                        if not content or not content.strip():
                            continue
                        
                        msg_type = msg.get('type', '').lower()
                        if msg_type == 'human':
                            chat_messages.append(HumanMessage(content=content))
                        elif msg_type == 'ai':
                            chat_messages.append(AIMessage(content=content))
                        elif msg_type == 'system':
                            chat_messages.append(SystemMessage(content=content))
                        else:
                            chat_messages.append(BaseMessage(content=content))
                    else:
                        # For non-dict messages, check content attribute
                        content = getattr(msg, 'content', '')
                        if not content or not content.strip():
                            continue
                        chat_messages.append(msg)
                
                # Get the initial system and human messages from prompt template
                prompt = prompt_templates[0].format_prompt(**state.model_dump())
                initial_messages = prompt.to_messages()[:2]  # Only take system and first human message
                
                # Combine messages in the correct order:
                # 1. System message from initial_messages[0]
                # 2. Original human message from initial_messages[1]
                # 3. All chat history messages in order
                messages = initial_messages + chat_messages
                
                # Check for empty message content in retry flow too
                for i, msg in enumerate(messages):
                    if not msg.content or not msg.content.strip():
                        raise ValueError(f"Retry message {i} has empty content")
                
                # Log the final message sequence
                logging.info("Final message sequence:")
                for i, msg in enumerate(messages):
                    logging.info(f"Message {i}: type={type(msg)}, content={msg.content}")
            # Otherwise build new messages from prompt template
            else:
                logging.info("Building new messages from prompt template")
                try:
                    state_dict = state.model_dump()
                    prompt = prompt_templates[0].format_prompt(**state_dict)
                    messages = prompt.to_messages()
                    
                    # Check for empty message content
                    for i, msg in enumerate(messages):
                        if not msg.content or not msg.content.strip():
                            raise ValueError(f"Message {i} has empty content")
                    
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

            if state.completion is None or state.completion.strip() == "":
                logging.info(f"  ⚠ {self.node_name}: No completion to parse")
                # Return state with None classification to trigger retry logic
                state.classification = None
                state.explanation = "No completion received from LLM"
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
            
            # Include reasoning for gpt-oss models
            if hasattr(state, 'reasoning') and state.reasoning:
                output_state["reasoning"] = state.reasoning
            
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

        # Check if this node produced a valid classification
        # We need to check both classification and completion to ensure this node succeeded
        has_valid_classification = (
            state.classification is not None and
            state.classification in self.parameters.valid_classes and
            state.completion is not None and
            state.completion.strip() != ""
        )

        if has_valid_classification:
            if self.parameters.confidence:
                logging.info(f"Classification found: {state.classification}, proceeding to confidence")
                return "calculate_confidence"
            else:
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
                    
                    # Normalize completion text (handles Responses API content blocks)
                    completion_text = self.normalize_text_output(response)

                    # Extract reasoning content for gpt-oss models
                    reasoning_content = ""
                    if self.is_gpt_oss_model():
                        reasoning_content = self.extract_reasoning_content(response)

                    # Extract logprobs for confidence calculation if enabled
                    raw_logprobs = None
                    if self.parameters.confidence and self._is_openai_model():
                        raw_logprobs = self._extract_logprobs(response)

                    # Create the initial result state
                    result_state = self.GraphState(
                        **{k: v for k, v in state.model_dump().items() if k not in ['completion', 'reasoning', 'raw_logprobs']},
                        completion=completion_text,
                        reasoning=reasoning_content if reasoning_content else None,
                        raw_logprobs=raw_logprobs
                    )
                    
                    return result_state

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

        # Add confidence node if enabled
        if self.parameters.confidence:
            workflow.add_node("calculate_confidence", self.get_confidence_node())

        # Add conditional edges for parse
        if self.parameters.confidence:
            # When confidence is enabled, parse goes to confidence first
            workflow.add_conditional_edges(
                "parse",
                self.should_retry,
                {
                    "retry": "retry",
                    "calculate_confidence": "calculate_confidence",  # Go to confidence when successful
                    "max_retries": "max_retries"
                }
            )
            # Confidence node then goes to end
            workflow.add_edge("calculate_confidence", END)
        else:
            # Normal flow without confidence
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
        completion_text = self.normalize_text_output(response)
        
        return {
            **state.dict(),
            "completion": completion_text,
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