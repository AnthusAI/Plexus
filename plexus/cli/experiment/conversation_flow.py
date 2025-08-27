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
        
        # DEBUG: Log the actual experiment config to see where the 15 is coming from
        logger.info(f"🔧 CONVERSATION_FLOW INIT: Full experiment_config keys = {list(experiment_config.keys())}")
        logger.info(f"🔧 CONVERSATION_FLOW INIT: conversation_flow section = {self.config}")
        logger.info(f"🔧 CONVERSATION_FLOW INIT: escalation section = {self.escalation}")
        if 'max_total_rounds' in self.escalation:
            logger.info(f"🔧 CONVERSATION_FLOW INIT: max_total_rounds found in config = {self.escalation['max_total_rounds']}")
        else:
            logger.info(f"🔧 CONVERSATION_FLOW INIT: max_total_rounds NOT found in config - will use default 500")
        
        # Set up transition triggers with sensible defaults to prevent immediate transitions
        default_triggers = {
            'exploration_to_synthesis': [
                'used_feedback_summary',  # Must use feedback summary tool first
                'min_tool_calls: 8',      # Must make at least 8 tool calls (more thorough analysis)
            ],
            'synthesis_to_hypothesis': [
                'min_insights: 5',        # Must capture at least 5 insights (more comprehensive understanding)
                'identified_patterns',    # Must identify patterns
                'min_tool_calls: 15',     # Must have examined many examples before hypothesis generation
            ]
        }
        self.transition_triggers = {**default_triggers, **self.config.get('transition_triggers', {})}
    
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
                    nodes_created: int = 0) -> Dict[str, Any]:
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
        
        logger.debug(f"ConversationFlow: Stage={self.state.stage.value}, Round={self.state.round_in_stage}, Tools={len(self.state.tools_used)}, Nodes={self.state.nodes_created}")
        
        # Return current state data for orchestration
        return {
            'current_state': self.state.stage.value,
            'round_in_stage': self.state.round_in_stage,
            'total_rounds': self.state.total_rounds,
            'tools_used': list(self.state.tools_used),
            'nodes_created': self.state.nodes_created,
            'analysis_completed': self.state.analysis_completed.copy()
        }
    
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
        
        # Look for key analysis patterns - generalized for any classification system
        if any(term in content_lower for term in ['scoring mistake', 'misclassified', 'incorrectly scored', 'wrong prediction', 'error pattern']):
            self.state.insights_captured.add('scoring_error_analysis')
            
        if any(term in content_lower for term in ['correction', 'edited', 'changed from', 'initial_value', 'final_value']):
            self.state.insights_captured.add('correction_analysis')
            
        if any(term in content_lower for term in ['pattern', 'trend', 'common', 'frequent', 'systematic']):
            self.state.insights_captured.add('pattern_identification')
            
        if any(term in content_lower for term in ['root cause', 'reason', 'because', 'why', 'underlying']):
            self.state.insights_captured.add('root_cause_analysis')
            
        if any(term in content_lower for term in ['suggest', 'recommend', 'improve', 'solution', 'fix', 'change']):
            self.state.insights_captured.add('proposed_solutions')
            
        # Track specific analysis completions for any classification system
        if any(term in content_lower for term in ['examined', 'analyzed', 'reviewed', 'looked at']):
            self.state.insights_captured.add('item_examination')
    
    def _update_analysis_completion(self) -> None:
        """Update which required analyses have been completed."""
        # Feedback summary completed - universal first step
        if 'plexus_feedback_analysis' in self.state.tools_used:
            self.state.analysis_completed['feedback_summary'] = True
            
        # Scoring error analysis - any classification system
        if 'plexus_feedback_find' in self.state.tools_used and 'scoring_error_analysis' in self.state.insights_captured:
            self.state.analysis_completed['scoring_errors'] = True
            
        # Correction pattern analysis - examining how scores were changed
        if 'plexus_feedback_find' in self.state.tools_used and 'correction_analysis' in self.state.insights_captured:
            self.state.analysis_completed['correction_patterns'] = True
            
        # Individual item examination - detailed case analysis
        if ('plexus_item_info' in self.state.tools_used or 'item_examination' in self.state.insights_captured):
            self.state.analysis_completed['item_details'] = True
            
        # Pattern identification across multiple examples
        if 'pattern_identification' in self.state.insights_captured:
            self.state.analysis_completed['pattern_analysis'] = True
    
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
            elif trigger.startswith('examined_scoring_errors'):
                if not self.state.analysis_completed.get('scoring_errors', False):
                    return False
            elif trigger.startswith('examined_corrections'):
                if not self.state.analysis_completed.get('correction_patterns', False):
                    return False
            elif trigger.startswith('min_tool_calls'):
                min_calls = int(trigger.split(':')[1].strip()) if ':' in trigger else 2
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
        
        # Determine what's missing and provide targeted guidance - generalized for any classification system
        missing_analyses = []
        if not self.state.analysis_completed.get('feedback_summary', False):
            missing_analyses.append("feedback summary overview")
        if not self.state.analysis_completed.get('scoring_errors', False):
            missing_analyses.append("scoring error examination")
        if not self.state.analysis_completed.get('correction_patterns', False):
            missing_analyses.append("correction pattern analysis")
        if not self.state.analysis_completed.get('item_details', False):
            missing_analyses.append("detailed item examination")
        if not self.state.analysis_completed.get('pattern_analysis', False):
            missing_analyses.append("cross-case pattern identification")
            
        context_reminder = self._get_context_reminder()
        
        if missing_analyses:
            if escalation_level == 'normal':
                return f"""
📊 **CONTINUE INVESTIGATION** 📊

Great progress! Next, focus on: {', '.join(missing_analyses[:2])}
{context_reminder}

**CRITICAL: Examine AT LEAST 5-6 examples** of each type of scoring mistake you find. Do NOT create hypotheses until you have thoroughly analyzed multiple examples from each confusion matrix segment (No→Yes, Yes→No, etc.). One example per category is insufficient.

{prompts[min(self.state.round_in_stage - 1, len(prompts) - 1)] if prompts else 'Continue your analysis using the available feedback tools.'}
"""
            elif escalation_level == 'gentle':
                return f"""
🔍 **IMPORTANT ANALYSIS NEEDED** 🔍

You still need to examine: {', '.join(missing_analyses)}

{prompts[min(self.state.round_in_stage - 1, len(prompts) - 1)] if prompts else 'Please use the feedback analysis tools to complete your investigation.'}

**MANDATORY**: You must examine AT LEAST 5-6 examples from each confusion matrix segment before proceeding. Do not rush to create experiment nodes with insufficient data.

This analysis is essential for generating effective hypotheses.
"""
            else:  # firm
                return f"""
⚠️  **CRITICAL ANALYSIS GAPS** ⚠️

Missing required analyses: {', '.join(missing_analyses)}

You must complete these investigations before proceeding to hypothesis generation. Use the tools available to gather this essential data.

**Note**: If limited examples are available for some mistake types, focus on the patterns you can identify and move forward.
"""
        else:
            # All exploration complete, encourage transition
            return """
✅ **EXPLORATION COMPLETE** ✅

Excellent investigation! You've gathered comprehensive feedback data. 

Now it's time to synthesize your findings and identify the key patterns causing scoring misalignment.
"""
    
    def _get_synthesis_guidance(self, escalation_level: str) -> str:
        """Get synthesis stage guidance."""
        stage_config = self.conversation_stages.get('synthesis', {})
        prompts = stage_config.get('guidance_prompts', [])
        
        # Summarize what analysis was completed - generalized for any classification system
        completed_analysis = []
        if self.state.analysis_completed.get('feedback_summary', False):
            completed_analysis.append("✅ Reviewed feedback summary and confusion matrix")
        if self.state.analysis_completed.get('scoring_errors', False):
            completed_analysis.append("✅ Examined scoring mistake patterns and error cases")
        if self.state.analysis_completed.get('correction_patterns', False):
            completed_analysis.append("✅ Analyzed correction patterns and human feedback")
        if self.state.analysis_completed.get('item_details', False):
            completed_analysis.append("✅ Reviewed specific problematic item details")
        
        tools_used_summary = f"Tools used: {', '.join(sorted(self.state.tools_used))}" if self.state.tools_used else "No tools used yet"
        
        context_reminder = self._get_context_reminder()
        
        # Get experiment context for required parameters
        experiment_id = self.experiment_context.get('experiment_id', 'EXPERIMENT_ID')
        scorecard_name = self.experiment_context.get('scorecard_name', 'Unknown')
        score_name = self.experiment_context.get('score_name', 'Unknown')
        
        if escalation_level == 'normal':
            # For the first few rounds in synthesis, provide minimal guidance to let AI work naturally
            if self.state.round_in_stage <= 3:
                return "Continue your analysis."  # Minimal guidance - let AI continue naturally  
            else:
                return f"""
💡 **CONTINUE YOUR ANALYSIS** 💡

{prompts[min(self.state.round_in_stage - 1, len(prompts) - 1)] if prompts else 'Keep analyzing and synthesizing your findings.'}
{context_reminder}

**Your exploration progress:**
{chr(10).join(completed_analysis) if completed_analysis else "⚠️ No analysis completed yet"}

{tools_used_summary}

**Continue deeper analysis:** What patterns are you seeing in the feedback data? What root causes are emerging?

**For rich hypothesis development, explore:**
- Specific quantified patterns (e.g., "67% of false positives occur when...")
- Concrete examples from the data you examined
- Root cause theories with supporting evidence  
- Multiple potential solution approaches with trade-offs
- Expected impact on scoring metrics

Take all the time you need to thoroughly understand the issues before considering solutions. The more detailed your analysis, the richer your eventual hypotheses will be.
"""
        elif escalation_level == 'gentle':
            return f"""
🔍 **CONTINUE SYNTHESIS** 🔍

{prompts[min(self.state.round_in_stage - 1, len(prompts) - 1)] if prompts else 'Continue analyzing patterns and developing your understanding.'}
{context_reminder}

**Deepen your analysis with quantified insights:**
- Are there common themes across the errors you examined? (What percentage?)
- What specific configuration changes would target these error patterns? (Be precise)
- How would you prioritize different potential improvements? (What's the expected impact?)
- Can you identify specific examples that illustrate key problem patterns?
- What success metrics would validate your proposed solutions?

**Next:** Once you have clear insights about root causes and potential solutions, you'll move to creating concrete hypotheses.

**For comprehensive hypotheses, document:**
- Specific error rates and patterns you discovered
- Concrete examples that illustrate the problems
- Multiple solution approaches with expected trade-offs

What are the most important quantified patterns you've identified so far?
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
        """Get detailed hypothesis generation stage guidance focused on comprehensive descriptions."""
        stage_config = self.conversation_stages.get('hypothesis_generation', {})
        prompts = stage_config.get('guidance_prompts', [])
        
        context_reminder = self._get_context_reminder()
        
        # Get experiment context for required parameters
        experiment_id = self.experiment_context.get('experiment_id', 'EXPERIMENT_ID')
        scorecard_name = self.experiment_context.get('scorecard_name', 'Unknown')
        score_name = self.experiment_context.get('score_name', 'Unknown')
        
        if escalation_level == 'normal':
            return f"""
🧠 **COMPREHENSIVE HYPOTHESIS DEVELOPMENT** 🧠

Now it's time to create detailed, well-reasoned hypotheses based on your thorough analysis.
{context_reminder}

**FOCUS ON RICH, DETAILED HYPOTHESES:**

Your hypothesis_description should include:
• **BACKGROUND**: What specific problems did you identify in the feedback data?
• **ROOT CAUSE**: What underlying issues are causing the scoring mistakes?
• **SOLUTION APPROACH**: What high-level strategy will address these issues?
• **EXPECTED IMPACT**: How will this change improve scoring accuracy?
• **IMPLEMENTATION DETAILS**: What specific configuration changes are needed?

**EXAMPLE of a comprehensive hypothesis format:**

create_experiment_node(
    experiment_id="{experiment_id}",
    hypothesis_description="BACKGROUND: Analysis revealed that 67% of false positives occur with medical terminology not in training data. ROOT CAUSE: Classification rules too broad, lack medical domain context. SOLUTION: Add medical terminology whitelist and stricter prescriber verification. EXPECTED IMPACT: Reduce false positive rate from 12% to 8% while maintaining 94% true positive detection. IMPLEMENTATION: Enhanced validation rules with medical context awareness.",
    yaml_configuration="name: medical_context\\nprompt: Enhanced classification with medical domain knowledge\\nvalidation_rules: strict_medical_terms",
    node_name="Medical Context Enhancement for Reduced False Positives"
)

**Take your time to craft detailed, thoughtful hypotheses that explain the reasoning behind each approach.**

What specific patterns did you identify that will inform your first hypothesis?
"""
        elif escalation_level == 'gentle':
            return f"""
📝 **DETAILED HYPOTHESIS CREATION** 📝

{prompts[min(self.state.round_in_stage - 1, len(prompts) - 1)] if prompts else 'Please create detailed experiment nodes based on your analysis.'}
{context_reminder}

**REMEMBER: Focus on comprehensive hypothesis descriptions, not just tool mechanics.**

Each hypothesis should tell a complete story:

1. **What problem did you find?** (specific examples from your analysis)
2. **Why is this problem occurring?** (root cause analysis)
3. **How will your solution address it?** (logical connection)
4. **What changes are needed?** (specific configuration details)

create_experiment_node(
    experiment_id="{experiment_id}",
    hypothesis_description="BACKGROUND: [What problems were found] ROOT CAUSE: [Why problems occur] SOLUTION: [High-level approach] IMPACT: [Expected improvements] IMPLEMENTATION: [Key configuration changes]",
    yaml_configuration="name: your_config_name\\nprompt: your enhanced prompt\\nrules: specific_validation_changes",
    node_name="Descriptive Name for This Hypothesis"
)

**Your hypothesis descriptions should be 3-4 paragraphs, not single sentences.**

Create 2-3 different hypotheses that test different aspects of the problems you identified.
"""
        else:  # firm
            return f"""
⚡ **URGENT: CREATE COMPREHENSIVE HYPOTHESES** ⚡

You must create detailed experiment nodes now, but focus on QUALITY over speed.
{context_reminder}

**CRITICAL: Your hypotheses must include detailed background context, not just brief summaries.**

**Required comprehensive format:**
create_experiment_node(
    experiment_id="{experiment_id}",
    hypothesis_description="PROBLEM IDENTIFIED: [What specific issues found in feedback data with examples] ROOT CAUSE ANALYSIS: [Why problems occurring, what patterns emerged] PROPOSED SOLUTION: [High-level approach to address root causes] EXPECTED OUTCOMES: [How scoring accuracy will improve, metric changes] CONFIGURATION STRATEGY: [Specific changes needed for implementation]",
    yaml_configuration="name: hypothesis_config\\nprompt: enhanced_classification_logic\\nvalidation: improved_rules",
    node_name="Clear Descriptive Name for This Hypothesis"
)

**NO TERSE SUMMARIES** - Each hypothesis description should be 200-400 words explaining:
- The specific problems you identified
- Why these problems are occurring  
- How your solution addresses the root causes
- What configuration changes will implement your approach

Create detailed, comprehensive hypotheses that future developers can understand and implement.
"""
    
    def should_continue(self) -> bool:
        """Check if the conversation should continue."""
        max_total = self.escalation.get('max_total_rounds', 500)  # High default to respect template settings
        
        # DEBUG: Log the actual escalation config to see where 15 is coming from
        logger.info(f"🔧 CONVERSATION_FLOW DEBUG: escalation config = {self.escalation}")
        logger.info(f"🔧 CONVERSATION_FLOW DEBUG: max_total_rounds from config = {self.escalation.get('max_total_rounds', 'NOT_SET')}")
        logger.info(f"🔧 CONVERSATION_FLOW DEBUG: max_total resolved to = {max_total}")
        
        # ENHANCED: Much more patient termination logic that prioritizes feedback over termination
        if (self.state.stage == ConversationStage.HYPOTHESIS_GENERATION and 
            self.state.nodes_created == 0):
            
            # Check if AI is actively trying to create nodes (even with parameter errors)
            attempting_node_creation = any(tool_name == 'create_experiment_node' for tool_name in self.state.tools_used)
            
            # CRITICAL IMPROVEMENT: Be much more patient when AI is learning from errors
            # The goal is to provide feedback and education, not quick termination
            if attempting_node_creation:
                # Give AI up to 12 rounds to learn from parameter errors and succeed
                # This accounts for multiple feedback iterations needed for complex tool parameters
                patience_limit = 12
                logger.info(f"HYPOTHESIS STAGE: AI is attempting node creation - extended patient mode (up to {patience_limit} rounds)")
            else:
                # Even if AI isn't trying, give them more time to understand what's needed
                patience_limit = 6
                logger.info(f"HYPOTHESIS STAGE: AI not attempting node creation - encouraging patience (up to {patience_limit} rounds)")
            
            if self.state.round_in_stage >= patience_limit:
                logger.warning(f"PATIENCE EXHAUSTED: AI has {'attempted but failed to succeed' if attempting_node_creation else 'failed to attempt'} node creation after {self.state.round_in_stage} rounds")
                # BEFORE terminating, log what went wrong to help with future improvements
                if attempting_node_creation:
                    logger.info("TERMINATION ANALYSIS: AI was actively trying to create nodes but couldn't get parameters right despite feedback")
                else:
                    logger.info("TERMINATION ANALYSIS: AI never attempted to use create_experiment_node tool - may still be in data gathering phase")
                # Don't force termination - let the main procedure definition handle stopping
                # return False  # Force termination, which will trigger emergency node creation
            else:
                remaining_rounds = patience_limit - self.state.round_in_stage
                logger.info(f"HYPOTHESIS STAGE: Continuing with patience - {remaining_rounds} more rounds available (currently round {self.state.round_in_stage}/{patience_limit})")
        
        # GENERAL CONTINUATION LOGIC: Stop when we reach our target
        result = (self.state.total_rounds < max_total and 
                  self.state.stage != ConversationStage.COMPLETE and
                  self.state.nodes_created < 2)  # Stop at 2 nodes as per completion logic
        
        # Enhanced logging for better debugging of conversation termination
        logger.info(f"🔍 FLOW_MANAGER.should_continue: stage={self.state.stage.value}, round_in_stage={self.state.round_in_stage}/{self._get_stage_patience_limit()}, total_rounds={self.state.total_rounds}/{max_total}, nodes_created={self.state.nodes_created}/2, attempting_node_creation={'create_experiment_node' in self.state.tools_used}, result={result}")
        
        if not result:
            if self.state.total_rounds >= max_total:
                logger.warning(f"🛑 CONVERSATION FLOW STOPPING: Hit maximum total rounds ({self.state.total_rounds}/{max_total})")
                logger.warning(f"🛑 STOP REASON: ConversationFlow max_total_rounds limit reached - escalation config had max_total_rounds={self.escalation.get('max_total_rounds', 'NOT_SET')}")
            elif self.state.stage == ConversationStage.COMPLETE:
                logger.info(f"🏁 CONVERSATION FLOW STOPPING: Stage is COMPLETE")
                logger.info(f"🏁 STOP REASON: ConversationFlow reached COMPLETE stage")
            elif self.state.nodes_created >= 2:
                logger.info(f"🏁 CONVERSATION FLOW STOPPING: Target nodes created ({self.state.nodes_created}/2)")
                logger.info(f"🏁 STOP REASON: ConversationFlow reached target node count")
            else:
                logger.error(f"🚨 CONVERSATION FLOW STOPPING: Unknown reason! total_rounds={self.state.total_rounds}, stage={self.state.stage.value}, nodes_created={self.state.nodes_created}")
                logger.error(f"🚨 STOP REASON: ConversationFlow stopped for unknown reason - escalation config had max_total_rounds={self.escalation.get('max_total_rounds', 'NOT_SET')}")
        
        return result
    
    def _get_stage_patience_limit(self) -> int:
        """Get the patience limit for the current stage."""
        if self.state.stage == ConversationStage.HYPOTHESIS_GENERATION:
            attempting_node_creation = any(tool_name == 'create_experiment_node' for tool_name in self.state.tools_used)
            return 12 if attempting_node_creation else 6
        return 10  # Default for other stages
    
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
