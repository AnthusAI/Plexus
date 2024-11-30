import os
import logging
import traceback
import graphviz
from types import FunctionType
from typing import Type, Tuple, Literal, Optional, Any, TypedDict, List, Dict, Union
from pydantic import BaseModel, ConfigDict, create_model, Field
import concurrent.futures
import aiosqlite
import importlib
import asyncio
from os import getenv
from dotenv import load_dotenv

from plexus.LangChainUser import LangChainUser
from plexus.scores.Score import Score

from langchain_community.callbacks import OpenAICallbackHandler

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolExecutor

from openai_cost_calculator.openai_cost_calculator import calculate_cost

from langchain.globals import set_debug, set_verbose
if os.getenv('DEBUG'):
    set_debug(True)
else:
    set_debug(False)
    set_verbose(False)

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from pathlib import Path
import uuid
from langgraph.errors import NodeInterrupt
from plexus_dashboard.api.client_manager import ClientManager
from plexus_dashboard.api.models.account import Account

class BatchProcessingPause(Exception):
    """Signals that execution has been paused for batch processing"""
    def __init__(self, thread_id: str, state: dict, message: str = None):
        self.thread_id = thread_id
        self.state = state
        self.message = message or "Execution paused for batch processing"
        super().__init__(f"{self.message}. Thread ID: {thread_id}")

class LangGraphScore(Score, LangChainUser):
    """
    A Score class that uses language models to perform text classification.

    This class initializes and manages a language model for processing text inputs,
    tracks token usage, and provides methods for text classification and cost calculation.
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
        is_not_empty: Optional[bool] = None
        value: Optional[str] = None
        explanation: Optional[str] = None
        reasoning: Optional[str] = None
        chat_history: List[Any] = Field(default_factory=list)
        completion: Optional[str] = None
        classification: Optional[str] = None
        confidence: Optional[float] = None
        retry_count: Optional[int] = Field(default=0)
        at_llm_breakpoint: Optional[bool] = Field(default=False)

        model_config = ConfigDict(arbitrary_types_allowed=True)

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
        load_dotenv()
        
        # Get PostgreSQL URL from parameters or environment
        db_uri = self.parameters.postgres_url or \
                 getenv('PLEXUS_LANGGRAPH_CHECKPOINTER_POSTGRES_URI')
        
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
    def add_edges(workflow, node_instances, entry_point, graph_config):
        """Add edges between nodes in the workflow."""
        for i, (node_name, _) in enumerate(node_instances):
            if i == 0 and entry_point:
                workflow.add_edge(entry_point, node_name)
            
            if i > 0:
                previous_node = node_instances[i-1][0]
                node_config = next((node for node in graph_config
                                  if node['name'] == previous_node), None)
                if node_config and 'conditions' in node_config:
                    logging.info(f"Node '{previous_node}' has conditions: {node_config['conditions']}")
                    
                    conditions = node_config['conditions']
                    if isinstance(conditions, list):
                        value_setters = {}
                        for j, condition in enumerate(conditions):
                            value_setter_name = f"{previous_node}_value_setter_{j}"
                            value_setters[condition['value'].lower()] = value_setter_name
                            workflow.add_node(
                                value_setter_name, 
                                LangGraphScore.create_value_setter_node(
                                    condition.get('output', {})
                                )
                            )

                        def create_routing_function(conditions, value_setters, node_name):
                            def routing_function(state):
                                for condition in conditions:
                                    if hasattr(state, condition['state']) and \
                                       getattr(state, condition['state']).lower() == \
                                           condition['value'].lower():
                                        return value_setters[condition['value'].lower()]
                                return node_name
                            return routing_function

                        workflow.add_conditional_edges(
                            previous_node,
                            create_routing_function(conditions, value_setters, node_name)
                        )

                        for condition in conditions:
                            value_setter_name = value_setters[condition['value'].lower()]
                            next_node = condition.get('node', 'final')
                            if next_node != 'END':
                                workflow.add_edge(value_setter_name, next_node)
                            else:
                                workflow.add_edge(value_setter_name, END)
                    else:
                        logging.error(f"Conditions is not a list: {conditions}")
                        workflow.add_edge(previous_node, node_name)
                else:
                    logging.debug(f"Node '{previous_node}' does not have conditions")
                    workflow.add_edge(previous_node, node_name)

    async def build_compiled_workflow(self):
        """Build the LangGraph workflow with optional persistence."""
        workflow = StateGraph(self.GraphState)
        node_instances = []

        # Add final node
        def final_function(state):
            return state
        workflow.add_node('final', final_function)

        # First pass: Collect node instances
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

        # Process nodes
        for node_name, node_instance in node_instances:
            workflow.add_node(node_name, node_instance.build_compiled_workflow(
                graph_state_class=LangGraphScore.GraphState
            ))

        # Set entry point to first node
        first_node = node_instances[0][0]
        workflow.set_entry_point(first_node)

        # Add remaining edges
        for i in range(len(node_instances) - 1):
            current_node = node_instances[i][0]
            next_node = node_instances[i + 1][0]
            workflow.add_edge(current_node, next_node)

        # Add edge from last node to final
        workflow.add_edge(node_instances[-1][0], 'final')

        # Add output aliasing if needed
        if hasattr(self.parameters, 'output') and self.parameters.output is not None:
            output_aliasing_function = LangGraphScore.generate_output_aliasing_function(
                self.parameters.output
            )
            workflow.add_node('output_aliasing', output_aliasing_function)
            workflow.add_edge('final', 'output_aliasing')
            final_node = 'output_aliasing'
        else:
            final_node = 'final'

        # Add edge to END
        workflow.add_edge(final_node, END)

        try:
            # Compile with checkpointer only if configured
            app = workflow.compile(
                checkpointer=self.checkpointer if self.checkpointer else None
            )
            
            # Store node instances for later token usage calculation
            self.node_instances = node_instances
            
            return app
            
        except Exception as e:
            logging.error(f"Error compiling workflow: {str(e)}")
            logging.error(f"Full exception: {traceback.format_exc()}")
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
        Generate and save a visual representation of the workflow graph.

        This method creates a graphical visualization of the workflow using Graphviz.
        It represents nodes and edges of the workflow, with different colors for
        start, end, and intermediate nodes.

        :param output_path: The file path where the graph image will be saved.
        """
        from IPython.display import Image, display
        from langchain_core.runnables.graph import CurveStyle, MermaidDrawMethod, NodeStyles

        graph = self.workflow.get_graph()
        with open("tmp/workflow_graph.png", "wb") as output_file:
            output_file.write(graph.draw_mermaid_png(draw_method=MermaidDrawMethod.API))

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
        attributes: Dict[str, Any] = {}
        output_aliases: Dict[str, str] = {}

        for instance in instances:
            for attr_name, attr_type in instance.GraphState.__annotations__.items():
                if attr_name in attributes:
                    if attributes[attr_name] != attr_type:
                        raise TypeError(f"Inconsistent type for attribute '{attr_name}': "
                                        f"{attributes[attr_name]} != {attr_type}")
                else:
                    attributes[attr_name] = attr_type

            # Collect output aliases from node instances
            if hasattr(instance.parameters, 'output') and instance.parameters.output is not None:
                for alias, original in instance.parameters.output.items():
                    if original in attributes:
                        attributes[alias] = attributes[original]
                        output_aliases[alias] = attributes[original]
                    else:
                        raise ValueError(f"Original attribute '{original}' not found in GraphState")

        # Collect output aliases from main LangGraphScore parameter
        if hasattr(self.parameters, 'output'):
            for alias, original in self.parameters.output.items():
                if original in output_aliases:
                    output_aliases[alias] = output_aliases[original]
                elif original in attributes:
                    output_aliases[alias] = attributes[original]
                else:
                    raise ValueError(f"Original attribute '{original}' not found in GraphState")

        # Add output aliases to attributes
        for alias, attr_type in output_aliases.items():
            attributes[alias] = attr_type

        CombinedGraphState = create_model("CombinedGraphState", **{k: (v, None) for k, v in attributes.items()}, __base__=LangGraphScore.GraphState)
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
            logging.debug(f"Output aliasing: {output_mapping}")
            for alias, original in output_mapping.items():
                if hasattr(state, original):
                    setattr(state, alias, getattr(state, original))
            return state
        return output_aliasing

    @staticmethod
    def _import_class(class_name):
        """Import a class from the nodes module."""
        try:
            # Import from the nodes package
            module = importlib.import_module('plexus.scores.nodes')
            logging.info(f"Attempting to get class {class_name} from nodes module")
            logging.info(f"Module contents: {dir(module)}")
            
            # List all modules in plexus.scores.nodes
            import pkgutil
            package = importlib.import_module('plexus.scores.nodes')
            modules = [name for _, name, _ in pkgutil.iter_modules(package.__path__)]
            logging.info(f"Available modules in plexus.scores.nodes: {modules}")
            
            # Try to import specific module
            specific_module_path = f'plexus.scores.nodes.{class_name}'
            logging.info(f"Attempting to import from specific path: {specific_module_path}")
            specific_module = importlib.import_module(specific_module_path)
            logging.info(f"Specific module contents: {dir(specific_module)}")
            
            # Check what's actually in the module
            for item_name in dir(specific_module):
                item = getattr(specific_module, item_name)
                if not item_name.startswith('_'):  # Skip private attributes
                    logging.info(f"Item '{item_name}' is of type: {type(item)}")
                    if isinstance(item, type):
                        logging.info(f"Found class: {item_name}")
                        if item_name == class_name:
                            logging.info(f"Found matching class {class_name}")
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
    def create_value_setter_node(output):
        def value_setter(state):
            state.value = output.get('value', state.value)
            state.explanation = output.get('explanation', state.explanation)
            logging.info(f"Value setter node: Set value to: {state.value}, explanation to: {state.explanation}")
            return state
        return value_setter

    async def predict(self, context, model_input: Optional[Union[Score.Input, dict]]):
        try:
            def truncate_strings(obj, max_length=80):
                if isinstance(obj, dict):
                    return {k: truncate_strings(v) for k, v in obj.items()}
                elif isinstance(obj, str):
                    return f"{obj[:max_length]}..." if len(obj) > max_length else obj
                return obj

            # Handle resume case (model_input is None)
            if model_input is None:
                logging.info("Resuming from checkpoint - passing None to continue")
                thread_id = None  # Will be in config
                initial_state = None  # Let LangGraph use checkpoint
            else:
                # Normal execution with input
                thread_id = model_input.metadata.get('content_id')
                if not thread_id:
                    thread_id = str(uuid.uuid4())
                    logging.warning(
                        f"No content_id found in metadata, using generated UUID: {thread_id}"
                    )
                
                initial_state = self.GraphState(
                    text=self.preprocess_text(model_input.text),
                    metadata=model_input.metadata,
                    results={
                        result['name']: {
                            "id": result['id'],
                            "value": result['result'].value if result['result'] else None,
                            "explanation": result['result'].explanation if result['result'] else None
                        }
                        for result in model_input.results or []
                    },
                    messages=None
                ).model_dump()

            logging.info(f"Using content_id as thread_id: {thread_id}")
            config = {
                "configurable": {
                    "thread_id": str(thread_id) if thread_id else None
                }
            }

            batch_mode = os.getenv('PLEXUS_ENABLE_BATCH_MODE', '').lower() == 'true'
            breakpoints_enabled = os.getenv('PLEXUS_ENABLE_LLM_BREAKPOINTS', '').lower() == 'true'
            logging.info(
                f"Mode: batch_mode={batch_mode}, breakpoints_enabled={breakpoints_enabled}"
            )

            final_result = await self.workflow.ainvoke(
                initial_state,  # Will be None when resuming
                config=config
            )
            logging.info(f"Raw workflow result: {final_result}")

            # Check for breakpoint state FIRST before any other processing
            if isinstance(final_result, dict) and (
                final_result.get('at_llm_breakpoint') or 
                final_result.get('should_end')
            ):
                logging.info("Found breakpoint state, creating batch job")
                if batch_mode:
                    # Initialize client manager with context from metadata
                    client_manager = ClientManager.for_scorecard(
                        account_key=model_input.metadata.get('account_key'),
                        scorecard_key=model_input.metadata.get('scorecard_key'),
                        score_name=model_input.metadata.get('score_name')
                    )
                    
                    # Create a fully serializable copy of the state
                    serializable_state = {}
                    for key, value in final_result.items():
                        if key == 'messages':
                            if isinstance(value, list):
                                serializable_state[key] = [
                                    {
                                        'type': msg.get('type', ''),
                                        'content': msg.get('content', ''),
                                        '_type': msg.get('_type', '')
                                    } if isinstance(msg, dict) else
                                    {
                                        'type': msg.__class__.__name__.lower().replace(
                                            'message', ''
                                        ),
                                        'content': msg.content,
                                        '_type': msg.__class__.__name__
                                    }
                                    for msg in value
                                ]
                        elif key == 'chat_history':
                            if isinstance(value, list):
                                serializable_state[key] = [
                                    {
                                        'type': msg.__class__.__name__.lower().replace(
                                            'message', ''
                                        ),
                                        'content': msg.content,
                                        '_type': msg.__class__.__name__
                                    }
                                    for msg in value
                                ]
                        else:
                            serializable_state[key] = value
                    
                    logging.info(f"Created serializable state: {serializable_state}")
                    
                    # Create batch job with serializable state
                    try:
                        # Get the score ID from the client manager's context
                        score_id = client_manager._resolve_score_id()
                        logging.info(f"Resolved score ID: {score_id}")
                        
                        scoring_job, batch_job = client_manager.api_client.batch_scoring_job(
                            itemId=thread_id,
                            scorecardId=client_manager._resolve_scorecard_id(),
                            accountId=client_manager._resolve_account_id(),
                            model_provider=self.parameters.model_provider,
                            model_name=self.parameters.model_name,
                            provider='OPENAI',
                            scoreId=score_id,
                            parameters={
                                'state': serializable_state,
                                'thread_id': thread_id,
                                'breakpoint': True,
                                'original_metadata': model_input.metadata,
                                'model_provider': self.parameters.model_provider,
                                'model_name': self.parameters.model_name
                            }
                        )
                        
                        logging.info(f"Created batch job {batch_job.id} for thread {thread_id}")
                        
                        # Clean up before raising the exception
                        await self.cleanup()
                        
                        raise BatchProcessingPause(
                            thread_id=thread_id,
                            state=serializable_state,
                            message=f"Workflow paused for batch processing. Batch job ID: {batch_job.id}. Thread ID: {thread_id}"
                        )
                    except Exception as e:
                        logging.error(f"Failed to create batch job: {str(e)}")
                        await self.cleanup()
                        raise BatchProcessingPause(
                            thread_id=thread_id,
                            state=serializable_state,
                            message=f"Workflow paused for batch processing. Thread ID: {thread_id}"
                        )
                else:
                    raise NodeInterrupt("Workflow paused at breakpoint")

            # Return None if we hit a breakpoint - no results to process yet
            if final_result.get('at_llm_breakpoint') or final_result.get('should_end'):
                logging.info("Workflow interrupted at breakpoint - no results to process")
                return None

            # Only continue processing if we have a valid result
            if isinstance(final_result, dict):
                logging.info(f"Final result keys: {final_result.keys()}")
                
                # Unwrap output_aliasing if present
                result_dict = final_result.get('output_aliasing', final_result)
                logging.info(f"Result dict after unwrapping: {result_dict}")
                
                # Check for classification or value
                if result_dict.get('classification') is not None:
                    logging.info(f"Creating result from classification: {result_dict['classification']}")
                    result = [self.Result(
                        parameters=self.parameters,
                        value=result_dict['classification'],
                        explanation=result_dict.get('explanation', '')
                    )]
                    logging.info(f"Created result object: {result}")
                    return result
                elif result_dict.get('value') is not None:
                    logging.info(f"Creating result from value: {result_dict['value']}")
                    result = [self.Result(
                        parameters=self.parameters,
                        value=result_dict['value'],
                        explanation=result_dict.get('explanation', '')
                    )]
                    logging.info(f"Created result object: {result}")
                    return result
                else:
                    logging.error("No classification or value found in result")
                    logging.error(f"Available keys: {list(result_dict.keys())}")
                    return None

            # If we get here without returning, something went wrong
            logging.error("Workflow completed without producing a valid result")
            logging.error(f"Final event: {final_result}")
            return None

        except BatchProcessingPause:
            # Expected condition - let it propagate up
            raise
        except Exception as e:
            logging.error(f"Error during prediction: {e}")
            logging.error(f"Full traceback: {traceback.format_exc()}")
            raise

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

