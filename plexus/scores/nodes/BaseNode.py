from abc import ABC, abstractmethod
from langgraph.graph import StateGraph
from typing import Type, Optional, Literal, Any
import pydantic
from pydantic import ConfigDict, BaseModel
from plexus.CustomLogging import logging
from plexus.LangChainUser import LangChainUser
from plexus.scores.LangGraphScore import LangGraphScore
from langgraph.graph import StateGraph, END
from langchain_core.prompts import ChatPromptTemplate

class BaseNode(ABC, LangChainUser):
    """
    Abstract base class for nodes in a LangGraph workflow.

    This class serves as a template for creating nodes that can be slotted into
    the main orchestration workflow of a LangGraphScore. Subclasses must implement
    the build_compiled_workflow method to define their specific behavior within
    the larger graph structure.
    """

    class GraphState(LangGraphScore.GraphState):
        pass

    class Parameters(LangChainUser.Parameters):
        ...
        input:  Optional[dict] = None
        output: Optional[dict] = None
        system_message: Optional[str] = None
        user_message: Optional[str] = None
        example_refinement_message: Optional[str] = None
        single_line_messages: bool = False
        name: Optional[str] = None

    def __init__(self, **parameters):
        super().__init__(**parameters)
        self.parameters = self.Parameters(**parameters)

    @property
    def node_name(self) -> str:
        """Get the node name from parameters."""
        if not hasattr(self, 'parameters') or not self.parameters.name:
            raise ValueError("Node name is required but not provided in parameters")
        return self.parameters.name

    def log_state(self, state, input_state=None, output_state=None, node_suffix=""):
        """
        Log the current state to the trace.node_results list in the state's metadata.
        
        Parameters
        ----------
        state : GraphState
            The current state object
        input_state : dict, optional
            The input state to log
        output_state : dict, optional
            The output state to log
        node_suffix : str, optional
            A suffix to add to the node name for more specific logging
            
        Returns
        -------
        GraphState
            A new state object with the updated trace information
        """
        # Use empty dicts if input_state or output_state not provided
        input_state = input_state or {}
        output_state = output_state or {}
            
        # Create the node name with optional suffix
        full_node_name = self.node_name
        if node_suffix:
            full_node_name = f"{full_node_name}.{node_suffix}"
            
        # Create the node result
        node_result = {
            "node_name": full_node_name,
            "input": input_state,
            "output": output_state
        }
        
        # Get the state as a dictionary
        if hasattr(state, 'dict'):
            state_dict = state.dict()
        elif hasattr(state, 'model_dump'):
            state_dict = state.model_dump()
        else:
            state_dict = dict(state)
            
        # Initialize metadata if it doesn't exist
        if 'metadata' not in state_dict or state_dict['metadata'] is None:
            state_dict['metadata'] = {}
            
        # Initialize trace if it doesn't exist
        if 'trace' not in state_dict['metadata']:
            state_dict['metadata']['trace'] = {}
            
        # Initialize node_results if it doesn't exist
        if 'node_results' not in state_dict['metadata']['trace']:
            state_dict['metadata']['trace']['node_results'] = []
            
        # Add the new node result
        state_dict['metadata']['trace']['node_results'].append(node_result)
        
        # Create and return a new state object
        return self.GraphState(**state_dict)

    def get_prompt_templates(self):
        """
        Get a list of prompt templates for the node, by looking for the "system_message" parameter for
        a system message, and the "user_message" parameter for a human message.  If either is missing or
        empty, the method will skip that template.
        """
        message_types = ['system_message', 'user_message']
        messages = []
        for message_type in message_types:
            if hasattr(self.parameters, message_type) and getattr(self.parameters, message_type):
                content = getattr(self.parameters, message_type)
                # Convert any message to single line if configured
                if self.parameters.single_line_messages:
                    content = ' '.join(content.split())
                role = message_type.split('_')[0]
                messages.append((role, content))
        
        if messages:
            return [
                ChatPromptTemplate.from_messages(
                    messages,
                    template_format = "jinja2"
                )
            ]
        else:
            return []

    def get_example_refinement_template(self):
        """
        Get the example refinement message for the node.
        """
        return self.parameters.example_refinement_message

    @abstractmethod
    def add_core_nodes(self, workflow: StateGraph) -> StateGraph:
        """Build and return a core LangGraph workflow.
        The node name is available as self.node_name when needed.
        """
        pass

    def build_compiled_workflow(self, graph_state_class: Type[LangGraphScore.GraphState]) -> StateGraph:
        """
        Build and return a compiled LangGraph workflow.

        This method must be implemented by all subclasses to define the specific
        sub-graph that this node represents in the larger workflow.

        Returns:
            StateGraph: A compiled LangGraph workflow that can be used as a
                        sub-graph node in the main LangGraphScore workflow.
        """
        workflow = StateGraph(graph_state_class)

        # Add input aliasing function if needed
        if hasattr(self.parameters, 'input') and self.parameters.input is not None:
            input_aliasing_function = LangGraphScore.generate_input_aliasing_function(self.parameters.input)
            workflow.add_node('input_aliasing', input_aliasing_function)

        # Call add_core_nodes (node name is available via self.node_name)
        workflow = self.add_core_nodes(workflow)
        
        if 'input_aliasing' in workflow.nodes:
            first_node = list(workflow.nodes.keys())[0]
            second_node = list(workflow.nodes.keys())[1]
            workflow.add_edge(first_node, second_node)

        # Add output aliasing function if needed
        if hasattr(self.parameters, 'output') and self.parameters.output is not None:
            output_aliasing_function = LangGraphScore.generate_output_aliasing_function(self.parameters.output)
            workflow.add_node('output_aliasing', output_aliasing_function)
            workflow.add_edge(list(workflow.nodes.keys())[-2], 'output_aliasing')
        
        # Add node result storage function
        def store_node_result(state):
            """Store this node's result under the node name for template access by other nodes."""
            logging.info(f"=== Node Result Storage for '{self.node_name}' ===")
            
            # Create node result object
            node_result = {}
            if hasattr(state, 'classification') and state.classification is not None:
                node_result['classification'] = state.classification
            if hasattr(state, 'explanation') and state.explanation is not None:
                node_result['explanation'] = state.explanation
            if hasattr(state, 'value') and state.value is not None:
                node_result['value'] = state.value
            if hasattr(state, 'confidence') and state.confidence is not None:
                node_result['confidence'] = state.confidence
                
            # Create new state with node result stored under node name
            new_state = state.model_dump()
            new_state[self.node_name] = node_result
            
            logging.info(f"Stored node result under '{self.node_name}': {node_result}")
            return state.__class__(**new_state)
        
        # Add the node result storage as the final step
        logging.info(f"Adding store_node_result node for '{self.node_name}'")
        workflow.add_node('store_node_result', store_node_result)
        
        # Connect store_node_result to END
        workflow.add_edge('store_node_result', END)
        
        # Modify existing edges to route through store_node_result instead of directly to END
        # This requires replacing END edges with edges to store_node_result
        logging.info(f"Redirecting workflow termination through store_node_result for '{self.node_name}'")

        if workflow.nodes:
            workflow.set_entry_point(next(iter(workflow.nodes)))

        if workflow.nodes:
            # Connect the final node (store_node_result) to END
            workflow.add_edge('store_node_result', END)

        app = workflow.compile()

        # logging.info(f"Graph for {self.__class__.__name__}:")
        # app.get_graph().print_ascii()

        async def invoke_workflow(state: Any) -> dict:
            # The state passed to a node is the Pydantic model object. Convert it to a dict.
            if isinstance(state, BaseModel):
                state_dict = state.model_dump()
            else:
                state_dict = dict(state) # Fallback
            
            final_node_state = await app.ainvoke(state_dict)
            
            # ✅ CRITICAL FIX: Merge ALL fields from final_node_state, not just hardcoded ones
            # This preserves node-level output aliases that were set during node execution
            for key, value in final_node_state.items():
                # Always update the main state with values from the node's final state
                # This ensures node-level output aliases (like non_qualifying_reason) are preserved
                state_dict[key] = value
            
            # Special handling for metadata trace to avoid complete replacement
            if 'metadata' in final_node_state and final_node_state.get('metadata') and final_node_state['metadata'].get('trace'):
                if 'metadata' not in state_dict or not state_dict.get('metadata'):
                    state_dict['metadata'] = {}
                if 'trace' not in state_dict['metadata']:
                    state_dict['metadata']['trace'] = {'node_results': []}
                
                # Get existing node names to avoid duplicates
                existing_node_names = {result.get('node_name') for result in state_dict['metadata']['trace']['node_results']}
                
                # Only add trace entries that don't already exist
                for trace_entry in final_node_state['metadata']['trace']['node_results']:
                    if trace_entry.get('node_name') not in existing_node_names:
                        state_dict['metadata']['trace']['node_results'].append(trace_entry)

            return state_dict

        return invoke_workflow