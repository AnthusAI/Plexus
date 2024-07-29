from abc import ABC, abstractmethod

from langgraph.graph import StateGraph

class BaseNode(ABC):
    """
    Abstract base class for nodes in a LangGraph workflow.

    This class serves as a template for creating nodes that can be slotted into
    the main orchestration workflow of a LangGraphScore. Subclasses must implement
    the build_compiled_workflow method to define their specific behavior within
    the larger graph structure.
    """

    @abstractmethod
    def build_compiled_workflow(self) -> StateGraph:
        """
        Build and return a compiled LangGraph workflow.

        This method must be implemented by all subclasses to define the specific
        sub-graph that this node represents in the larger workflow.

        Returns:
            StateGraph: A compiled LangGraph workflow that can be used as a
                        sub-graph node in the main LangGraphScore workflow.
        """
        pass