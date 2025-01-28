"""
Mismatch analyzer node for analyzing individual mismatches.
"""
import logging
import os
import json
from typing import Dict, Any, Callable, List
from dataclasses import asdict

from plexus.apos.nodes.base import APOSNode
from plexus.apos.graph_state import APOSState
from plexus.apos.analyzer import MismatchAnalyzer
from plexus.apos.models import MismatchAnalysis

logger = logging.getLogger('plexus.apos.nodes.mismatch')


class MismatchAnalyzerNode(APOSNode):
    """Node for analyzing individual mismatches."""
    
    def _setup_node(self) -> None:
        """Set up the mismatch analyzer components."""
        self.analyzer = MismatchAnalyzer(config=self.config)
        logger.info("Initialized mismatch analyzer node")
    
    async def _analyze_mismatches(
        self,
        mismatches: List[MismatchAnalysis],
        system_message: str,
        user_message: str
    ) -> List[MismatchAnalysis]:
        """
        Analyze a list of mismatches.
        
        Args:
            mismatches: List of mismatches to analyze
            system_message: Current system message
            user_message: Current user message
            
        Returns:
            List of analyzed mismatches
        """
        analyzed_mismatches = []
        for mismatch in mismatches:
            logger.info(f"Analyzing mismatch for question: {mismatch.question_name}")
            analysis = await self.analyzer.analyze_mismatch(
                mismatch,
                system_message=system_message,
                user_message=user_message
            )
            analyzed_mismatches.append(analysis)
            logger.debug(f"Analysis complete: {analysis.detailed_analysis}")
        
        return analyzed_mismatches
    
    def get_node_handler(self) -> Callable[[APOSState], Dict[str, Any]]:
        """Get the handler function for this node."""
        
        async def analyze_mismatches(state: APOSState) -> Dict[str, Any]:
            """Analyze mismatches from evaluation."""
            try:
                if not state.mismatches:
                    logger.warning("No mismatches available for analysis")
                    return state.dict()
                
                logger.info(f"Analyzing {len(state.mismatches)} mismatches individually")
                
                # Get iteration directory from state metadata
                self.iteration_dir = state.metadata.get("iteration_dir")
                if not self.iteration_dir:
                    logger.warning("No iteration directory found in state metadata")
                
                # Convert raw mismatches to MismatchAnalysis objects
                mismatch_analyses = []
                for mismatch in state.mismatches:
                    # Handle both dict and MismatchAnalysis objects
                    if isinstance(mismatch, dict):
                        # Convert form_id to transcript_id and other field mappings
                        analysis = MismatchAnalysis(
                            transcript_id=mismatch.get('form_id'),
                            question_name=mismatch.get('question'),
                            transcript_text=mismatch.get('transcript', ''),
                            model_answer=mismatch.get('predicted', ''),
                            ground_truth=mismatch.get('ground_truth', ''),
                            original_explanation=mismatch.get('explanation', '')
                        )
                    else:
                        # If it's already a MismatchAnalysis, use it as is
                        analysis = mismatch
                    mismatch_analyses.append(analysis)
                
                # Analyze mismatches
                analyzed_mismatches = await self.analyzer.analyze_mismatches(mismatch_analyses)
                
                # Save analyses - convert back to dict format expected by evaluation
                if self.iteration_dir:
                    output_path = os.path.join(self.iteration_dir, "mismatches.json")
                    mismatch_dicts = []
                    for m in analyzed_mismatches:
                        mismatch_dict = {
                            'form_id': m.transcript_id,
                            'question': m.question_name,
                            'predicted': m.model_answer,
                            'ground_truth': m.ground_truth,
                            'original_explanation': m.original_explanation,
                            'detailed_analysis': m.detailed_analysis,
                            'error_category': m.error_category,
                            'root_cause': m.root_cause
                        }
                        mismatch_dicts.append(mismatch_dict)
                    
                    with open(output_path, 'w') as f:
                        json.dump(mismatch_dicts, f, indent=4)
                    logger.info(f"Saved {len(analyzed_mismatches)} mismatch analyses to {output_path}")
                
                # Update state with analyzed mismatches
                state.analyzed_mismatches = analyzed_mismatches
                
                return state.dict()
                
            except Exception as e:
                logger.error(f"Error analyzing mismatches: {e}")
                return self.handle_error(e, state)
                
        return analyze_mismatches 