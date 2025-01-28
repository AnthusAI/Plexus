"""
Node implementations for APOS LangGraph workflow.
"""
from typing import Any, Dict, Optional, Callable, List
from abc import ABC, abstractmethod
import logging

from langchain.graphs import StateGraph
from langchain_core.runnables import RunnableConfig
from langchain_core.pydantic_v1 import BaseModel
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field

from plexus.apos.graph_state import APOSState
from plexus.apos.config import APOSConfig
from plexus.apos.models import (
    OptimizationStatus,
    SynthesisResult,
    PromptChange,
    PatternAnalysisOutput,
    PromptImprovement,
    IterationResult,
    MismatchAnalysis
)
from plexus.apos.evaluation import APOSEvaluation
from plexus.apos.analyzer import MismatchAnalyzer
from plexus.Registries import scorecard_registry
from plexus.Scorecard import Scorecard

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
        graph.add_node(node_name, handler, config)


class PatternAnalyzerNode(APOSNode):
    """Node for analyzing patterns in mismatches."""
    
    def _setup_node(self) -> None:
        """Set up the pattern analyzer components."""
        model_config = self.config.pattern_analyzer_model
        
        # Initialize LLM
        self.llm = ChatOpenAI(
            model=model_config.model_type,
            temperature=model_config.temperature,
            max_tokens=model_config.max_tokens,
            top_p=model_config.top_p,
            max_retries=model_config.max_retries
        ).with_structured_output(PatternAnalysisOutput)
        
        # Set up prompt templates
        self.system_template = SystemMessagePromptTemplate.from_template(
            model_config.prompts['system_template']
        )
        self.human_template = HumanMessagePromptTemplate.from_template(
            model_config.prompts['human_template']
        )
        self.chat_prompt = ChatPromptTemplate.from_messages([
            self.system_template,
            self.human_template
        ])
    
    def get_node_handler(self) -> Callable[[APOSState], Dict[str, Any]]:
        """Get the pattern analysis handler."""
        def analyze_patterns(state: APOSState) -> Dict[str, Any]:
            try:
                # Format mismatches for analysis
                mismatch_summaries = "\n".join(
                    f"""
                    Question: {m.question_name}
                    System Message: {state.system_message}
                    User Message: {state.user_message}
                    Model's Answer: {m.model_answer}
                    Correct Answer: {m.ground_truth}
                    Analysis: {m.detailed_analysis}
                    ---"""
                    for m in state.mismatches
                )
                
                # Prepare context with all available state
                context = {
                    **state.dict(),
                    "mismatch_summaries": mismatch_summaries
                }
                
                # Get analysis from LLM
                messages = self.chat_prompt.format_messages(**context)
                result = self.llm.invoke(messages)
                
                # Update state with results
                return {
                    **state.dict(),
                    "pattern_analysis": SynthesisResult(
                        common_issues=result.common_issues,
                        summary=result.summary
                    ),
                    "retry_count": 0  # Reset retry count on success
                }
                
            except Exception as e:
                return self.handle_error(e, state)
                
        return analyze_patterns


class OptimizerNode(APOSNode):
    """Node for generating optimized prompts."""
    
    def _setup_node(self) -> None:
        """Set up the optimizer components."""
        model_config = self.config.optimizer_model
        
        # Initialize LLM
        self.llm = ChatOpenAI(
            model=model_config.model_type,
            temperature=model_config.temperature,
            max_tokens=model_config.max_tokens,
            top_p=model_config.top_p,
            max_retries=model_config.max_retries
        ).with_structured_output(PromptImprovement)
        
        # Set up prompt templates
        self.system_template = SystemMessagePromptTemplate.from_template(
            model_config.prompts['system_template']
        )
        self.human_template = HumanMessagePromptTemplate.from_template(
            model_config.prompts['human_template']
        )
        self.chat_prompt = ChatPromptTemplate.from_messages([
            self.system_template,
            self.human_template
        ])
        
        logger.info(f"Initialized optimizer node using {model_config.model_type}")
    
    def get_current_prompts(self, score_name: str) -> Dict[str, str]:
        """Get the current prompts for a given score from scorecard."""
        try:
            # Load scorecard
            logger.info(f"Loading scorecards for {score_name}")
            Scorecard.load_and_register_scorecards('scorecards/')
            
            # Get score configuration from the scorecard
            for scorecard_class in scorecard_registry._classes_by_key.values():
                scorecard_key = scorecard_class.properties.get('key') or scorecard_class.name
                logger.info(f"Checking scorecard: {scorecard_key}")
                
                scorecard = scorecard_class(scorecard=scorecard_key)
                score_config = next((score for score in scorecard.scores 
                                if score['name'] == score_name), None)
                
                if score_config:
                    logger.info(f"Found score config for {score_name}")
                    
                    # Look for Classifier node in graph
                    if 'graph' in score_config:
                        for node in score_config['graph']:
                            if node.get('class') == 'Classifier':
                                logger.info(f"Found Classifier node: {node}")
                                prompts = {
                                    'system_message': node.get('system_message', ''),
                                    'user_message': node.get('user_message', '')
                                }
                                if prompts['system_message'] and prompts['user_message']:
                                    logger.info("Found prompts in Classifier node")
                                    return prompts
                    
                    # Try top-level prompts
                    prompts = {
                        'system_message': score_config.get('system_message', ''),
                        'user_message': score_config.get('user_message', '')
                    }
                    
                    if prompts['system_message'] and prompts['user_message']:
                        logger.info("Using top-level prompts")
                        return prompts
                    else:
                        logger.error("No valid prompts found in score config")
                        raise ValueError(f"No prompts found for score: {score_name}")
            
            raise ValueError(f"No configuration found for score: {score_name}")
            
        except Exception as e:
            logger.error(f"Error getting current prompts for {score_name}: {e}")
            raise
    
    def get_node_handler(self) -> Callable[[APOSState], Dict[str, Any]]:
        """Get the optimizer handler."""
        def optimize_prompts(state: APOSState) -> Dict[str, Any]:
            try:
                if not state.pattern_analysis:
                    raise ValueError("No pattern analysis available for optimization")
                
                # Log pattern analysis results
                logger.info("\n=== Pattern Analysis Results ===")
                logger.info("Common Issues:")
                for issue in state.pattern_analysis.common_issues:
                    logger.info(f"- {issue}")
                logger.info("\nSummary:")
                logger.info(state.pattern_analysis.summary)
                logger.info("===============================\n")
                
                # Get current prompts with fallback
                current_prompts = {
                    'system_message': state.system_message,
                    'user_message': state.user_message
                }
                if not any(current_prompts.values()):
                    logger.warning(f"No current prompts in state for {state.score_name}, falling back to scorecard")
                    current_prompts = self.get_current_prompts(state.score_name)
                
                # Prepare context with all available state
                context = {
                    **state.dict(),
                    "current_system_message": current_prompts['system_message'],
                    "current_user_message": current_prompts['user_message'],
                    "common_issues": "\n".join(f"- {issue}" for issue in state.pattern_analysis.common_issues),
                    "summary": state.pattern_analysis.summary
                }
                
                # Get improvements from LLM
                messages = self.chat_prompt.format_messages(**context)
                result = self.llm.invoke(messages)
                
                # Validate {{text}} variable placement
                if '{{text}}' in result.system_message:
                    logger.error("system_message should not contain {{text}} variable")
                    raise ValueError("system_message should not contain {{text}} variable")
                if '{{text}}' not in result.user_message:
                    logger.error("user_message must contain {{text}} variable")
                    raise ValueError("user_message must contain {{text}} variable")
                
                # Create prompt changes
                changes = {}
                metadata = {
                    "score_name": state.score_name,
                    "analysis_summary": state.pattern_analysis.summary,
                    "iteration": state.current_iteration
                }
                
                # Only create changes if prompts are different
                if result.system_message.strip() != current_prompts['system_message'].strip():
                    changes["system_message"] = PromptChange(
                        component="system_message",
                        old_text=current_prompts['system_message'],
                        new_text=result.system_message,
                        rationale=result.rationale,
                        metadata=metadata.copy()
                    )
                    logger.info("Generated new system message")
                    logger.info(f"DEBUG: Created system message change: {changes['system_message']}")
                
                if result.user_message.strip() != current_prompts['user_message'].strip():
                    changes["user_message"] = PromptChange(
                        component="user_message",
                        old_text=current_prompts['user_message'],
                        new_text=result.user_message,
                        rationale=result.rationale,
                        metadata=metadata.copy()
                    )
                    logger.info("Generated new user message")
                    logger.info(f"DEBUG: Created user message change: {changes['user_message']}")
                
                if not changes:
                    logger.warning("No meaningful changes to prompts were needed")
                else:
                    logger.info(f"DEBUG: Final changes to return: {changes}")
                
                # Update state with results
                return {
                    **state.dict(),
                    "system_message": result.system_message,
                    "user_message": result.user_message,
                    "optimization_result": changes.get("system_message") or changes.get("user_message"),
                    "retry_count": 0  # Reset retry count on success
                }
                
            except Exception as e:
                logger.error(f"Error generating prompt improvements: {e}")
                return self.handle_error(e, state)
                
        return optimize_prompts


class EvaluationNode(APOSNode):
    """Node for evaluating prompts and collecting mismatches."""
    
    def _setup_node(self) -> None:
        """Set up evaluation components."""
        self.evaluation_cache = {}  # Cache evaluation results
    
    def _create_evaluation(
        self,
        state: APOSState,
        **kwargs
    ) -> APOSEvaluation:
        """Create a new evaluation instance with current state."""
        # Create evaluation with current prompts and config
        evaluation = APOSEvaluation(
            config=self.config,
            scorecard_name=state.scorecard_name,
            score_name=state.score_name,
            **kwargs
        )
        
        # Set the current prompts
        evaluation.set_prompts({
            state.score_name: {
                'system_message': state.system_message,
                'user_message': state.user_message
            }
        })
        
        return evaluation
    
    async def _run_evaluation(
        self,
        state: APOSState
    ) -> Dict[str, Any]:
        """Run evaluation and return state updates."""
        try:
            # Create cache key from current prompts
            cache_key = f"{state.system_message}::{state.user_message}"
            
            # Check cache first
            if cache_key in self.evaluation_cache:
                cached_result = self.evaluation_cache[cache_key]
                return {
                    **state.dict(),
                    "current_accuracy": cached_result.accuracy,
                    "mismatches": cached_result.mismatches,
                    "retry_count": 0
                }
            
            # Create and run evaluation
            evaluation = self._create_evaluation(state)
            result = await evaluation.run()
            
            # Cache the result
            self.evaluation_cache[cache_key] = result
            
            # Create iteration result
            iteration_result = IterationResult(
                iteration=state.current_iteration,
                accuracy=result.accuracy,
                mismatches=result.mismatches,
                prompt_changes=[state.optimization_result] if state.optimization_result else [],
                metrics=evaluation._get_metrics(),
                metadata={
                    "score_name": state.score_name,
                    "system_message": state.system_message,
                    "user_message": state.user_message
                }
            )
            
            # Update state
            state_updates = {
                **state.dict(),
                "current_accuracy": result.accuracy,
                "mismatches": result.mismatches,
                "retry_count": 0
            }
            
            # Update best accuracy if needed
            if result.accuracy > state.best_accuracy:
                state_updates["best_accuracy"] = result.accuracy
            
            # Add iteration result to history
            state_updates["history"] = [*state.history, iteration_result]
            
            # Increment iteration counter
            state_updates["current_iteration"] = state.current_iteration + 1
            
            # Check completion conditions
            if (
                result.accuracy >= state.target_accuracy or
                state.current_iteration >= state.max_iterations
            ):
                state_updates["status"] = OptimizationStatus.COMPLETED
            
            return state_updates
            
        except Exception as e:
            return self.handle_error(e, state)
    
    def get_node_handler(self) -> Callable[[APOSState], Dict[str, Any]]:
        """Get the evaluation handler."""
        async def evaluate_prompts(state: APOSState) -> Dict[str, Any]:
            return await self._run_evaluation(state)
                
        return evaluate_prompts 


class MismatchAnalyzerNode(APOSNode):
    """Node for analyzing individual mismatches."""
    
    def _setup_node(self) -> None:
        """Set up the mismatch analyzer components."""
        self.analyzer = MismatchAnalyzer(config=self.config)
    
    def get_node_handler(self) -> Callable[[APOSState], Dict[str, Any]]:
        """Get the mismatch analysis handler."""
        async def analyze_mismatches(state: APOSState) -> Dict[str, Any]:
            try:
                if not state.mismatches:
                    raise ValueError("No mismatches available for analysis")
                
                # Analyze each mismatch
                analyzed_mismatches = []
                for mismatch in state.mismatches:
                    analysis = await self.analyzer.analyze_mismatch(
                        mismatch,
                        system_message=state.system_message,
                        user_message=state.user_message
                    )
                    analyzed_mismatches.append(analysis)
                
                # Update state with analyzed mismatches
                return {
                    **state.dict(),
                    "mismatches": analyzed_mismatches,
                    "retry_count": 0
                }
                
            except Exception as e:
                return self.handle_error(e, state)
                
        return analyze_mismatches 