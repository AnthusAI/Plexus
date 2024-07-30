from abc import ABC, abstractmethod
from langgraph.graph import StateGraph
from typing import Type
from plexus.CustomLogging import logging
from plexus.scores.LangGraphScore import LangGraphScore
from langgraph.graph import StateGraph, END

class BaseNode(ABC):
    """
    Abstract base class for nodes in a LangGraph workflow.

    This class serves as a template for creating nodes that can be slotted into
    the main orchestration workflow of a LangGraphScore. Subclasses must implement
    the build_compiled_workflow method to define their specific behavior within
    the larger graph structure.
    """

    class Parameters(LangGraphScore.Parameters):
        """
        Parameters for this node.  Based on the LangGraphScore.Parameters class.
        """

    class GraphState(LangGraphScore.GraphState):
        pass

    def __init__(self, **kwargs):
        self.parameters = kwargs

    @abstractmethod
    def add_core_nodes(self, workflow: StateGraph) -> StateGraph:
        """
        Build and return a core LangGraph workflow.
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
        if 'input' in self.parameters and self.parameters['input'] is not None:
            input_aliasing_function = LangGraphScore.generate_input_aliasing_function(self.parameters['input'])
            workflow.add_node('input_aliasing', input_aliasing_function)

        workflow = self.add_core_nodes(workflow)
        
        if 'input_aliasing' in workflow.nodes:
            first_node = list(workflow.nodes.keys())[0]
            second_node = list(workflow.nodes.keys())[1]
            workflow.add_edge(first_node, second_node)

        # Add output aliasing function if needed
        if 'output' in self.parameters and self.parameters['output'] is not None:
            output_aliasing_function = LangGraphScore.generate_output_aliasing_function(self.parameters['output'])
            workflow.add_node('output_aliasing', output_aliasing_function)
            workflow.add_edge(list(workflow.nodes.keys())[-2], 'output_aliasing')

        if workflow.nodes:
            workflow.set_entry_point(next(iter(workflow.nodes)))

        if workflow.nodes:
            last_node = list(workflow.nodes.keys())[-1]
            workflow.add_edge(last_node, END)

        app = workflow.compile()

        logging.info(f"Graph for {self.__class__.__name__}:")
        app.get_graph().print_ascii()

        return app
