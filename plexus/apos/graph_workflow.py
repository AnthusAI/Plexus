"""
Workflow graph implementation for APOS using LangGraph.
"""
import os
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig

from plexus.apos.config import APOSConfig, load_config
from plexus.apos.graph_state import APOSState
from plexus.apos.nodes.evaluation import EvaluationNode
from plexus.apos.nodes.mismatch import MismatchAnalyzerNode
from plexus.apos.nodes.pattern import PatternAnalyzerNode
from plexus.apos.nodes.optimizer import OptimizerNode
from plexus.apos.models import OptimizationStatus
from plexus.Scorecard import Scorecard
from plexus.Registries import scorecard_registry

logger = logging.getLogger('plexus.apos.workflow')

def create_apos_workflow(config: APOSConfig) -> StateGraph:
    """
    Create the APOS workflow graph.
    
    Args:
        config: APOS configuration
        
    Returns:
        Configured StateGraph for the optimization workflow
    """
    # Initialize graph with our state type
    workflow = StateGraph(APOSState)
    
    # Create nodes
    evaluator = EvaluationNode(config)
    mismatch_analyzer = MismatchAnalyzerNode(config)
    pattern_analyzer = PatternAnalyzerNode(config)
    optimizer = OptimizerNode(config)
    
    # Add nodes to graph
    evaluator.add_to_graph(workflow, "evaluate_prompts")
    mismatch_analyzer.add_to_graph(workflow, "analyze_mismatches")
    pattern_analyzer.add_to_graph(workflow, "analyze_patterns")
    optimizer.add_to_graph(workflow, "optimize_prompts")
    
    # Define conditional routing
    def should_continue(state: APOSState) -> str:
        """Determine next node based on state."""
        # Check if we've reached max iterations
        if state.current_iteration >= state.max_iterations - 1:  # -1 because we increment after
            state.status = OptimizationStatus.COMPLETED
            return END
            
        # Check for completion conditions
        if state.status == OptimizationStatus.COMPLETED:
            return END
            
        # Check for errors
        if state.status == OptimizationStatus.FAILED:
            return END
            
        # Check retry conditions
        if state.retry_count >= state.max_retries:
            state.status = OptimizationStatus.FAILED
            return END
            
        # Normal flow - continue optimization cycle
        return "evaluate_prompts"
    
    # Add edges to create optimization cycle:
    # evaluate -> mismatch analysis -> pattern analysis -> optimize -> evaluate
    workflow.add_edge("evaluate_prompts", "analyze_mismatches")
    workflow.add_edge("analyze_mismatches", "analyze_patterns")
    workflow.add_edge("analyze_patterns", "optimize_prompts")
    
    # Add conditional edges from optimizer back to evaluation or end
    workflow.add_conditional_edges(
        "optimize_prompts",
        should_continue,
        {
            "evaluate_prompts": "evaluate_prompts",
            END: END
        }
    )
    
    # Set entry point to evaluation
    workflow.set_entry_point("evaluate_prompts")
    
    # Compile the graph
    app = workflow.compile()
    
    return app


class APOSWorkflow:
    """
    High-level interface for running the APOS workflow.
    """
    
    def _load_scorecard(self) -> Any:
        """Load scorecard from registry."""
        # Load and register scorecards
        Scorecard.load_and_register_scorecards('scorecards/')
        
        # Get scorecard type from registry
        scorecard_type = scorecard_registry.get(self.scorecard_name)
        if scorecard_type is None:
            raise ValueError(f"Scorecard with name '{self.scorecard_name}' not found.")
        
        # Create scorecard instance
        scorecard = scorecard_type(scorecard=self.scorecard_name)
        logger.info(f"Loaded scorecard: {self.scorecard_name}")
        
        return scorecard
        
    def _create_workflow(self) -> StateGraph:
        """Create the workflow graph."""
        # Initialize graph with our state type
        workflow = StateGraph(APOSState)
        
        # Create nodes
        evaluator = EvaluationNode(self.config)
        mismatch_analyzer = MismatchAnalyzerNode(self.config)
        pattern_analyzer = PatternAnalyzerNode(self.config)
        optimizer = OptimizerNode(self.config)
        
        # Add nodes to graph
        evaluator.add_to_graph(workflow, "evaluate_prompts")
        mismatch_analyzer.add_to_graph(workflow, "analyze_mismatches")
        pattern_analyzer.add_to_graph(workflow, "analyze_patterns")
        optimizer.add_to_graph(workflow, "optimize_prompts")
        
        # Add edges to create optimization cycle:
        # evaluate -> mismatch analysis -> pattern analysis -> optimize -> evaluate
        workflow.add_edge("evaluate_prompts", "analyze_mismatches")
        workflow.add_edge("analyze_mismatches", "analyze_patterns")
        workflow.add_edge("analyze_patterns", "optimize_prompts")
        
        # Add conditional edges from optimizer back to evaluation or end
        def should_continue(state: APOSState) -> str:
            """Determine next node based on state."""
            # Check if we've reached max iterations
            if state.current_iteration >= state.max_iterations - 1:  # -1 because we increment after
                state.status = OptimizationStatus.COMPLETED
                return END
                
            # Check for completion conditions
            if state.status == OptimizationStatus.COMPLETED:
                return END
                
            # Check for errors
            if state.status == OptimizationStatus.FAILED:
                return END
                
            # Check retry conditions
            if state.retry_count >= state.max_retries:
                state.status = OptimizationStatus.FAILED
                return END
                
            # Normal flow - continue optimization cycle
            return "evaluate_prompts"
        
        workflow.add_conditional_edges(
            "optimize_prompts",
            should_continue,
            {
                "evaluate_prompts": "evaluate_prompts",
                END: END
            }
        )
        
        # Set entry point to evaluation
        workflow.set_entry_point("evaluate_prompts")
        
        return workflow
        
    def __init__(self, scorecard_name: str, score_name: str, config: Optional[APOSConfig] = None):
        """Initialize the workflow."""
        self.config = config or load_config()
        self.scorecard_name = scorecard_name
        self.score_name = score_name
        
        # Load scorecard
        self.scorecard = self._load_scorecard()
        
        # Get score config
        self.score_config = next((score for score in self.scorecard.scores 
                                if score['name'] == score_name), None)
        if not self.score_config:
            raise ValueError(f"Score '{score_name}' not found in scorecard")
            
        # Set initial prompts in scorecard
        if 'graph' in self.score_config and self.score_config['graph']:
            # Update first node's prompts
            node = self.score_config['graph'][0]
            self.system_message = node.get('system_message', '')
            self.user_message = node.get('user_message', '')
        else:
            # Fallback to direct score prompts if no graph
            self.system_message = self.score_config.get('system_message', '')
            self.user_message = self.score_config.get('user_message', '')
        
        # Create workflow graph
        self.graph = self._create_workflow()
        
        # Compile graph
        self.app = self.graph.compile()
        
    async def run(self) -> Dict[str, Any]:
        """Run the optimization workflow."""
        # Initialize state
        state = APOSState(
            system_message=self.system_message,
            user_message=self.user_message,
            scorecard_name=self.scorecard_name,
            score_name=self.score_name,
            target_accuracy=self.config.optimization.target_accuracy,
            max_iterations=self.config.optimization.max_iterations,
            status=OptimizationStatus.IN_PROGRESS,
            metadata={"scorecard": self.scorecard}
        )
        
        # Run workflow
        try:
            result = await self.app.ainvoke(state.dict())
            
            # Handle both wrapped and unwrapped states
            if isinstance(result, dict):
                if "state" in result:
                    # State is wrapped
                    return result
                else:
                    # State is unwrapped, wrap it
                    return {"state": result}
            else:
                raise ValueError("Invalid workflow result type")
                
        except Exception as e:
            logger.error(f"Error running workflow: {e}")
            raise
    
    def get_best_prompts(self, state: APOSState) -> Dict[str, str]:
        """
        Get the best performing prompts from the optimization history.
        
        Args:
            state: The final state after optimization
            
        Returns:
            Dict containing best system_message and user_message
        """
        best_iteration = max(
            state.history,
            key=lambda x: x.accuracy,
            default=None
        )
        
        if best_iteration:
            return {
                "system_message": best_iteration.metadata["system_message"],
                "user_message": best_iteration.metadata["user_message"]
            }
        
        # If no history, return current prompts
        return {
            "system_message": state.system_message,
            "user_message": state.user_message
        } 