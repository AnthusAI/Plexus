from abc import ABC, abstractmethod
from langgraph.graph import StateGraph
from typing import Type, Optional, Literal
import pydantic
from pydantic import ConfigDict, BaseModel
from plexus.CustomLogging import logging
from plexus.LangChainUser import LangChainUser
from plexus.scores.LangGraphScore import LangGraphScore
from langgraph.graph import StateGraph, END
from langchain_core.prompts import ChatPromptTemplate

class BaseNode(ABC):
    """
    Abstract base class for nodes in a LangGraph workflow.

    This class serves as a template for creating nodes that can be slotted into
    the main orchestration workflow of a LangGraphScore. Subclasses must implement
    the build_compiled_workflow method to define their specific behavior within
    the larger graph structure.
    """

    class GraphState(LangGraphScore.GraphState):
        pass

    class Parameters(BaseModel):
        ...
        input:  Optional[dict] = None
        output: Optional[dict] = None

    def __init__(self, **parameters):
        combined_parameters_model = pydantic.create_model("CombinedParameters", __base__=(LangChainUser.Parameters, BaseNode.Parameters))
        self.parameters = combined_parameters_model(**parameters)

    def get_prompt_templates(self):
        """
        Get a list of prompt templates for the node, by looking for the "system" parameter for
        a system message, and the "human" parameter for a human message.  If either is missing or
        empty, the method will skip that template.
        """
        message_types = ['system_message', 'user_message']
        messages = []
        for message_type in message_types:
            if hasattr(self.parameters, message_type) and getattr(self.parameters, message_type):
                content = getattr(self.parameters, message_type)
                role = message_type.split('_')[0]
                messages.append((role, content))
        
        if messages:
            return [ChatPromptTemplate.from_messages(messages)]
        else:
            return []

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
        if hasattr(self.parameters, 'input') and self.parameters.input is not None:
            input_aliasing_function = LangGraphScore.generate_input_aliasing_function(self.parameters.input)
            workflow.add_node('input_aliasing', input_aliasing_function)

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

        if workflow.nodes:
            workflow.set_entry_point(next(iter(workflow.nodes)))

        if workflow.nodes:
            last_node = list(workflow.nodes.keys())[-1]
            workflow.add_edge(last_node, END)

        app = workflow.compile()

        logging.info(f"Graph for {self.__class__.__name__}:")
        app.get_graph().print_ascii()

        return app