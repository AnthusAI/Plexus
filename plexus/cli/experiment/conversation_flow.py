#!/usr/bin/env python3
"""
Conversation Flow Manager for Experiment Hypothesis Generation

This module provides intelligent conversation guidance that:
1. Tracks what analysis has been completed
2. Identifies what's missing from the investigation  
3. Provides targeted prompts to guide the AI through proper methodology
4. Gradually escalates pressure based on progress, not just message count
"""

import logging
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class ConversationStage(Enum):
    """Stages of the hypothesis generation conversation."""
    EXPLORATION = "exploration"
    SYNTHESIS = "synthesis" 
    HYPOTHESIS_GENERATION = "hypothesis_generation"
    COMPLETE = "complete"

@dataclass
class ConversationState:
    """Tracks the current state of the conversation."""
    stage: ConversationStage = ConversationStage.EXPLORATION
    round_in_stage: int = 0
    total_rounds: int = 0
    tools_used: Set[str] = None
    insights_captured: Set[str] = None
    nodes_created: int = 0
    analysis_completed: Dict[str, bool] = None
    
    def __post_init__(self):
        if self.tools_used is None:
            self.tools_used = set()
        if self.insights_captured is None:
            self.insights_captured = set()
        if self.analysis_completed is None:
            self.analysis_completed = {}

class ConversationFlowManager:
    """
    Manages the conversation flow for experiment hypothesis generation.
    
    Provides intelligent guidance based on:
    - What analysis has been completed
    - What tools have been used
    - What insights have been captured
    - Current stage and progress
    """
    
    def __init__(self, experiment_config: Dict[str, Any], experiment_context: Dict[str, Any] = None):
        """Initialize with experiment configuration and context."""
        self.config = experiment_config.get('conversation_flow', {})
        self.experiment_context = experiment_context or {}
        self.state = ConversationState()
        self.conversation_stages = self.config.get('conversation_stages', {})
        self.escalation = self.config.get('escalation', {})
        self.transition_triggers = self.config.get('transition_triggers', {})
    
    def _get_context_reminder(self) -> str:
        """Get a context reminder with scorecard and score names."""
        scorecard_name = self.experiment_context.get('scorecard_name', 'Unknown')
        score_name = self.experiment_context.get('score_name', 'Unknown')
        
        return f"""
**🎯 CONTEXT REMINDER:**
- scorecard_name: "{scorecard_name}"
- score_name: "{score_name}"

**Use these exact values in all tool calls.**"""
        
    def update_state(self, 
                    tools_used: List[str] = None,
                    response_content: str = "",
                    nodes_created: int = 0) -> None:
        """Update conversation state based on recent activity."""
        
        # Track tools used
        if tools_used:
            self.state.tools_used.update(tools_used)
            
        # Track node creation
        self.state.nodes_created = nodes_created
        
        # Analyze response content for insights
        self._analyze_response_for_insights(response_content)
        
        # Update analysis completion status
        self._update_analysis_completion()
        

        
        logger.info(f"ConversationFlow: Stage={self.state.stage.value}, Round={self.state.round_in_stage}, Tools={len(self.state.tools_used)}, Nodes={self.state.nodes_created}")
    
    def get_next_guidance(self) -> Optional[str]:
        """Get the next guidance prompt based on current state."""
        # Check if we've completed the hypothesis generation
        if self.state.nodes_created >= 2:
            self.state.stage = ConversationStage.COMPLETE
            return None
        
        # Increment counters BEFORE stage transition check to ensure transitions use correct counts
        self.state.total_rounds += 1
        self.state.round_in_stage += 1
        
        # Now check for stage transitions with updated counters
        self._check_stage_transition()
            
        # Check for escalation needs
        escalation_level = self._get_escalation_level()
        
        # Get stage-specific guidance
        if self.state.stage == ConversationStage.EXPLORATION:
            return self._get_exploration_guidance(escalation_level)
        elif self.state.stage == ConversationStage.SYNTHESIS:
            return self._get_synthesis_guidance(escalation_level)
        elif self.state.stage == ConversationStage.HYPOTHESIS_GENERATION:
            return self._get_hypothesis_guidance(escalation_level)
        
        return None
    
    def _analyze_response_for_insights(self, content: str) -> None:
        """Analyze response content to identify captured insights."""
        content_lower = content.lower()
        
        # Look for key analysis patterns
        if any(term in content_lower for term in ['false positive', 'precision', 'specificity']):
            self.state.insights_captured.add('false_positive_analysis')
            
        if any(term in content_lower for term in ['false negative', 'recall', 'sensitivity']):
            self.state.insights_captured.add('false_negative_analysis')
            
        if any(term in content_lower for term in ['pattern', 'trend', 'common']):
            self.state.insights_captured.add('pattern_identification')
            
        if any(term in content_lower for term in ['root cause', 'reason', 'because']):
            self.state.insights_captured.add('root_cause_analysis')
            
        if any(term in content_lower for term in ['suggest', 'recommend', 'improve', 'solution']):
            self.state.insights_captured.add('proposed_solutions')
    
    def _update_analysis_completion(self) -> None:
        """Update which required analyses have been completed."""
        # Feedback summary completed
        if 'plexus_feedback_summary' in self.state.tools_used:
            self.state.analysis_completed['feedback_summary'] = True
            
        # False positive analysis 
        if 'plexus_feedback_find' in self.state.tools_used and 'false_positive_analysis' in self.state.insights_captured:
            self.state.analysis_completed['false_positives'] = True
            
        # False negative analysis
        if 'plexus_feedback_find' in self.state.tools_used and 'false_negative_analysis' in self.state.insights_captured:
            self.state.analysis_completed['false_negatives'] = True
            
        # Item details examined
        if 'plexus_item_info' in self.state.tools_used:
            self.state.analysis_completed['item_details'] = True
    
    def _check_stage_transition(self) -> None:
        """Check if we should transition to the next stage."""
        current_stage = self.state.stage
        
        if current_stage == ConversationStage.EXPLORATION:
            # Check transition to synthesis
            triggers = self.transition_triggers.get('exploration_to_synthesis', [])
            if self._check_triggers(triggers):
                self.state.stage = ConversationStage.SYNTHESIS
                self.state.round_in_stage = 0
                logger.info("ConversationFlow: Transitioning from EXPLORATION to SYNTHESIS")
                
        elif current_stage == ConversationStage.SYNTHESIS:
            # Allow MUCH more synthesis time: at least 10+ rounds before forcing hypothesis generation
            triggers = self.transition_triggers.get('synthesis_to_hypothesis', [])
            # Only transition if triggers are met AND we've had SUBSTANTIAL time to synthesize
            if self._check_triggers(triggers) and self.state.round_in_stage >= 10:
                self.state.stage = ConversationStage.HYPOTHESIS_GENERATION  
                self.state.round_in_stage = 0
                logger.info("ConversationFlow: Transitioning from SYNTHESIS to HYPOTHESIS_GENERATION after thorough analysis")
    
    def _check_triggers(self, triggers: List[str]) -> bool:
        """Check if transition triggers are met."""
        for trigger in triggers:
            if trigger.startswith('used_feedback_summary'):
                if not self.state.analysis_completed.get('feedback_summary', False):
                    return False
            elif trigger.startswith('examined_false_positives'):
                if not self.state.analysis_completed.get('false_positives', False):
                    return False
            elif trigger.startswith('examined_false_negatives'):
                if not self.state.analysis_completed.get('false_negatives', False):
                    return False
            elif trigger.startswith('min_tool_calls'):
                min_calls = int(trigger.split(':')[1].strip()) if ':' in trigger else 3
                # Only count successful analysis completions, not just tool attempts
                completed_analyses = sum(1 for completed in self.state.analysis_completed.values() if completed)
                if completed_analyses < min_calls:
                    return False
            elif trigger.startswith('identified_patterns'):
                if 'pattern_identification' not in self.state.insights_captured:
                    return False
            elif trigger.startswith('proposed_solutions'):
                if 'proposed_solutions' not in self.state.insights_captured:
                    return False
            elif trigger.startswith('min_insights'):
                min_insights = int(trigger.split(':')[1].strip()) if ':' in trigger else 2
                if len(self.state.insights_captured) < min_insights:
                    return False
        return True
    
    def _get_escalation_level(self) -> str:
        """Determine the escalation level based on progress."""
        max_rounds = self.conversation_stages.get(self.state.stage.value, {}).get('max_rounds', 5)
        gentle_nudge = self.escalation.get('gentle_nudge_after', 2)  # Give more time: escalate after 2 rounds
        firm_pressure = self.escalation.get('firm_pressure_after', 4)  # Give more time: firm after 4 rounds
        
        # Special case: In synthesis stage, focus on analysis not node creation pressure
        if self.state.stage == ConversationStage.SYNTHESIS:
            # Don't pressure for nodes during synthesis - let AI analyze and synthesize properly
            if self.state.round_in_stage <= 8:
                return 'normal'  # Normal synthesis guidance - lots of time
            elif self.state.round_in_stage <= 10:
                return 'gentle'  # Gentle encouragement to continue
            else:
                return 'firm'   # Only after 10+ rounds, suggest wrapping up
                
        # In hypothesis generation stage, be more direct about node creation
        elif self.state.stage == ConversationStage.HYPOTHESIS_GENERATION:
            if self.state.nodes_created == 0:
                if self.state.round_in_stage <= 1:
                    return 'normal'  # Give time to plan hypotheses
                elif self.state.round_in_stage <= 2:
                    return 'gentle'  # Start encouraging node creation
                else:
                    return 'firm'   # Demand nodes after 3 rounds
        
        # Standard escalation for other stages
        if self.state.round_in_stage <= gentle_nudge:
            return 'normal'
        elif self.state.round_in_stage <= firm_pressure:
            return 'gentle'
        else:
            return 'firm'
    
    def _get_exploration_guidance(self, escalation_level: str) -> str:
        """Get exploration stage guidance."""
        stage_config = self.conversation_stages.get('exploration', {})
        prompts = stage_config.get('guidance_prompts', [])
        
        # Determine what's missing and provide targeted guidance
        missing_analyses = []
        if not self.state.analysis_completed.get('feedback_summary', False):
            missing_analyses.append("feedback summary overview")
        if not self.state.analysis_completed.get('false_positives', False):
            missing_analyses.append("false positive analysis")
        if not self.state.analysis_completed.get('false_negatives', False):
            missing_analyses.append("false negative analysis")
        if not self.state.analysis_completed.get('item_details', False):
            missing_analyses.append("detailed item examination")
            
        context_reminder = self._get_context_reminder()
        
        if missing_analyses:
            if escalation_level == 'normal':
                return f"""
📊 **CONTINUE INVESTIGATION** 📊

Great progress! Next, focus on: {', '.join(missing_analyses[:2])}
{context_reminder}

{prompts[min(self.state.round_in_stage - 1, len(prompts) - 1)] if prompts else 'Continue your analysis using the available feedback tools.'}
"""
            elif escalation_level == 'gentle':
                return f"""
🔍 **IMPORTANT ANALYSIS NEEDED** 🔍

You still need to examine: {', '.join(missing_analyses)}

{prompts[min(self.state.round_in_stage - 1, len(prompts) - 1)] if prompts else 'Please use the feedback analysis tools to complete your investigation.'}

This analysis is essential for generating effective hypotheses.
"""
            else:  # firm
                return f"""
⚠️  **CRITICAL ANALYSIS GAPS** ⚠️

Missing required analyses: {', '.join(missing_analyses)}

You must complete these investigations before proceeding to hypothesis generation. Use the tools available to gather this essential data.
"""
        else:
            # All exploration complete, encourage transition
            return """
✅ **EXPLORATION COMPLETE** ✅

Excellent investigation! You've gathered comprehensive feedback data. 

Now it's time to synthesize your findings and identify the key patterns causing misalignment.
"""
    
    def _get_synthesis_guidance(self, escalation_level: str) -> str:
        """Get synthesis stage guidance."""
        stage_config = self.conversation_stages.get('synthesis', {})
        prompts = stage_config.get('guidance_prompts', [])
        
        # Summarize what analysis was completed
        completed_analysis = []
        if self.state.analysis_completed.get('feedback_summary', False):
            completed_analysis.append("✅ Reviewed feedback summary and confusion matrix")
        if self.state.analysis_completed.get('false_positives', False):
            completed_analysis.append("✅ Examined false positive cases (Yes→No corrections)")
        if self.state.analysis_completed.get('false_negatives', False):
            completed_analysis.append("✅ Examined false negative cases (No→Yes corrections)")
        if self.state.analysis_completed.get('item_details', False):
            completed_analysis.append("✅ Reviewed specific problematic item details")
        
        tools_used_summary = f"Tools used: {', '.join(sorted(self.state.tools_used))}" if self.state.tools_used else "No tools used yet"
        
        context_reminder = self._get_context_reminder()
        
        # Get experiment context for required parameters
        experiment_id = self.experiment_context.get('experiment_id', 'EXPERIMENT_ID')
        scorecard_name = self.experiment_context.get('scorecard_name', 'Unknown')
        score_name = self.experiment_context.get('score_name', 'Unknown')
        
        if escalation_level == 'normal':
            # For the first many rounds in synthesis, just say "Okay?" to let AI continue naturally
            if self.state.round_in_stage <= 6:
                return "Okay?"
            else:
                return f"""
💡 **CONTINUE YOUR ANALYSIS** 💡

{prompts[min(self.state.round_in_stage - 1, len(prompts) - 1)] if prompts else 'Keep analyzing and synthesizing your findings.'}
{context_reminder}

**Your exploration progress:**
{chr(10).join(completed_analysis) if completed_analysis else "⚠️ No analysis completed yet"}

{tools_used_summary}

**Continue deeper analysis:** What patterns are you seeing in the feedback data? What root causes are emerging?

Take all the time you need to thoroughly understand the issues before considering solutions.
"""
        elif escalation_level == 'gentle':
            return f"""
🔍 **CONTINUE SYNTHESIS** 🔍

{prompts[min(self.state.round_in_stage - 1, len(prompts) - 1)] if prompts else 'Continue analyzing patterns and developing your understanding.'}
{context_reminder}

**Deepen your analysis:**
- Are there common themes across the errors you examined?
- What specific configuration changes would target these error patterns?
- How would you prioritize different potential improvements?

**Next:** Once you have clear insights about root causes and potential solutions, you'll move to creating concrete hypotheses.

What are the most important patterns you've identified so far?
"""
        else:  # firm
            return f"""
🎯 **READY FOR HYPOTHESIS GENERATION** 🎯

You have completed thorough analysis and synthesis. It's time to move to the hypothesis generation stage.
{context_reminder}

**Summary of your analysis:** Based on the patterns you've identified, you're ready to design specific configuration changes.

**Next stage:** You'll transition to hypothesis generation where you can create experiment nodes to test your theories.

**Wrap up:** Summarize your key findings and the main approaches you want to test, then we'll move to creating concrete hypotheses.
"""
    
    def _get_hypothesis_guidance(self, escalation_level: str) -> str:
        """Get hypothesis generation stage guidance."""
        stage_config = self.conversation_stages.get('hypothesis_generation', {})
        prompts = stage_config.get('guidance_prompts', [])
        
        context_reminder = self._get_context_reminder()
        
        # Get experiment context for required parameters
        experiment_id = self.experiment_context.get('experiment_id', 'EXPERIMENT_ID')
        scorecard_name = self.experiment_context.get('scorecard_name', 'Unknown')
        score_name = self.experiment_context.get('score_name', 'Unknown')
        
        if escalation_level == 'normal':
            return f"""
🚀 **MANDATORY HYPOTHESIS CREATION** 🚀

Analysis is complete. You MUST now create experiment nodes.
{context_reminder}

{prompts[min(self.state.round_in_stage - 1, len(prompts) - 1)] if prompts else 'Create experiment nodes to test your hypotheses.'}

**REQUIRED ACTION**: Use the `create_experiment_node` tool with these exact parameters:

**Example call:**
create_experiment_node(
    experiment_id="{experiment_id}",
    hypothesis_description="GOAL: Reduce false positives for {score_name} | METHOD: Add stricter verification requirements",
    yaml_configuration="[your complete YAML with specific changes]",
    node_name="Stricter Verification Requirements"
)

This is not optional - you must create nodes to proceed.
"""
        elif escalation_level == 'gentle':
            return f"""
⏰ **NODE CREATION REQUIRED** ⏰

{prompts[min(self.state.round_in_stage - 1, len(prompts) - 1)] if prompts else 'Please create experiment nodes based on your analysis.'}
{context_reminder}

The analysis phase is over. You must now create testable hypotheses using create_experiment_node.

**Required call format:**
create_experiment_node(
    experiment_id="{experiment_id}",
    hypothesis_description="GOAL: [specific improvement] | METHOD: [exact changes]",
    yaml_configuration="[complete YAML configuration with your changes]",
    node_name="[descriptive name for this hypothesis]"
)

Create 2-3 different hypotheses based on the feedback patterns you found.
"""
        else:  # firm
            return f"""
🚨 **FINAL WARNING: CREATE NODES NOW** 🚨

You MUST use the `create_experiment_node` tool immediately to create 2-3 hypothesis variations.
{context_reminder}

**THIS IS YOUR LAST CHANCE** - Failure to create nodes will terminate the conversation.

**MANDATORY PARAMETERS:**
- experiment_id: "{experiment_id}"
- scorecard_name: "{scorecard_name}" 
- score_name: "{score_name}"

**Example calls you MUST make:**
create_experiment_node(
    experiment_id="{experiment_id}",
    hypothesis_description="GOAL: Reduce false positives | METHOD: Stricter verification requirements",
    yaml_configuration="[complete YAML with stricter rules]",
    node_name="Conservative: Stricter Verification"
)

create_experiment_node(
    experiment_id="{experiment_id}",
    hypothesis_description="GOAL: Improve accuracy | METHOD: Enhanced pattern matching",
    yaml_configuration="[complete YAML with enhanced patterns]",
    node_name="Aggressive: Enhanced Patterns"
)

Create diverse approaches: incremental, creative, and revolutionary hypotheses.
**NO MORE ANALYSIS - CREATE NODES NOW!**
"""
    
    def should_continue(self) -> bool:
        """Check if the conversation should continue."""
        max_total = self.escalation.get('max_total_rounds', 25)  # Increased for longer analysis time
        
        # Allow proper time for hypothesis generation before forcing termination
        if (self.state.stage == ConversationStage.HYPOTHESIS_GENERATION and 
            self.state.nodes_created == 0):
            # Allow 4 rounds in hypothesis generation, then force termination for emergency
            if self.state.round_in_stage >= 4:
                logger.warning(f"FORCING NODE CREATION: AI has failed to create nodes in hypothesis stage after {self.state.round_in_stage} rounds")
                return False  # Force termination, which will trigger emergency node creation
            else:
                logger.info(f"HYPOTHESIS STAGE: Giving AI {4 - self.state.round_in_stage} more chances to create nodes (currently round {self.state.round_in_stage})")
        
        result = (self.state.total_rounds < max_total and 
                  self.state.stage != ConversationStage.COMPLETE and
                  self.state.nodes_created < 2)
        
        logger.info(f"should_continue: stage={self.state.stage.value}, round_in_stage={self.state.round_in_stage}, total_rounds={self.state.total_rounds}, nodes={self.state.nodes_created}, result={result}")
        return result
    
    def get_completion_summary(self) -> str:
        """Get a summary when the conversation is complete."""
        if self.state.nodes_created >= 2:
            return f"""
🎉 **HYPOTHESIS GENERATION COMPLETE** 🎉

Successfully created {self.state.nodes_created} experiment nodes after {self.state.total_rounds} rounds of analysis.

Tools used: {', '.join(sorted(self.state.tools_used))}
Insights captured: {', '.join(sorted(self.state.insights_captured))}

The hypotheses are ready for testing!
"""
        else:
            return f"""
⏰ **CONVERSATION TIMEOUT** ⏰

Reached {self.state.total_rounds} rounds without generating sufficient hypotheses.

Analysis completed: {list(self.state.analysis_completed.keys())}
Tools used: {', '.join(sorted(self.state.tools_used))}

Consider running the experiment again with a more focused approach.
"""
