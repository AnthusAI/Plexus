"""
Base node class for APOS workflow.
"""
from typing import Any, Dict, Optional, Callable
from abc import ABC, abstractmethod
import logging

from langgraph.graph import StateGraph
from langchain_core.runnables import RunnableConfig

from plexus.apos.graph_state import APOSState
from plexus.apos.config import APOSConfig
from plexus.apos.models import OptimizationStatus

logger = logging.getLogger('plexus.apos.nodes')


class APOSNode(ABC):
    """
    Base class for all APOS workflow nodes.
    Provides common functionality and ensures consistent interface.
    """
    
    def __init__(self, config: APOSConfig):
        """Initialize the node with configuration."""
        self.config = config
        self._setup_node()
    
    @abstractmethod
    def _setup_node(self) -> None:
        """Set up any node-specific components (LLMs, chains, etc)."""
        pass
    
    @abstractmethod
    def get_node_handler(self) -> Callable[[APOSState], Dict[str, Any]]:
        """
        Get the main handler function for this node.
        
        Returns:
            Callable that takes APOSState and returns dict of updates
        """
        pass
    
    def handle_error(self, error: Exception, state: APOSState) -> Dict[str, Any]:
        """
        Handle errors that occur during node execution.
        
        Args:
            error: The exception that occurred
            state: Current state when error occurred
            
        Returns:
            Dict of state updates to apply
        """
        # Increment retry count
        state.retry_count += 1
        
        # If we've exceeded max retries, mark as failed
        if state.retry_count >= state.max_retries:
            state.status = OptimizationStatus.FAILED
            state.metadata["error"] = str(error)
            return state.dict()
            
        # Otherwise return current state for retry
        return state.dict()
    
    def add_to_graph(
        self,
        graph: StateGraph,
        node_name: str,
        config: Optional[RunnableConfig] = None
    ) -> None:
        """
        Add this node to a StateGraph.
        
        Args:
            graph: The StateGraph to add to
            node_name: Name for this node in the graph
            config: Optional config for the node
        """
        handler = self.get_node_handler()
        
        # Wrap handler to unwrap state key from response
        async def wrapped_handler(state: APOSState) -> Dict[str, Any]:
            result = await handler(state)
            if isinstance(result, dict) and "state" in result:
                return result["state"]
            return result
            
        if config:
            graph.add_node(node_name, wrapped_handler, config=config)
        else:
            graph.add_node(node_name, wrapped_handler) 