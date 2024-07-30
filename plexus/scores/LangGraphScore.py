import os
import logging
import traceback
import graphviz
from langsmith import Client
from types import FunctionType
from typing import Type, Tuple, Literal, Optional, Any, TypedDict, List, Dict
from pydantic import BaseModel, ConfigDict, create_model

from plexus.scores.Score import Score

from langchain_core.language_models import BaseLanguageModel
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from langchain_aws import ChatBedrock
from langchain_openai import AzureChatOpenAI, ChatOpenAI
from langchain_google_vertexai import ChatVertexAI
from langchain_community.callbacks import OpenAICallbackHandler

from langgraph.graph import StateGraph, END

from openai_cost_calculator.openai_cost_calculator import calculate_cost

# Logging.
from langchain.globals import set_debug
set_debug(True)

class LangGraphScore(Score):
    """
    A Score class that uses language models to perform text classification.

    This class initializes and manages a language model for processing text inputs,
    tracks token usage, and provides methods for text classification and cost calculation.
    """

    MAX_RETRY_ATTEMPTS = 20
    
    class Parameters(Score.Parameters):
        model_config = ConfigDict(protected_namespaces=())
        model_provider: Literal["ChatOpenAI", "AzureChatOpenAI", "BedrockChat", "ChatVertexAI"] = "AzureChatOpenAI"
        model_name: Optional[str] = None
        model_region: Optional[str] = None
        temperature: Optional[float] = 0.1
        max_tokens: Optional[int] = 500
        graph: Optional[list[dict]] = None
        input: Optional[dict] = None
        output: Optional[dict] = None

    class Result(Score.Result):
        """
        Model output containing the validation result.

        :param explanation: Detailed explanation of the validation result.
        """
        ...
        explanation: str

    class GraphState(BaseModel):
        text: str
        is_not_empty: Optional[bool]
        value: Optional[str]
        explanation: Optional[str]
        reasoning: Optional[str]

    def __init__(self, **parameters):
        """
        Initialize the LangGraphScore.

        This method sets up the score parameters, initializes the token counter,
        and sets up the language model specified in the configuration.

        :param parameters: Configuration parameters for the score and language model.
        """
        super().__init__(**parameters)
        self.token_counter = self._create_token_counter()
        self.openai_callback = None
        self.langsmith_client = Client()
        self.model = self._initialize_model()

    def _create_token_counter(self):
        """
        Create and return a token counter callback.

        This method sets up a custom callback handler to track token usage
        across different language model providers. It logs detailed information
        about each LLM call and accumulates token counts.

        :return: An instance of TokenCounterCallback.
        """
        class TokenCounterCallback(BaseCallbackHandler):
            def __init__(self):
                self.prompt_tokens = 0
                self.completion_tokens = 0
                self.total_tokens = 0
                self.llm_calls = 0

            def on_llm_start(self, serialized, prompts, **kwargs):
                self.llm_calls += 1
                logging.info(f"LLM Call {self.llm_calls} started")

            def on_llm_end(self, response: LLMResult, **kwargs):
                logging.info(f"LLM Call {self.llm_calls} ended")
                logging.info(f"Response type: {type(response)}")
                logging.info(f"Response content: {response}")

                usage = {}
                if isinstance(response, LLMResult):
                    if response.llm_output:
                        usage = response.llm_output.get("usage", {})
                        logging.info(f"Token usage from llm_output: {usage}")
                    else:
                        logging.info("No llm_output in response")
                        
                    if response.generations and response.generations[0]:
                        generation = response.generations[0][0]
                        if hasattr(generation, 'generation_info') and generation.generation_info:
                            usage = generation.generation_info.get("token_usage", {})
                            logging.info(f"Token usage from generation_info: {usage}")
                        elif hasattr(generation, 'message') and hasattr(generation.message, 'usage_metadata'):
                            usage = generation.message.usage_metadata
                            logging.info(f"Token usage from usage_metadata: {usage}")
                        else:
                            logging.info("No token usage information found in generation")
                    else:
                        logging.info("No generations in response")

                self.prompt_tokens += usage.get("input_tokens", 0) or usage.get("prompt_tokens", 0)
                self.completion_tokens += usage.get("output_tokens", 0) or usage.get("completion_tokens", 0)
                self.total_tokens += usage.get("total_tokens", 0) or (self.prompt_tokens + self.completion_tokens)

                logging.info(f"Current cumulative token usage - Prompt: {self.prompt_tokens}, Completion: {self.completion_tokens}, Total: {self.total_tokens}")

            def on_chain_end(self, outputs, **kwargs):
                logging.info(f"Chain ended. Cumulative token usage - Prompt: {self.prompt_tokens}, Completion: {self.completion_tokens}, Total: {self.total_tokens}")

        return TokenCounterCallback()

    def _initialize_model(self) -> BaseLanguageModel:
        """
        Initialize and return the appropriate language model based on the configured provider.

        This method sets up the specified language model with retry logic and callbacks
        for token counting. It supports various model providers including OpenAI, Azure,
        Amazon Bedrock, and Google Vertex AI.

        :return: An initialized BaseLanguageModel with retry logic and callbacks.
        :raises ValueError: If an unsupported model provider is specified.
        """
        max_tokens = self.parameters.max_tokens

        if self.parameters.model_provider in ["AzureChatOpenAI", "ChatOpenAI"]:
            self.openai_callback = OpenAICallbackHandler()
            callbacks = [self.openai_callback]
            
            if self.parameters.model_provider == "AzureChatOpenAI":
                base_model = AzureChatOpenAI(
                    azure_endpoint=os.environ.get("AZURE_API_BASE"),
                    api_version=os.environ.get("AZURE_API_VERSION"),
                    api_key=os.environ.get("AZURE_API_KEY"),
                    model=self.parameters.model_name,
                    temperature=self.parameters.temperature,
                    max_tokens=max_tokens
                )
            else:  # ChatOpenAI
                base_model = ChatOpenAI(
                    model=self.parameters.model_name,
                    api_key=os.environ.get("OPENAI_API_KEY"),
                    temperature=self.parameters.temperature,
                    max_tokens=max_tokens
                )
        elif self.parameters.model_provider == "BedrockChat":
            base_model = ChatBedrock(
                model_id=self.parameters.model_name or "anthropic.claude-3-5-sonnet-20240620-v1:0",
                model_kwargs={
                    "temperature": self.parameters.temperature,
                    "max_tokens": max_tokens
                },
                region_name=self.parameters.model_region or "us-east-1"
            )
            callbacks = [self.token_counter]
        elif self.parameters.model_provider == "ChatVertexAI":
            base_model = ChatVertexAI(
                model=self.parameters.model_name or "gemini-1.5-flash-001",
                temperature=self.parameters.temperature,
                max_output_tokens=max_tokens
            )
            callbacks = [self.token_counter]
        else:
            raise ValueError(f"Unsupported model provider: {self.parameters.model_provider}")

        return base_model.with_retry(
            retry_if_exception_type=(Exception,),
            wait_exponential_jitter=True,
            stop_after_attempt=self.MAX_RETRY_ATTEMPTS
        ).with_config(
            callbacks=callbacks,
            max_tokens=max_tokens
        )

    def _parse_validation_result(self, output: str) -> Tuple[str, str]:
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
        try:
            logging.info("Starting graph visualization generation")
            
            # Get the graph
            graph = self.workflow.get_graph()
            logging.info("Graph obtained from workflow")

            # Ensure the directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            logging.info(f"Output directory created: {os.path.dirname(output_path)}")

            # Create a new directed graph
            dot = graphviz.Digraph(comment='Workflow Graph')
            dot.attr(rankdir='TB', size='8,5', dpi='300')
            dot.attr('node', shape='rectangle', style='rounded,filled', fontname='Arial', fontsize='10', margin='0.2,0.1')
            dot.attr('edge', fontname='Arial', fontsize='8')

            # Color scheme
            colors = {
                'start': '#73fa97',  # Light green
                'end': '#f086bb',    # Light pink
                'other': '#deeffa'   # Light blue
            }

            # Add nodes
            for node_id, node in graph.nodes.items():
                node_label = node_id.replace('\n', '\\n')  # Preserve newlines in labels
                if node_id == '__start__':
                    dot.node(node_id, 'Start', fillcolor=colors['start'])
                elif node_id == '__end__':
                    dot.node(node_id, 'End', fillcolor=colors['end'])
                else:
                    dot.node(node_id, node_label, fillcolor=colors['other'])

            # Add edges
            for edge in graph.edges:
                source = edge.source
                target = edge.target
                if edge.conditional:
                    label = str(edge.data)  # Convert edge data to string
                    dot.edge(source, target, label=label, color='#666666')
                else:
                    dot.edge(source, target, color='#666666')

            # # Save the graph as a PNG file
            # dot.render(output_path, format='png', cleanup=True)
            # logging.info(f"Graph visualization saved to {output_path}")

        except Exception as e:
            error_msg = f"Failed to generate graph visualization: {str(e)}\n{traceback.format_exc()}"
            logging.error(error_msg)

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
        if self.parameters.model_provider in ["AzureChatOpenAI", "ChatOpenAI"]:
            return {
                "prompt_tokens": self.openai_callback.prompt_tokens,
                "completion_tokens": self.openai_callback.completion_tokens,
                "total_tokens": self.openai_callback.total_tokens,
                "successful_requests": self.openai_callback.successful_requests
            }
        else:
            return {
                "prompt_tokens": self.token_counter.prompt_tokens,
                "completion_tokens": self.token_counter.completion_tokens,
                "total_tokens": self.token_counter.total_tokens,
                "successful_requests": self.token_counter.llm_calls
            }

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
            if 'output' in instance.parameters:
                for alias, original in instance.parameters['output'].items():
                    if original in attributes:
                        output_aliases[alias] = attributes[original]
                    else:
                        raise ValueError(f"Original attribute '{original}' not found in GraphState")

        # Collect output aliases from main LangGraphScore parameter
        if hasattr(self.parameters, 'output'):
            for alias, original in self.parameters.output.items():
                if original in attributes:
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
            logging.info(f"Output aliasing: {output_mapping}")
            for alias, original in output_mapping.items():
                if hasattr(state, original):
                    setattr(state, alias, getattr(state, original))
            return state
        return output_aliasing

    def build_compiled_workflow(self):
        """
        Build the LangGraph workflow.
        """
        def _import_class(class_name):
            default_module_path = 'plexus.scores.nodes.'
            full_class_name = default_module_path + class_name
            components = full_class_name.split('.')
            module_path = '.'.join(components[:-1])
            class_name = components[-1]
            module = __import__(module_path, fromlist=[class_name])
            imported_class = getattr(module, class_name)
            logging.info(f"Imported {imported_class} from {module_path}")
            return imported_class

        # First pass: Collect node instances
        node_instances = []
        node_names = []
        if hasattr(self.parameters, 'graph') and isinstance(self.parameters.graph, list):
            for node_config in self.parameters.graph:
                if 'class' in node_config and 'name' in node_config:
                    node_class_name = node_config['class']
                    node_name = node_config['name']
                    node_class = _import_class(node_class_name)
                    logging.info(f"Node class: {node_class}")
                    node_instance = node_class(**node_config)
                    node_instances.append((node_name, node_instance))
                    node_names.append(node_name)
        else:
            raise ValueError("Invalid or missing graph configuration in parameters.")

        # Create the combined GraphState class
        combined_graphstate_class = self.create_combined_graphstate_class([instance for _, instance in node_instances])

        # Second pass: Create workflow and add nodes
        workflow = StateGraph(combined_graphstate_class)

        # Add input aliasing function if needed
        if hasattr(self.parameters, 'input') and self.parameters.input is not None:
            input_aliasing_function = LangGraphScore.generate_input_aliasing_function(self.parameters.input)
            workflow.add_node('input_aliasing', input_aliasing_function)

        current_node = None
        for node_name, node_instance in node_instances:
            workflow.add_node(node_name,
                node_instance.build_compiled_workflow(
                    graph_state_class=combined_graphstate_class))
            if len(workflow.nodes) > 1:
                previous_node = list(workflow.nodes.keys())[-2]
                workflow.add_edge(previous_node, node_name)
            current_node = node_name

        # Add output aliasing function if needed
        if hasattr(self.parameters, 'output') and self.parameters.output is not None:
            output_aliasing_function = LangGraphScore.generate_output_aliasing_function(self.parameters.output)
            workflow.add_node('output_aliasing', output_aliasing_function)
            workflow.add_edge(current_node, 'output_aliasing')

        # Start at the first node in the list.  End at the last node.
        if workflow.nodes:
            workflow.set_entry_point(next(iter(workflow.nodes)))
            last_node = list(workflow.nodes.keys())[-1]
            workflow.add_edge(last_node, END)

        app = workflow.compile()

        logging.info(f"Graph for {self.__class__.__name__}:")
        app.get_graph().print_ascii()

        return app

    def predict(self, context, model_input: Score.Input):
        text = model_input.text

        app = self.build_compiled_workflow()
        
        # TODO: Remove this truncation.  It's for debugging.
        text = text[:100]

        result = app.invoke({"text": text.lower()})
        logging.info(f"LangGraph result: {result}")

        return [
            LangGraphScore.Result(
                name  =       self.parameters.score_name,
                value =       result["before"],
                explanation = result["after"]
            )
        ]