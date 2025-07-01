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

from plexus.LangChainUser import LangChainUser
from plexus.scores.Score import Score
from plexus.utils.dict_utils import truncate_dict_strings

from langchain_community.callbacks import OpenAICallbackHandler

from langgraph.graph import StateGraph, END

from openai_cost_calculator.openai_cost_calculator import calculate_cost

from langchain.globals import set_debug, set_verbose
# Only enable debug for very specific debugging scenarios
debug_mode = os.getenv('LANGCHAIN_DEBUG', '').lower() in ['true', '1', 'yes']
if debug_mode:
    set_debug(True)
    set_verbose(True)
else:
    set_debug(False)
    set_verbose(False)

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from pathlib import Path
import uuid
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
            logging.info("Using PostgreSQL checkpoint database")
            # Create checkpointer and store the context manager
            self._checkpointer_context = AsyncPostgresSaver.from_conn_string(db_uri)
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
    def add_edges(workflow, node_instances, entry_point, graph_config, end_node=None):
        """Add edges between nodes in the workflow."""
        logging.info(f"Building workflow with nodes: {[name for name, _ in node_instances]}")
        
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
                        logging.info(f"Added output mapping: {previous_node} -> {value_setter_name} -> {node_name}")
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
                            final_target = end_node or END
                            workflow.add_edge(value_setter_name, final_target)
                            logging.info(f"Added edge routing: {previous_node} -> {final_target}")
                        else:
                            workflow.add_edge(value_setter_name, target_node)
                            logging.info(f"Added edge routing: {previous_node} -> {target_node}")
                    
                    # Handle conditions clause - conditional routing
                    elif 'conditions' in node_config:
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
                                    logging.info(f"Routing from {previous_node}: classification={getattr(state, 'classification', None)}")
                                    
                                    if hasattr(state, 'classification') and state.classification is not None:
                                        state_value = state.classification.lower()
                                        # Check if we have a value setter for this classification
                                        if state_value in value_setters:
                                            target = value_setters[state_value]
                                            logging.info(f"  -> {target} (condition: {state_value})")
                                            return target
                                    
                                    # Default case - route to next node
                                    logging.info(f"  -> {next_node} (default)")
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
                                    final_target = end_node or END
                                    workflow.add_edge(value_setter_name, final_target)
                                else:
                                    workflow.add_edge(value_setter_name, target_node)
                            
                            logging.info(f"Added conditional routing from {previous_node} with {len(conditions)} conditions")
                        else:
                            logging.error(f"Conditions is not a list: {conditions}")
                            workflow.add_edge(previous_node, node_name)
                    
                    # No edge or conditions clause - add direct edge to next node
                    else:
                        workflow.add_edge(previous_node, node_name)
                        logging.info(f"Added direct edge: {previous_node} -> {node_name}")
                else:
                    logging.warning(f"No config found for previous_node: {previous_node}")
        
        # NEW: Handle edge configurations for the final node that routes to END
        if node_instances:
            final_node_name = node_instances[-1][0]
            final_node_config = next((node for node in graph_config
                                    if node['name'] == final_node_name), None)
            
            if final_node_config and 'edge' in final_node_config:
                edge = final_node_config['edge']
                target_node = edge.get('node')
                
                # Only process if this edge routes to END
                if target_node == 'END' and 'output' in edge:
                    value_setter_name = f"{final_node_name}_value_setter"
                    # Create value setter node for the final edge
                    workflow.add_node(
                        value_setter_name,
                        LangGraphScore.create_value_setter_node(
                            edge.get('output', {})
                        )
                    )
                    # Add edge from final node to value setter
                    workflow.add_edge(final_node_name, value_setter_name)
                    # Add edge from value setter to end target
                    final_target = end_node or END
                    workflow.add_edge(value_setter_name, final_target)
                    logging.info(f"Added final node edge routing: {final_node_name} -> {value_setter_name} -> {final_target}")
                    
                    # Return True to indicate we handled the final node's routing
                    return True
        
        logging.info("Workflow edges configured")
        return False  # Indicate we didn't handle final node routing

    async def build_compiled_workflow(self):
        """Build the LangGraph workflow with optional persistence."""
        logging.info("Building LangGraph workflow")
        
        # First collect node instances
        node_instances = []
        if hasattr(self.parameters, 'graph') and isinstance(self.parameters.graph, list):
            for node_configuration_entry in self.parameters.graph:
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
                        node_class = self._import_class(node_class_name)
                        if node_class is None:
                            raise ValueError(f"Could not import class {node_class_name}")
                        
                        node_instance = node_class(**node_configuration_entry)
                        node_instances.append((node_name, node_instance))
                        logging.info(f"Added node: {node_name} ({node_class_name})")
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
        
        # Store the combined state class
        self.combined_state_class = combined_state_class

        try:
            # Use combined state class when creating workflow
            workflow = StateGraph(combined_state_class)

            # Add all nodes to the graph
            for node_name, node_instance in node_instances:
                workflow.add_node(
                    node_name, 
                    node_instance.build_compiled_workflow(
                        graph_state_class=combined_state_class
                    )
                )

            # Set the entry point to the first node
            if node_instances:
                workflow.set_entry_point(node_instances[0][0])

            # Add the final output aliasing node if needed
            output_aliasing_node_name = None
            if hasattr(self.parameters, 'output') and self.parameters.output:
                output_aliasing_node_name = 'output_aliasing'
                output_aliasing_function = self.generate_output_aliasing_function(self.parameters.output)
                workflow.add_node(output_aliasing_node_name, output_aliasing_function)
                workflow.add_edge(output_aliasing_node_name, END)
                logging.info("Added final output aliasing node, which will connect to END.")

            # Add edges between nodes, redirecting any 'END' edges to the output aliasing node
            final_node_handled = self.add_edges(workflow, node_instances, None, self.parameters.graph, end_node=output_aliasing_node_name)

            # Connect the last sequential node to the appropriate end target
            if node_instances and not final_node_handled:
                last_node_name = node_instances[-1][0]
                last_node_config = next((n for n in self.parameters.graph if n['name'] == last_node_name), None)
                
                # Only add a fall-through edge if the last node doesn't have its own explicit routing
                if not (last_node_config and ('edge' in last_node_config or 'conditions' in last_node_config)):
                    end_target = output_aliasing_node_name or END
                    workflow.add_edge(last_node_name, end_target)
                    logging.info(f"Connected final sequential node '{last_node_name}' to '{end_target}'.")

            logging.info("Workflow compilation complete.")
            
            # Compile with checkpointer only if configured
            app = workflow.compile(
                checkpointer=self.checkpointer if self.checkpointer else None
            )
            
            # Store node instances for later token usage calculation
            self.node_instances = node_instances
            
            # Store the compiled workflow before trying to visualize it
            self.workflow = app
            
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
                for alias, original in instance.parameters.output.items():
                    base_annotations[alias] = Optional[str]
                    
            # Check for edge configuration with output mappings
            if hasattr(instance.parameters, 'edge') and instance.parameters.edge is not None:
                edge_config = instance.parameters.edge
                if isinstance(edge_config, dict) and 'output' in edge_config:
                    for alias, original in edge_config['output'].items():
                        base_annotations[alias] = Optional[str]

            # Check for conditions configuration with output mappings
            if hasattr(instance.parameters, 'conditions') and instance.parameters.conditions is not None:
                conditions = instance.parameters.conditions
                if isinstance(conditions, list):
                    for condition in conditions:
                        if isinstance(condition, dict) and 'output' in condition:
                            for alias, original in condition['output'].items():
                                base_annotations[alias] = Optional[str]

        # Also check the graph configuration directly from the YAML
        if hasattr(self.parameters, 'graph') and isinstance(self.parameters.graph, list):
            for node_config in self.parameters.graph:
                # Check for edge output mappings
                if 'edge' in node_config and isinstance(node_config['edge'], dict) and 'output' in node_config['edge']:
                    for alias, original in node_config['edge']['output'].items():
                        base_annotations[alias] = Optional[str]
                
                # Check for conditions output mappings
                if 'conditions' in node_config and isinstance(node_config['conditions'], list):
                    for condition in node_config['conditions']:
                        if isinstance(condition, dict) and 'output' in condition:
                            for alias, original in condition['output'].items():
                                base_annotations[alias] = Optional[str]

        # Handle output aliases from main parameters
        if hasattr(self.parameters, 'output') and self.parameters.output is not None:
            for alias, original in self.parameters.output.items():
                base_annotations[alias] = Optional[str]

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
        
        return CombinedGraphState

    @staticmethod
    def generate_input_aliasing_function(input_mapping: dict) -> FunctionType:
        def input_aliasing(state):
            for alias, original in input_mapping.items():
                if hasattr(state, original):
                    setattr(state, alias, getattr(state, original))
            return state
        return input_aliasing

    @staticmethod
    def generate_output_aliasing_function(output_mapping: dict) -> FunctionType:
        def output_aliasing(state):
            logging.info(f"Applying output aliases: {list(output_mapping.keys())}")
            
            # DEBUG: Log the current state before aliasing
            logging.info(f"DEBUG: State before aliasing: {state.model_dump()}")
            logging.info(f"DEBUG: State attributes: {[attr for attr in dir(state) if not attr.startswith('_')]}")
            
            # Create a new dict with all current state values
            new_state = state.model_dump()
            
            # Add aliased values
            for alias, original in output_mapping.items():
                logging.info(f"DEBUG: Processing alias '{alias}' -> '{original}'")
                if hasattr(state, original):
                    original_value = getattr(state, original)
                    logging.info(f"DEBUG: Found {original} = {original_value!r} (type: {type(original_value)})")
                    
                    # Defensive check: never set a field to None, provide sensible defaults
                    if original_value is None:
                        if alias == 'value':
                            original_value = "No"  # Default classification value
                        elif alias in ['explanation', 'criteria_met']:
                            original_value = ""  # Default empty string for text fields
                        else:
                            original_value = ""  # General fallback
                        logging.warning(f"Output aliasing: {original} was None, defaulting {alias} to '{original_value}'")
                    
                    new_state[alias] = original_value
                    logging.info(f"DEBUG: Set new_state['{alias}'] = {original_value!r}")
                    # Also directly set on the state object to ensure it's accessible
                    setattr(state, alias, original_value)
                else:
                    logging.info(f"DEBUG: {original} not found as attribute, treating as literal")
                    # If the original isn't a state variable, treat it as a literal value
                    new_state[alias] = original
                    # Also directly set on the state object
                    setattr(state, alias, original)
            
            # DEBUG: Log the final new_state before creating combined_state
            logging.info(f"DEBUG: Final new_state: {new_state}")
            
            # Create new state with extra fields allowed
            combined_state = state.__class__(**new_state)
            
            # DEBUG: Log the combined_state after creation
            logging.info(f"DEBUG: Combined state created: {combined_state.model_dump()}")
            
            return combined_state
            
        return output_aliasing

    @staticmethod
    def _import_class(class_name):
        """Import a class from the nodes module."""
        try:
            # Try to import specific module
            specific_module_path = f'plexus.scores.nodes.{class_name}'
            specific_module = importlib.import_module(specific_module_path)
            
            # Check what's actually in the module
            for item_name in dir(specific_module):
                item = getattr(specific_module, item_name)
                if not item_name.startswith('_'):  # Skip private attributes
                    if isinstance(item, type):
                        if item_name == class_name:
                            return item
            
            raise ImportError(
                f"Could not find class {class_name} in module {specific_module_path}\n"
                f"Available items: {[name for name in dir(specific_module) if not name.startswith('_')]}"
            )
            
        except Exception as e:
            logging.error(f"Error importing class {class_name}: {str(e)}")
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
                    node_instance = node_class(**node_configuration_entry)
                    node_instances.append((node_name, node_instance))
                    example_refinement_templates.append(node_instance.get_example_refinement_template())
        else:
            raise ValueError("Invalid or missing graph configuration in parameters.")
        
        return example_refinement_templates

    @staticmethod
    def create_value_setter_node(output_mapping: dict) -> FunctionType:
        def value_setter(state):
            # Create a new dict with all current state values
            new_state = state.model_dump()
            
            # Add aliased values
            for alias, original in output_mapping.items():
                if hasattr(state, original):
                    original_value = getattr(state, original)
                    new_state[alias] = original_value
                    # Also directly set on the state object to ensure it's accessible
                    setattr(state, alias, original_value)
                else:
                    # If the original isn't a state variable, treat it as a literal value
                    new_state[alias] = original
                    # Also directly set on the state object
                    setattr(state, alias, original)
            
            # Create new state with extra fields allowed
            combined_state = state.__class__(**new_state)
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

        initial_state = self.combined_state_class(
            text=self.preprocess_text(model_input.text),
            metadata=model_input.metadata,
            results=initial_results,
            retry_count=0,
            at_llm_breakpoint=False,
        ).model_dump()

        if batch_data:
            initial_state.update(batch_data)

        try:
            logging.info(f"Starting workflow execution with thread_id: {thread_id}")
            
            graph_result = await self.workflow.ainvoke(
                initial_state,
                config=thread
            )
            
            # DEBUG: Log the graph_result before converting to Score.Result
            logging.info(f"DEBUG: graph_result keys: {list(graph_result.keys())}")
            logging.info(f"DEBUG: graph_result['value'] = {graph_result.get('value')!r} (type: {type(graph_result.get('value'))})")
            logging.info(f"DEBUG: Full graph_result: {graph_result}")
            
            # Convert graph result to Score.Result
            value_for_result = graph_result.get('value', 'Error')
            if value_for_result is None:
                logging.warning("DEBUG: graph_result['value'] is None, defaulting to 'No'")
                value_for_result = 'No'
            
            result = Score.Result(
                parameters=self.parameters,
                value=value_for_result,
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
                # Merge the existing metadata with the graph_result metadata
                result.metadata.update(graph_result['metadata'])
            
            return result
        except BatchProcessingPause:
            # Let BatchProcessingPause propagate up
            raise
        except Exception as e:
            logging.error(f"Error in predict: {e}")
            return Score.Result(
                parameters=self.parameters,
                value="ERROR",
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

