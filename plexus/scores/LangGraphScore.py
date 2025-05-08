import os
import logging
import traceback
import graphviz
from types import FunctionType
from typing import Type, Tuple, Literal, Optional, Any, TypedDict, List, Dict, Union
from pydantic import BaseModel, ConfigDict, create_model, Field
import concurrent.futures
import importlib
import asyncio
from os import getenv
from dotenv import load_dotenv
import json
import warnings
from functools import partialmethod
import inspect  # Ensure inspect is imported at the top
import uuid # Add this import

from plexus.LangChainUser import LangChainUser
from plexus.scores.Score import Score
from plexus.utils.dict_utils import truncate_dict_strings

from langchain_community.callbacks import OpenAICallbackHandler

from langgraph.graph import StateGraph, END

from openai_cost_calculator.openai_cost_calculator import calculate_cost

from langchain.globals import set_debug, set_verbose
if os.getenv('DEBUG'):
    set_debug(True)
else:
    set_debug(False)
    set_verbose(False)

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver, CheckpointMetadata
from langgraph.checkpoint.base import Checkpoint
import types

from langgraph.errors import NodeInterrupt
from plexus.dashboard.api.client import PlexusDashboardClient
from plexus.dashboard.api.models.account import Account
from plexus.dashboard.api.models.scoring_job import ScoringJob

from plexus.utils.dict_utils import truncate_dict_strings
class BatchProcessingPause(Exception):
    """Exception raised when execution should pause for batch processing."""
    def __init__(self, thread_id, state, batch_job_id=None, message=None):
        self.thread_id = thread_id
        self.state = state
        self.batch_job_id = batch_job_id
        self.message = message or f"Execution paused for batch processing. Thread ID: {thread_id}"
        super().__init__(self.message)

# Temporarily suppress the specific Pydantic warning about protected namespaces
warnings.filterwarnings("ignore", 
    message="Field \"model_.*\" .* has conflict with protected namespace \"model_\".*")

# Custom Checkpointer with detailed logging on serialization error
class LoggingAsyncPostgresSaver(AsyncPostgresSaver):

    @staticmethod
    def _find_unserializable(obj, path=""):
        """Recursively find the first unserializable object (method/function/callable) in a nested structure."""
        if isinstance(obj, (types.MethodType, types.FunctionType, types.LambdaType)) or callable(obj):
            try:
                # Try to get a meaningful name
                name = getattr(obj, '__qualname__', str(obj))
                return path, f"<callable: {name}>"
            except Exception:
                return path, "<callable: unknown>"
        elif isinstance(obj, dict):
            for k, v in obj.items():
                found_path, found_val = LoggingAsyncPostgresSaver._find_unserializable(v, path=f"{path}['{k}']")
                if found_path:
                    return found_path, found_val
        elif isinstance(obj, (list, tuple)):
            for i, item in enumerate(obj):
                found_path, found_val = LoggingAsyncPostgresSaver._find_unserializable(item, path=f"{path}[{i}]")
                if found_path:
                    return found_path, found_val
        # Add checks for other known complex types if necessary
        return None, None

    async def aput(
        self, 
        config: CheckpointMetadata, 
        checkpoint: Checkpoint, 
        metadata: CheckpointMetadata, 
        new_versions: Optional[Dict[str, int]] = None
    ) -> CheckpointMetadata:
        """Save checkpoint to DB, logging unserializable data on TypeError."""
        try:
            # Log the state *before* attempting serialization
            logging.debug(f"[Checkpointer] Pre-serialization checkpoint for thread_id: {config['configurable']['thread_id']}")
            # Use truncate_dict_strings for potentially large state
            logging.debug(f"[Checkpointer] Checkpoint data (pre-serialization, truncated): {truncate_dict_strings(checkpoint, 150)}")
            
            # --- Add safety net: Ensure checkpoint is serializable ---
            try:
                logging.debug("[Checkpointer] Applying _ensure_serializable safeguard...")
                # Use the utility function defined within LangGraphScore scope
                serializable_checkpoint = _ensure_serializable(checkpoint)
                logging.debug("[Checkpointer] _ensure_serializable safeguard applied.")
                logging.debug(f"[Checkpointer] Checkpoint data (post-serialization safeguard, truncated): {truncate_dict_strings(serializable_checkpoint, 150)}")
            except Exception as e_ensure:
                logging.error(f"[Checkpointer] Error applying _ensure_serializable: {e_ensure}", exc_info=True)
                # Fallback to original checkpoint if safeguard fails
                serializable_checkpoint = checkpoint
            # --- End safety net ---

            # Directly call the superclass method which handles the internal logic including _dump_blobs
            logging.debug(f"[Checkpointer] Attempting to save checkpoint for thread_id: {config['configurable']['thread_id']}")
            # Use the potentially modified checkpoint
            result = await super().aput(config, serializable_checkpoint, metadata, new_versions)
            logging.debug(f"[Checkpointer] Successfully saved checkpoint for thread_id: {config['configurable']['thread_id']}")
            return result
        except (TypeError, OverflowError) as e:
            logging.error(f"[Checkpointer] Serialization failed during aput: {e}", exc_info=True)
            try:
                # Attempt to find the specific problematic part of the checkpoint
                problem_path, problem_value = self._find_unserializable(checkpoint)
                if problem_path:
                    logging.error(f"[Checkpointer] Found potentially unserializable object at path: {problem_path}")
                    logging.error(f"[Checkpointer] Value (representation): {problem_value}")
                else:
                    logging.error("[Checkpointer] Could not pinpoint the exact unserializable object, but error occurred during serialization.")
                # Log the full checkpoint structure (truncated) for context
                logging.error(f"[Checkpointer] Checkpoint structure keys: {list(checkpoint.keys()) if isinstance(checkpoint, dict) else 'N/A'}")
                logging.error(f"[Checkpointer] Checkpoint data (truncated): {truncate_dict_strings(checkpoint, 150)}")

            except Exception as find_err:
                logging.error(f"[Checkpointer] Error while trying to find unserializable object: {find_err}")
            
            # Re-raise the original serialization error
            raise e
        except Exception as e_aput:
            logging.error(f"[Checkpointer] Unexpected error during aput: {e_aput}", exc_info=True)
            raise e_aput

# Utility function to ensure an object is serializable
def _ensure_serializable(obj, _level=0, _current_path="root"):
    _indent = "  " * _level
    # Add import inside function if not at module level
    import inspect
    import json
    import logging # Assuming logging is configured
    from plexus.utils.dict_utils import truncate_dict_strings # Assuming this path is correct

    logging.debug(f"{_indent}ensure_serializable: path='{_current_path}', type='{type(obj)}'")

    if obj is None:
        logging.debug(f"{_indent} -> None")
        return None
    elif isinstance(obj, (str, int, float, bool)):
        # Truncate long strings in debug logs
        log_val = str(obj) if not isinstance(obj, str) else obj
        logging.debug(f"{_indent} -> Basic type: {log_val[:50]}{'...' if len(log_val) > 50 else ''}")
        return obj
    elif inspect.ismethod(obj) or inspect.isfunction(obj) or callable(obj):
        try:
            name = obj.__qualname__ if hasattr(obj, '__qualname__') else str(obj)
            logging.warning(f"{_indent} -> Found callable at path '{_current_path}': {name}. Converting to string representation.")
            return f"<callable: {name}>"
        except Exception as e:
            logging.warning(f"{_indent}Error getting callable name at path '{_current_path}': {e}")
            return "<callable: unknown>"
    elif isinstance(obj, (list, tuple)):
        logging.debug(f"{_indent} -> List/Tuple (len={len(obj)}), processing items...")
        return [_ensure_serializable(item, _level + 1, f"{_current_path}[{i}]") for i, item in enumerate(obj)]
    elif isinstance(obj, dict):
        logging.debug(f"{_indent} -> Dict (keys={list(obj.keys())}), processing items...")
        return {k: _ensure_serializable(v, _level + 1, f"{_current_path}['{k}']") for k, v in obj.items()}
    elif hasattr(obj, '__dict__'):
        logging.debug(f"{_indent} -> Custom object: {obj.__class__.__name__}, processing attributes...")
        try:
            serializable_dict = {
                k: _ensure_serializable(v, _level + 1, f"{_current_path}.{k}")
                for k, v in obj.__dict__.items()
                # Avoid private/protected attributes and callables
                if not k.startswith('_') and not callable(v)
            }
            serializable_dict['__class__'] = obj.__class__.__name__
            logging.debug(f"{_indent} -> Serialized custom object: {list(serializable_dict.keys())}")
            return serializable_dict
        except (TypeError, AttributeError, RecursionError) as e:
             logging.warning(f"{_indent}Could not serialize object attribute for {obj.__class__.__name__} at path '{_current_path}': {e}")
             return f"<object: {obj.__class__.__name__} (serialization error)>"
    else:
        # Add specific handling for common unserializable types if needed
        # E.g., if isinstance(obj, SomeUnserializableType): return repr(obj)
        logging.debug(f"{_indent} -> Fallback attempt for type: {type(obj)}")
        try:
            # Use default=str as a fallback for json.dumps
            json.dumps(obj, default=str) 
            logging.debug(f"{_indent} -> Fallback: Directly JSON serializable (or via str)")
            # If dumps worked with default=str, it might still be problematic for msgpack
            # Let's try returning the string representation for safety
            try:
                s = str(obj)
                logging.debug(f"{_indent} -> Fallback: Returning string representation: {s[:50]}{'...' if len(s) > 50 else ''}")
                return s
            except Exception as e_repr:
                 logging.warning(f"{_indent}Fallback: Could not get string representation at path '{_current_path}': {e_repr}")
                 return f"<unserializable: {type(obj).__name__} (repr error)>"
        except (TypeError, OverflowError) as e_json:
            logging.debug(f"{_indent} -> Fallback: Not directly JSON serializable, even with str. Error: {e_json}")
            try:
                s = str(obj)
                logging.debug(f"{_indent} -> Fallback: Converting to string: {s[:50]}{'...' if len(s) > 50 else ''}")
                return s
            except Exception as e_str:
                logging.warning(f"{_indent}Fallback: Could not convert object of type {type(obj)} to string at path '{_current_path}': {e_str}")
                return f"<unserializable: {type(obj).__name__} (str error)>"

class LangGraphScore(Score, LangChainUser):
    """
    A Score implementation that uses LangGraph for orchestrating LLM-based classification.

    LangGraphScore enables complex classification logic using a graph of LLM operations.
    It provides:
    - Declarative graph definition in YAML
    - State management and checkpointing
    - Cost tracking and optimization
    - Batch processing support
    - Integration with multiple LLM providers

    The graph is defined in the scorecard YAML:
    ```yaml
    scores:
      ComplexScore:
        class: LangGraphScore
        model_provider: AzureChatOpenAI
        model_name: gpt-4
        graph:
          - name: extract_context
            type: prompt
            template: Extract relevant context...
            output: context
          - name: classify
            type: prompt
            template: Based on the context...
            input: context
            output: classification
          - name: validate
            type: condition
            input: classification
            conditions:
              - value: Yes
                goto: explain_yes
              - value: No
                goto: explain_no
    ```

    Common usage patterns:
    1. Basic classification:
        score = LangGraphScore(**config)
        result = await score.predict(context, Score.Input(
            text="content to classify"
        ))

    2. Batch processing:
        async for result in score.batch_predict(texts):
            # Process each result

    3. Cost optimization:
        score.reset_token_usage()
        result = await score.predict(...)
        costs = score.get_accumulated_costs()

    Key features:
    - Graph visualization for debugging
    - Token usage tracking
    - State persistence
    - Error handling and retries
    - Batch processing optimization

    LangGraphScore is commonly used with:
    - Complex classification tasks requiring multiple steps
    - Tasks needing explanation or reasoning
    - High-volume processing requiring cost optimization
    """
    
    class Parameters(Score.Parameters):
        ...
        model_config = ConfigDict(protected_namespaces=())
        model_provider: Literal["ChatOpenAI", "AzureChatOpenAI", "BedrockChat", "ChatVertexAI"] = "AzureChatOpenAI"
        model_name: Optional[str] = None
        model_region: Optional[str] = None
        temperature: Optional[float] = 0
        max_tokens: Optional[int] = 500
        graph: Optional[list[dict]] = None
        input: Optional[dict] = None
        output: Optional[dict] = None
        depends_on: Optional[Union[List[str], Dict[str, Union[str, Dict[str, Any]]]]] = None
        single_line_messages: bool = False
        checkpoint_db_path: Optional[str] = Field(
            default="./.plexus/checkpoints/langgraph.db",
            description="Path to SQLite checkpoint database"
        )
        thread_id: Optional[str] = Field(
            default=None,
            description="Deprecated - thread_id is now automatically set from content_id"
        )
        postgres_url: Optional[str] = Field(
            default=None,
            description="PostgreSQL connection URL for LangGraph checkpoints"
        )

    class Result(Score.Result):
        """
        Model output containing the validation result.

        :param explanation: Detailed explanation of the validation result.
        """
        ...
        explanation: str

    class GraphState(BaseModel):
        text: str
        metadata: Optional[dict] = None
        results: Optional[dict] = None
        messages: Optional[List[Dict[str, Any]]] = Field(
            default=None,
            description="Messages for LLM prompts"
        )
        is_not_empty: Optional[bool] = Field(default=None)
        value: Optional[str] = Field(default=None)
        explanation: Optional[str] = Field(default=None)
        reasoning: Optional[str] = Field(default=None)
        chat_history: List[Any] = Field(default_factory=list)
        completion: Optional[str] = Field(default=None)
        classification: Optional[str] = Field(default=None)
        confidence: Optional[float] = Field(default=None)
        retry_count: Optional[int] = Field(default=0)
        at_llm_breakpoint: Optional[bool] = Field(default=False)
        good_call: Optional[str] = Field(default=None)
        good_call_explanation: Optional[str] = Field(default=None)
        non_qualifying_reason: Optional[str] = Field(default=None)
        non_qualifying_explanation: Optional[str] = Field(default=None)

        model_config = ConfigDict(
            arbitrary_types_allowed=True,
            validate_default=True,
            extra='allow'
        )

    def __init__(self, **parameters):
        """
        Initialize the LangGraphScore.

        This method sets up the score parameters and initializes basic attributes.
        The language model initialization is deferred to the async setup.

        :param parameters: Configuration parameters for the score and language model.
        """
        Score.__init__(self, **parameters)
        self.token_counter = self._create_token_counter()
        self.openai_callback = None
        self.model = None
        self.parameters = self.Parameters(**parameters)
        self.node_instances = []
        self.workflow = None
        self.checkpointer = None
        self.db_connection = None

    async def async_setup(self):
        """Asynchronous setup for LangGraphScore."""
        self.model = await self._ainitialize_model()
        
        # Load environment variables
        load_dotenv('.env', override=True)
        
        # Get PostgreSQL URL from parameters or environment
        db_uri = self.parameters.postgres_url or \
                 os.getenv('PLEXUS_LANGGRAPH_CHECKPOINTER_POSTGRES_URI')
        
        if db_uri:
            logging.info("Using PostgreSQL checkpoint database with Logging Checkpointer")
            # Use the custom Logging Checkpointer
            self._checkpointer_context = LoggingAsyncPostgresSaver.from_conn_string(db_uri)
            # Enter the context and store the checkpointer
            self.checkpointer = await self._checkpointer_context.__aenter__()
            
            # Initialize tables
            logging.info("Setting up checkpointer database tables...")
            await self.checkpointer.setup()
            logging.info("PostgreSQL checkpointer setup complete")
        else:
            logging.info("No PostgreSQL URL provided - running without checkpointing")
            self.checkpointer = None
            self._checkpointer_context = None
        
        # Build workflow with optional checkpointer
        self.workflow = await self.build_compiled_workflow()

    @staticmethod
    def process_node(node_data):
        """Process a single node to build its workflow."""
        node_name, node_instance = node_data
        logging.info(f"Adding node: {node_name}")
        return node_name, node_instance.build_compiled_workflow(
            graph_state_class=LangGraphScore.GraphState
        )

    @staticmethod
    def add_edges(workflow, node_instances, entry_point, graph_config):
        """Add edges between nodes in the workflow."""
        for i, (node_name, _) in enumerate(node_instances):
            if i == 0 and entry_point:
                workflow.add_edge(entry_point, node_name)
            
            if i > 0:
                previous_node = node_instances[i-1][0]
                node_config = next((node for node in graph_config
                                  if node['name'] == previous_node), None)
                
                if node_config:
                    # Handle output field in node config directly - this is critical for node-level output aliasing
                    if 'output' in node_config:
                        value_setter_name = f"{previous_node}_value_setter"
                        workflow.add_node(
                            value_setter_name,
                            LangGraphScore.create_value_setter_node(
                                node_config['output']
                            )
                        )
                        workflow.add_edge(previous_node, value_setter_name)
                        workflow.add_edge(value_setter_name, node_name)
                        continue  # Skip other edge processing for this node
                        
                    # Handle edge clause - direct routing with output aliasing
                    if 'edge' in node_config:
                        edge = node_config['edge']
                        value_setter_name = f"{previous_node}_value_setter"
                        # Create value setter node for the edge
                        workflow.add_node(
                            value_setter_name,
                            LangGraphScore.create_value_setter_node(
                                edge.get('output', {})
                            )
                        )
                        # Add edge from previous node to value setter
                        workflow.add_edge(previous_node, value_setter_name)
                        # Add edge from value setter to target node
                        target_node = edge.get('node', node_name)
                        if target_node == 'END':
                            workflow.add_edge(value_setter_name, END)
                        else:
                            workflow.add_edge(value_setter_name, target_node)
                    
                    # Handle conditions clause - conditional routing
                    elif 'conditions' in node_config:
                        logging.info(f"Node '{previous_node}' has conditions: {node_config['conditions']}")
                        
                        conditions = node_config['conditions']
                        if isinstance(conditions, list):
                            value_setters = {}
                            # Create value setter nodes for each condition
                            for j, condition in enumerate(conditions):
                                value_setter_name = f"{previous_node}_value_setter_{j}"
                                value_setters[condition['value'].lower()] = value_setter_name
                                workflow.add_node(
                                    value_setter_name, 
                                    LangGraphScore.create_value_setter_node(
                                        condition.get('output', {})
                                    )
                                )

                            def create_routing_function(conditions, value_setters, next_node):
                                def routing_function(state):
                                    if hasattr(state, 'classification') and state.classification is not None:
                                        state_value = state.classification.lower()
                                        # Check if we have a value setter for this classification
                                        if state_value in value_setters:
                                            return value_setters[state_value]
                                    # Default case - route to next node
                                    return next_node
                                return routing_function

                            # Create a list of valid targets for conditional edges
                            valid_targets = list(value_setters.values()) + [node_name]
                            
                            # Add conditional routing only to valid targets
                            workflow.add_conditional_edges(
                                previous_node,
                                create_routing_function(conditions, value_setters, node_name),
                                valid_targets
                            )

                            # Add edges from value setters to their target nodes
                            for condition in conditions:
                                value_setter_name = value_setters[condition['value'].lower()]
                                target_node = condition.get('node', node_name)
                                if target_node == 'END':
                                    workflow.add_edge(value_setter_name, END)
                                else:
                                    workflow.add_edge(value_setter_name, target_node)
                        else:
                            logging.error(f"Conditions is not a list: {conditions}")
                            workflow.add_edge(previous_node, node_name)
                    
                    # No edge or conditions clause - add direct edge to next node
                    else:
                        logging.debug(f"Node '{previous_node}' does not have conditions or edge clause")
                        workflow.add_edge(previous_node, node_name)

    async def build_compiled_workflow(self):
        """Build the LangGraph workflow with optional persistence."""
        logging.info("=== Building Workflow ===")
        
        # First collect node instances
        node_instances = []
        if hasattr(self.parameters, 'graph') and isinstance(self.parameters.graph, list):
            for node_configuration_entry in self.parameters.graph:
                logging.debug(f"Processing node configuration: {node_configuration_entry}")
                
                for attribute in ['model_provider', 'model_name', 'model_region', 
                                'temperature', 'max_tokens']:
                    if attribute not in node_configuration_entry:
                        node_configuration_entry[attribute] = getattr(
                            self.parameters, attribute
                        )

                if 'class' in node_configuration_entry and 'name' in node_configuration_entry:
                    node_class_name = node_configuration_entry['class']
                    node_name = node_configuration_entry['name']
                    try:
                        logging.info(f"Attempting to import class: {node_class_name}")
                        node_class = self._import_class(node_class_name)
                        if node_class is None:
                            raise ValueError(f"Could not import class {node_class_name}")
                        
                        node_instance = node_class(**node_configuration_entry)
                        node_instances.append((node_name, node_instance))
                    except Exception as e:
                        logging.error(f"Error creating node instance for {node_class_name}: {str(e)}")
                        logging.error(f"Configuration: {node_configuration_entry}")
                        raise
        else:
            raise ValueError("Invalid or missing graph configuration in parameters.")

        # Create combined state class that includes output aliases
        combined_state_class = self.create_combined_graphstate_class(
            [instance for _, instance in node_instances]
        )
        logging.info(f"Created combined state class: {combined_state_class}")
        logging.info(f"Combined state fields: {combined_state_class.model_fields.keys()}")
        
        # Store the combined state class
        self.combined_state_class = combined_state_class

        try:
            # Use combined state class when creating workflow
            workflow = StateGraph(combined_state_class)

            try:
                # Process nodes - now using combined_state_class
                for node_name, node_instance in node_instances:
                    workflow.add_node(
                        node_name, 
                        node_instance.build_compiled_workflow(
                            graph_state_class=combined_state_class
                        )
                    )
            except Exception as e:
                logging.error(f"Error creating node {node_name}: {str(e)}")
                logging.error(f"Full traceback: {traceback.format_exc()}")
                raise

            # Set entry point to first node
            first_node = node_instances[0][0]
            workflow.set_entry_point(first_node)

            # Add edges using our add_edges method
            LangGraphScore.add_edges(workflow, node_instances, None, self.parameters.graph)

            # Add final node and edge from last node to END
            last_node = node_instances[-1][0]
            
            # Add output aliasing if needed
            if hasattr(self.parameters, 'output') and self.parameters.output is not None:
                logging.info(f"Adding output aliasing node with mapping: {self.parameters.output}")
                output_aliasing_function = LangGraphScore.generate_output_aliasing_function(
                    self.parameters.output
                )
                workflow.add_node('output_aliasing', output_aliasing_function)
                workflow.add_edge(last_node, 'output_aliasing')
                workflow.add_edge('output_aliasing', END)
                logging.info("Added output aliasing node to workflow")
            else:
                workflow.add_edge(last_node, END)
                logging.info("No output aliasing needed, connected last node directly to END")

            logging.info("=== Workflow Build Complete ===")

            # Compile with checkpointer only if configured
            app = workflow.compile(
                checkpointer=self.checkpointer if self.checkpointer else None
            )
            
            # Store node instances for later token usage calculation
            self.node_instances = node_instances
            
            logging.info(f"Created combined state class with fields: {combined_state_class.__annotations__}")
            
            # Store the compiled workflow before trying to visualize it
            self.workflow = app
            
            # Generate and log the graph visualization
            # self.generate_graph_visualization("./tmp/workflow_graph.png")
            
            return app
            
        except Exception as e:
            logging.error(f"Error compiling workflow: {str(e)}")
            logging.error(f"Full traceback: {traceback.format_exc()}")
            raise

    @classmethod
    async def create(cls, **parameters):
        instance = cls(**parameters)
        await instance.async_setup()
        return instance

    async def _ainitialize_model(self):
        """
        Asynchronously initialize the language model.

        This method should be implemented in LangChainUser.
        """
        # Implement this in LangChainUser
        pass

    async def _parse_validation_result(self, output: str) -> Tuple[str, str]:
        """
        Parse the output from the language model to determine the validation result and explanation.

        This method processes the raw output from the language model, extracting
        the validation result (Yes, No, or Unclear) and the accompanying explanation.

        :param output: The raw output string from the language model.
        :return: A tuple containing the validation result and explanation.
        """
        logging.info(f"Raw output to parse: {output}")
        
        # Clean and normalize the output
        cleaned_output = output.strip().lower()
        
        # Extract the first word, handling potential punctuation
        first_word = cleaned_output.split(None, 1)[0].rstrip('.,')
        
        if first_word == "yes":
            validation_result = "Yes"
        elif first_word == "no":
            validation_result = "No"
        else:
            validation_result = "Unclear"

        # Extract explanation (everything after the first word)
        explanation = cleaned_output[len(first_word):].lstrip('., ')

        logging.info(f"Parsed result: {validation_result}")
        logging.info(f"Parsed explanation: {explanation}")

        return validation_result, explanation

    def generate_graph_visualization(self, output_path: str = "./tmp/workflow_graph.png"):
        """
        Generate and save a visual representation of the workflow graph using LangChain's
        built-in visualization capabilities.

        :param output_path: The file path where the graph image will be saved.
        """
        from langchain_core.runnables.graph import CurveStyle, MermaidDrawMethod, NodeStyles
        import os
        
        # Clean up the output path - replace spaces with underscores
        output_dir = os.path.dirname(output_path)
        filename = os.path.basename(output_path)
        clean_filename = filename.replace(' ', '_')
        output_path = os.path.join(output_dir, clean_filename)
        
        logging.info("Getting workflow graph...")
        graph = self.workflow.get_graph(xray=True)
        logging.info(f"Graph nodes: {graph.nodes}")
        logging.info(f"Graph edges: {graph.edges}")
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        logging.info(f"Generating PNG visualization at {output_path}")
        
        try:
            png_data = graph.draw_mermaid_png(
                draw_method=MermaidDrawMethod.API,
                curve_style=CurveStyle.LINEAR,
                node_colors=NodeStyles(
                    first="#ffdfba",
                    last="#baffc9", 
                    default="#f2f0ff"
                )
            )
            logging.info(f"Generated PNG data size: {len(png_data)} bytes")
            
            if not png_data:
                raise ValueError("No PNG data generated")
                
            # Write in a way that ensures the file is properly closed
            try:
                with open(output_path, "wb") as output_file:
                    bytes_written = output_file.write(png_data)
                    output_file.flush()
                    os.fsync(output_file.fileno())  # Ensure data is written to disk
                
                # Verify the file was written correctly
                if not os.path.exists(output_path):
                    raise IOError(f"File {output_path} was not created")
                    
                file_size = os.path.getsize(output_path)
                logging.info(f"Wrote {bytes_written} bytes, file size is {file_size} bytes")
                
                if file_size == 0:
                    raise IOError(f"File {output_path} is empty")
                elif file_size != len(png_data):
                    raise IOError(f"File size {file_size} does not match PNG data size {len(png_data)}")
                    
                logging.info("Successfully wrote PNG file")
                
            except IOError as e:
                logging.error(f"IO Error writing PNG file: {str(e)}")
                raise
                
            return output_path
            
        except Exception as e:
            logging.error(f"Error generating graph visualization: {str(e)}")
            logging.error(f"Full traceback: {traceback.format_exc()}")
            raise

    def register_model(self):
        """
        Register the model.
        """

    def save_model(self):
        """
        Save the model.
        """

    def train_model(self):
        """
        Placeholder method to satisfy the base class requirement.
        This validator doesn't require traditional training.
        """
        pass

    def predict_validation(self):
        """
        Placeholder method to satisfy the base class requirement.
        This validator doesn't require traditional training.
        """
        pass

    def get_token_usage(self):
        """
        Retrieve the current token usage statistics.

        This method returns a dictionary containing the number of prompt tokens,
        completion tokens, total tokens, and successful requests made to the language model.

        :return: A dictionary with token usage statistics.
        """
        total_usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "successful_requests": 0,
            "cached_tokens": 0
        }

        try:
            for node_name, node_instance in self.node_instances:
                node_usage = node_instance.get_token_usage()
                for key in total_usage:
                    total_usage[key] += node_usage[key]
        # TODO: Remove it.  It's necessary because AgenticValidator doesn't set node_instances because it overrides `predict()`
        except Exception as e:
            logging.error(f"Error getting token usage: {str(e)}")

        return total_usage

    def get_accumulated_costs(self):
        """
        Calculate and return the accumulated costs for all computed elements.

        This method computes the costs based on the token usage and the specific
        model being used. It includes input costs, output costs, and total costs.

        :return: A dictionary containing cost and usage information.
        """
        usage = self.get_token_usage()

        try:
            cost_info = calculate_cost(
                model_name=self.parameters.model_name,
                input_tokens=usage['prompt_tokens'],
                output_tokens=usage['completion_tokens']
            )
        except ValueError as e:
            logging.error(f"Error calculating cost: {str(e)}")
            cost_info = {"input_cost": 0, "output_cost": 0, "total_cost": 0}

        return {
            "prompt_tokens":     usage['prompt_tokens'],
            "completion_tokens": usage['completion_tokens'],
            "total_tokens":      usage['total_tokens'],
            "llm_calls":         usage['successful_requests'],
            "cached_tokens":     usage['cached_tokens'],
            "input_cost":        cost_info['input_cost'],
            "output_cost":       cost_info['output_cost'],
            "total_cost":        cost_info['total_cost']
        }

    def reset_token_usage(self):
        """
        Reset the token usage counters.

        This method resets all token usage statistics to zero, allowing for
        fresh tracking of token usage in subsequent operations.
        """
        if self.parameters.model_provider in ["AzureChatOpenAI", "ChatOpenAI"]:
            self.openai_callback = OpenAICallbackHandler()
            self.model = self.model.with_config(callbacks=[self.openai_callback])
        else:
            self.token_counter.prompt_tokens = 0
            self.token_counter.completion_tokens = 0
            self.token_counter.total_tokens = 0
            self.token_counter.llm_calls = 0

    def _initialize_memory(self, state: Any) -> Any:
        """
        Initialize the agent's memory with the text.
        """
        if hasattr(self, 'agent_executor'):
            self.agent_executor.memory.memories["text"] = state.text
        return state

    def create_combined_graphstate_class(self, instances: list) -> Type['LangGraphScore.GraphState']:
        """
        Dynamically create a combined GraphState class based on all nodes in the workflow.
        """
        # Start with base annotations
        base_annotations = self.GraphState.__annotations__.copy()
        logging.info(f"Starting with base annotations: {base_annotations}")

        # First collect all attributes from node instances
        for instance in instances:
            # Add fields from the node's GraphState
            for attr_name, attr_type in instance.GraphState.__annotations__.items():
                # Always make fields Optional
                if not (hasattr(attr_type, '__origin__') and attr_type.__origin__ is Union and type(None) in attr_type.__args__):
                    attr_type = Optional[attr_type]
                base_annotations[attr_name] = attr_type

            # Add fields from output mappings
            if hasattr(instance.parameters, 'output') and instance.parameters.output is not None:
                logging.info(f"Adding output fields from node {instance.__class__.__name__}: {instance.parameters.output}")
                for alias, original in instance.parameters.output.items():
                    base_annotations[alias] = Optional[str]
                    logging.info(f"Added node output alias {alias} with type Optional[str]")
                    
            # Check for edge configuration with output mappings
            if hasattr(instance.parameters, 'edge') and instance.parameters.edge is not None:
                edge_config = instance.parameters.edge
                if isinstance(edge_config, dict) and 'output' in edge_config:
                    logging.info(f"Adding edge output fields from node {instance.__class__.__name__}: {edge_config['output']}")
                    for alias, original in edge_config['output'].items():
                        base_annotations[alias] = Optional[str]
                        logging.info(f"Added edge output alias {alias} with type Optional[str]")

            # Check for conditions configuration with output mappings
            if hasattr(instance.parameters, 'conditions') and instance.parameters.conditions is not None:
                conditions = instance.parameters.conditions
                if isinstance(conditions, list):
                    for condition in conditions:
                        if isinstance(condition, dict) and 'output' in condition:
                            logging.info(f"Adding condition output fields from node {instance.__class__.__name__}: {condition['output']}")
                            for alias, original in condition['output'].items():
                                base_annotations[alias] = Optional[str]
                                logging.info(f"Added condition output alias {alias} with type Optional[str]")

        # Also check the graph configuration directly from the YAML
        if hasattr(self.parameters, 'graph') and isinstance(self.parameters.graph, list):
            for node_config in self.parameters.graph:
                # Check for edge output mappings
                if 'edge' in node_config and isinstance(node_config['edge'], dict) and 'output' in node_config['edge']:
                    node_name = node_config.get('name', 'unknown')
                    logging.info(f"Adding edge output fields from graph config node {node_name}: {node_config['edge']['output']}")
                    for alias, original in node_config['edge']['output'].items():
                        base_annotations[alias] = Optional[str]
                        logging.info(f"Added edge output alias {alias} from graph config")
                
                # Check for conditions output mappings
                if 'conditions' in node_config and isinstance(node_config['conditions'], list):
                    node_name = node_config.get('name', 'unknown')
                    for condition in node_config['conditions']:
                        if isinstance(condition, dict) and 'output' in condition:
                            logging.info(f"Adding condition output fields from graph config node {node_name}: {condition['output']}")
                            for alias, original in condition['output'].items():
                                base_annotations[alias] = Optional[str]
                                logging.info(f"Added condition output alias {alias} from graph config")

        # Handle output aliases from main parameters
        if hasattr(self.parameters, 'output') and self.parameters.output is not None:
            logging.info(f"Adding score output fields: {self.parameters.output}")
            for alias, original in self.parameters.output.items():
                base_annotations[alias] = Optional[str]
                logging.info(f"Added score output alias {alias} with type Optional[str]")

        # Create new class with updated configuration
        class CombinedGraphState(self.GraphState):
            __annotations__ = base_annotations
            model_config = ConfigDict(
                arbitrary_types_allowed=True,
                validate_default=False,  # Don't validate defaults
                extra='allow',  # Allow extra fields
                validate_assignment=False,  # Don't validate on assignment
                populate_by_name=True,  # Allow population by field name
                use_enum_values=True,  # Use enum values instead of enum objects
            )

            def __init__(self, **data):
                # Set all fields to None by default
                defaults = {field: None for field in self.__annotations__}
                # Special case for chat_history which should be an empty list
                if 'chat_history' in self.__annotations__:
                    defaults['chat_history'] = []
                # Override defaults with provided data
                defaults.update(data)
                super().__init__(**defaults)

        logging.info(f"Base GraphState fields: {self.GraphState.__annotations__}")
        logging.info(f"Final combined state fields: {CombinedGraphState.__annotations__}")
        
        return CombinedGraphState

    @staticmethod
    def generate_input_aliasing_function(input_mapping: dict) -> FunctionType:
        def input_aliasing(state):
            logging.info(f"Input aliasing: {input_mapping}")
            for alias, original in input_mapping.items():
                if hasattr(state, original):
                    setattr(state, alias, getattr(state, original))
            return state
        return input_aliasing

    @staticmethod
    def generate_output_aliasing_function(output_mapping: dict) -> FunctionType:
        def output_aliasing(state):
            logging.debug("=== Output Aliasing Node Start ===")
            logging.debug(f"Input state type: {type(state)}")
            logging.debug(f"Input state fields: {state.model_fields.keys()}")
            logging.debug(f"Input state values: {truncate_dict_strings(state.model_dump(), max_length=80)}")
            
            # Create a new dict with all current state values
            new_state = state.model_dump()
            
            # Add aliased values
            for alias, original in output_mapping.items():
                if hasattr(state, original):
                    original_value = getattr(state, original)
                    new_state[alias] = original_value
                    # Also directly set on the state object to ensure it's accessible
                    setattr(state, alias, original_value)
                    value = str(original_value)
                    if len(value) > 80:
                        value = value[:77] + "..."
                    logging.info(f"Added alias {alias}={value} from {original}")
                else:
                    # If the original isn't a state variable, treat it as a literal value
                    new_state[alias] = original
                    # Also directly set on the state object
                    setattr(state, alias, original)
                    logging.info(f"Added literal value {alias}={original}")
            
            # Create new state with extra fields allowed
            combined_state = state.__class__(**new_state)
            logging.info(f"Output state type: {type(combined_state)}")
            logging.info(f"Output state fields: {combined_state.model_fields.keys()}")
            logging.info(f"Output state values: {truncate_dict_strings(combined_state.model_dump(), max_length=80)}")
            logging.info("=== Output Aliasing Node End ===")
            return combined_state
            
        return output_aliasing

    @staticmethod
    def _import_class(class_name):
        """Import a class from the nodes module."""
        try:
            # Import from the nodes package
            module = importlib.import_module('plexus.scores.nodes')
            logging.debug(f"Attempting to get class {class_name} from nodes module")
            logging.debug(f"Module contents: {dir(module)}")
            
            # List all modules in plexus.scores.nodes
            import pkgutil
            package = importlib.import_module('plexus.scores.nodes')
            modules = [name for _, name, _ in pkgutil.iter_modules(package.__path__)]
            logging.debug(f"Available modules in plexus.scores.nodes: {modules}")
            
            # Try to import specific module
            specific_module_path = f'plexus.scores.nodes.{class_name}'
            logging.debug(f"Attempting to import from specific path: {specific_module_path}")
            specific_module = importlib.import_module(specific_module_path)
            logging.debug(f"Specific module contents: {dir(specific_module)}")
            
            # Check what's actually in the module
            for item_name in dir(specific_module):
                item = getattr(specific_module, item_name)
                if not item_name.startswith('_'):  # Skip private attributes
                    logging.debug(f"Item '{item_name}' is of type: {type(item)}")
                    if isinstance(item, type):
                        logging.debug(f"Found class: {item_name}")
                        if item_name == class_name:
                            logging.debug(f"Found matching class {class_name}")
                            return item
            
            raise ImportError(
                f"Could not find class {class_name} in module {specific_module_path}\n"
                f"Available items: {[name for name in dir(specific_module) if not name.startswith('_')]}"
            )
            
        except Exception as e:
            logging.error(f"Error importing class {class_name}: {str(e)}")
            logging.error(f"Stack trace: {traceback.format_exc()}")
            raise

    def get_prompt_templates(self):
        """
        Get the prompt templates for the score by iterating over the graph nodes and asking each node for its prompt templates.
        """
        # First pass: Collect node instances
        node_instances = []
        node_templates = []
        if hasattr(self.parameters, 'graph') and isinstance(self.parameters.graph, list):
            for node_configuration_entry in self.parameters.graph:

                for attribute in ['model_provider', 'model_name', 'model_region', 'temperature', 'max_tokens']:
                    if attribute not in node_configuration_entry:
                        node_configuration_entry[attribute] = getattr(self.parameters, attribute)

                if 'class' in node_configuration_entry and 'name' in node_configuration_entry:
                    node_class_name = node_configuration_entry['class']
                    node_name = node_configuration_entry['name']
                    node_class = LangGraphScore._import_class(node_class_name)
                    logging.info(f"Node class: {node_class}")
                    node_instance = node_class(**node_configuration_entry)
                    node_instances.append((node_name, node_instance))
                    node_templates.append(node_instance.get_prompt_templates())
        else:
            raise ValueError("Invalid or missing graph configuration in parameters.")
        
        return node_templates

    def get_example_refinement_templates(self):
        """
        Get the example refinement templates for the score by iterating over the graph nodes and asking each node for its example refinement template.
        """
        # First pass: Collect node instances
        node_instances = []
        example_refinement_templates = []
        if hasattr(self.parameters, 'graph') and isinstance(self.parameters.graph, list):
            for node_configuration_entry in self.parameters.graph:

                for attribute in ['model_provider', 'model_name', 'model_region', 'temperature', 'max_tokens']:
                    if attribute not in node_configuration_entry:
                        node_configuration_entry[attribute] = getattr(self.parameters, attribute)

                if 'class' in node_configuration_entry and 'name' in node_configuration_entry:
                    node_class_name = node_configuration_entry['class']
                    node_name = node_configuration_entry['name']
                    node_class = LangGraphScore._import_class(node_class_name)
                    logging.info(f"Node class: {node_class}")
                    node_instance = node_class(**node_configuration_entry)
                    node_instances.append((node_name, node_instance))
                    example_refinement_templates.append(node_instance.get_example_refinement_template())
        else:
            raise ValueError("Invalid or missing graph configuration in parameters.")
        
        return example_refinement_templates

    @staticmethod
    def create_value_setter_node(output_mapping: dict) -> FunctionType:
        def value_setter(state):
            logging.info("=== Value Setter Node Start ===")
            logging.info(f"Input state type: {type(state)}")
            logging.info(f"Input state fields: {state.model_fields.keys()}")
            logging.info(f"Input state values: {truncate_dict_strings(state.model_dump(), max_length=80)}")
            
            # Create a new dict with all current state values
            new_state = state.model_dump()
            
            # Add aliased values
            for alias, original in output_mapping.items():
                if hasattr(state, original):
                    original_value = getattr(state, original)
                    new_state[alias] = original_value
                    # Also directly set on the state object to ensure it's accessible
                    setattr(state, alias, original_value)
                    value = str(original_value)
                    if len(value) > 80:
                        value = value[:77] + "..."
                    logging.info(f"Added alias {alias}={value} from {original}")
                else:
                    # If the original isn't a state variable, treat it as a literal value
                    new_state[alias] = original
                    # Also directly set on the state object
                    setattr(state, alias, original)
                    logging.info(f"Added literal value {alias}={original}")
            
            # Create new state with extra fields allowed
            combined_state = state.__class__(**new_state)
            logging.info(f"Output state type: {type(combined_state)}")
            logging.info(f"Output state fields: {combined_state.model_fields.keys()}")
            logging.info(f"Output state values: {truncate_dict_strings(combined_state.model_dump(), max_length=80)}")
            logging.info("=== Value Setter Node End ===")
            return combined_state
            
        return value_setter

    async def predict(
        self,
        model_input: Score.Input,
        thread_id: Optional[str] = None,
        batch_data: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> Score.Result:
        """
        Make predictions using the LangGraph workflow.

        Parameters
        ----------
        model_input : Score.Input
            The input data containing text and metadata
        thread_id : Optional[str]
            Thread ID for checkpointing
        batch_data : Optional[Dict[str, Any]]
            Additional data for batch processing
        **kwargs : Any
            Additional keyword arguments

        Returns
        -------
        Score.Result
            The prediction result with value and explanation
        """
        # Generate checkpoint IDs if not provided
        if not thread_id:
            thread_id = str(uuid.uuid4())
        checkpoint_ns = f"{self.parameters.name}_{thread_id}" if self.parameters.name else str(uuid.uuid4())
        checkpoint_id = str(uuid.uuid4())

        thread = {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id
            }
        }
        # Use the passed-in results if available, otherwise start with empty dict
        initial_results = {}
        if model_input.results:
            for result in model_input.results:
                if not isinstance(result, Score.Result):
                    raise TypeError(f"Expected Score.Result object but got {type(result)}")
                initial_results[result.parameters.name] = result.value

        # --- Logging Input Metadata ---
        logging.debug("=== Inspecting model_input.metadata before state creation ===")
        if model_input.metadata:
            logging.debug(f"model_input.metadata type: {type(model_input.metadata)}")
            logging.debug(f"model_input.metadata keys: {list(model_input.metadata.keys()) if isinstance(model_input.metadata, dict) else 'N/A'}")
            logging.debug(f"model_input.metadata content (truncated): {truncate_dict_strings(model_input.metadata, 150)}")
            if isinstance(model_input.metadata, dict) and 'scorecard_name' in model_input.metadata:
                logging.debug(f"model_input.metadata['scorecard_name'] type: {type(model_input.metadata['scorecard_name'])}")
                logging.debug(f"model_input.metadata['scorecard_name'] value: {str(model_input.metadata['scorecard_name'])[:100]}")
        else:
            logging.debug("model_input.metadata is None or empty.")
        # --- End Logging ---

        # --- Sanitize metadata BEFORE adding to state ---
        sanitized_metadata = _ensure_serializable(model_input.metadata)
        logging.debug("=== Sanitized metadata before state creation ===")
        logging.debug(f"sanitized_metadata type: {type(sanitized_metadata)}")
        logging.debug(f"sanitized_metadata content (truncated): {truncate_dict_strings(sanitized_metadata, 150)}")
        # --- End Sanitization ---

        initial_state_dict = {
            'text': self.preprocess_text(model_input.text),
            'metadata': sanitized_metadata, # Use sanitized version
            'results': initial_results,
            'retry_count': 0,
            'at_llm_breakpoint': False,
        }

        if batch_data:
            initial_state_dict.update(batch_data)

        # Create the state object using the combined class
        try:
            initial_state_obj = self.combined_state_class(**initial_state_dict)
            initial_state = initial_state_obj.model_dump()
        except Exception as e_state_create:
            logging.error(f"Error creating combined_state_class instance: {e_state_create}", exc_info=True)
            logging.error(f"Initial data provided: {initial_state_dict}")
            raise

        # --- Logging Initial State ---
        logging.debug("=== Inspecting initial_state before workflow invocation ===")
        logging.debug(f"initial_state type: {type(initial_state)}")
        logging.debug(f"initial_state keys: {list(initial_state.keys()) if isinstance(initial_state, dict) else 'N/A'}")
        if isinstance(initial_state, dict) and 'metadata' in initial_state and initial_state['metadata']:
             logging.debug(f"initial_state['metadata'] type: {type(initial_state['metadata'])}")
             logging.debug(f"initial_state['metadata'] keys: {list(initial_state['metadata'].keys()) if isinstance(initial_state['metadata'], dict) else 'N/A'}")
             logging.debug(f"initial_state['metadata'] content (truncated): {truncate_dict_strings(initial_state['metadata'], 150)}")
             if isinstance(initial_state['metadata'], dict) and 'scorecard_name' in initial_state['metadata']:
                 logging.debug(f"initial_state['metadata']['scorecard_name'] type: {type(initial_state['metadata']['scorecard_name'])}")
                 logging.debug(f"initial_state['metadata']['scorecard_name'] value: {str(initial_state['metadata']['scorecard_name'])[:100]}")
        else:
             logging.debug("initial_state['metadata'] is missing, None, or empty.")
        # --- End Logging ---

        try:
            logging.info("=== Pre-invoke State Inspection ===")
            logging.info(f"Initial state type: {type(initial_state)}")
            logging.info(f"Initial state keys: {list(initial_state.keys())}") # Log keys as list
            logging.debug(f"Initial state values (truncated): {truncate_dict_strings(initial_state, max_length=100)}")
            logging.info(f"Workflow type: {type(self.workflow)}")

            graph_result = await self.workflow.ainvoke(
                initial_state,
                config=thread
            )

            logging.info("=== Post-invoke Graph Result ===")
            logging.info(f"Graph result type: {type(graph_result)}")
            if isinstance(graph_result, dict):
                 logging.info(f"Graph result keys: {list(graph_result.keys())}") # Log keys as list
                 logging.debug(f"Graph result values (truncated): {truncate_dict_strings(graph_result, max_length=100)}")
            else:
                 logging.debug(f"Graph result value (truncated): {str(graph_result)[:100]}")

            # Convert graph result to Score.Result
            result = Score.Result(
                parameters=self.parameters,
                value=graph_result.get('value', 'Error'),
                metadata={
                    'explanation': graph_result.get('explanation'),
                    'good_call': graph_result.get('good_call'),
                    'good_call_explanation': graph_result.get('good_call_explanation'),
                    'non_qualifying_reason': graph_result.get('non_qualifying_reason'),
                    'non_qualifying_explanation': graph_result.get('non_qualifying_explanation'),
                    'confidence': graph_result.get('confidence'),
                    'classification': graph_result.get('classification'),
                    'source': graph_result.get('source')
                }
            )
            
            # Include ALL fields from graph_result in the metadata
            for key, value in graph_result.items():
                if key not in ['value', 'metadata'] and key not in result.metadata:
                    result.metadata[key] = value
            
            # If metadata with trace exists in graph_result, add it to the result metadata
            if 'metadata' in graph_result and graph_result['metadata'] is not None:
                logging.info("=== Processing graph_result['metadata'] ===")
                logging.debug(f"Original graph_result['metadata'] type: {type(graph_result['metadata'])}")
                logging.debug(f"Original graph_result['metadata'] (truncated): {truncate_dict_strings(graph_result['metadata'], 100) if isinstance(graph_result['metadata'], dict) else str(graph_result['metadata'])[:100]}")

                # Ensure the incoming metadata is serializable BEFORE merging
                serializable_graph_metadata = ensure_serializable(graph_result['metadata'])
                logging.debug(f"Serialized graph_result['metadata'] type: {type(serializable_graph_metadata)}")
                logging.debug(f"Serialized graph_result['metadata'] (truncated): {truncate_dict_strings(serializable_graph_metadata, 100) if isinstance(serializable_graph_metadata, dict) else str(serializable_graph_metadata)[:100]}")

                if isinstance(serializable_graph_metadata, dict):
                    result.metadata.update(serializable_graph_metadata)
                    logging.info("Successfully merged serializable graph_result['metadata'] (dict) into result.metadata")
                else:
                    logging.warning(f"graph_result['metadata'] was not a dict after serialization attempt, type: {type(serializable_graph_metadata)}. Adding as extra key.")
                    result.metadata['additional_graph_metadata'] = serializable_graph_metadata
            else:
                logging.info("No 'metadata' key found in graph_result or it is None.")


            # Apply serialization safety to the final result dict's metadata before returning
            logging.info("=== Final Serialization Pass for result.metadata ===")
            try:
                if result.metadata and isinstance(result.metadata, dict):
                    logging.debug(f"Pre-final serialization result.metadata type: {type(result.metadata)}")
                    logging.debug(f"Pre-final serialization result.metadata (truncated): {truncate_dict_strings(result.metadata, 100)}")
                    result.metadata = ensure_serializable(result.metadata)
                    logging.debug(f"Post-final serialization result.metadata type: {type(result.metadata)}")
                    logging.debug(f"Post-final serialization result.metadata (truncated): {truncate_dict_strings(result.metadata, 100)}")
                    logging.info("Final serialization pass on result.metadata completed.")
                elif not result.metadata:
                     logging.info("result.metadata is None or empty, skipping final serialization.")
                else:
                     logging.warning(f"result.metadata is not a dict (type: {type(result.metadata)}), skipping final serialization.")

            except Exception as e:
                logging.error(f"Error during final serialization of result.metadata: {e}")
                # Provide a fallback result if serialization fails
                result.metadata = {"value": "Error", "explanation": f"Final serialization error: {str(e)}"}

            logging.info("=== Predict Method Complete ===")
            logging.debug(f"Final Score.Result value: {result.value}")
            logging.debug(f"Final Score.Result metadata (truncated): {truncate_dict_strings(result.metadata, 100) if isinstance(result.metadata, dict) else str(result.metadata)[:100]}")
            return result
        except BatchProcessingPause:
            # Let BatchProcessingPause propagate up
            logging.info("BatchProcessingPause encountered, propagating.")
            raise
        except Exception as e:
            logging.error(f"Error in predict: {e}", exc_info=True) # Add exc_info for traceback
            return Score.Result(
                parameters=self.parameters,
                value="Error",
                error=str(e)
            )

    def preprocess_text(self, text):
        # Join all text elements into a single string
        if isinstance(text, list):
            return " ".join(text)
        return text

    async def cleanup(self):
        """Cleanup resources."""
        try:
            # Give LangGraph a chance to finish any pending operations
            await asyncio.sleep(0.1)

            # Close PostgreSQL checkpointer if it was initialized
            if hasattr(self, '_checkpointer_context') and \
               self._checkpointer_context is not None:
                try:
                    logging.info("Closing PostgreSQL checkpointer...")
                    await self._checkpointer_context.__aexit__(None, None, None)
                    self.checkpointer = None
                    self._checkpointer_context = None
                    logging.info("PostgreSQL checkpointer closed")
                except Exception as e:
                    logging.error(f"Error closing PostgreSQL checkpointer: {e}")

            # Close Azure credentials
            if hasattr(self, '_credential'):
                try:
                    logging.info("Closing Azure credential...")
                    await self._credential.close()
                    self._credential = None
                    logging.info("Azure credential closed")
                except Exception as e:
                    logging.error(f"Error closing Azure credential: {e}")

        except Exception as e:
            logging.error(f"Error during cleanup: {e}")

    async def __aenter__(self):
        """Async context manager entry."""
        await self.async_setup()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.cleanup()

    async def get_scoring_jobs_for_batch(
        self,
        batch_job_id: str
    ) -> List[Dict[str, Any]]:
        """Get all scoring jobs associated with a batch job."""
        # Create client using account_key from metadata
        client = PlexusDashboardClient.for_scorecard(
            account_key=self.parameters.account_key,
            scorecard_key=self.parameters.scorecard_name,
            score_name=self.parameters.name
        )
        
        query = """
        query GetBatchScoringJobs($batchJobId: String!) {
            listBatchJobScoringJobs(
                filter: { batchJobId: { eq: $batchJobId } }
                limit: 1000
            ) {
                items {
                    scoringJob {
                        id
                        itemId
                        status
                        metadata
                    }
                    createdAt
                }
            }
        }
        """
        result = client.execute(query, {'batchJobId': batch_job_id})
        scoring_jobs = [item['scoringJob'] 
                       for item in result.get('listBatchJobScoringJobs', {}).get('items', [])]
        logging.info(f"Found {len(scoring_jobs)} scoring jobs for batch {batch_job_id}")
        return scoring_jobs

