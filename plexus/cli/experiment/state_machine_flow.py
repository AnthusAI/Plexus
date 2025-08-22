#!/usr/bin/env python3
"""
State Machine-Based Conversation Flow Manager

This module provides an intelligent conversation state machine that:
1. Tracks tool usage patterns and progress
2. Uses predicate logic for state transitions 
3. Provides dynamic prompt templates based on current state
4. Enables proper investigation before forcing hypothesis generation
"""

import logging
import json
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class ToolUsageTracker:
    """Tracks usage of different tools throughout the conversation."""
    tool_counts: Dict[str, int] = field(default_factory=dict)
    tool_last_used: Dict[str, datetime] = field(default_factory=dict)
    successful_tools: Set[str] = field(default_factory=set)
    failed_tools: Set[str] = field(default_factory=set)
    
    def record_tool_use(self, tool_name: str, success: bool = True) -> None:
        """Record a tool usage event."""
        self.tool_counts[tool_name] = self.tool_counts.get(tool_name, 0) + 1
        self.tool_last_used[tool_name] = datetime.now()
        
        if success:
            self.successful_tools.add(tool_name)
        else:
            self.failed_tools.add(tool_name)
            
        logger.info(f"ToolTracker: {tool_name} used (count: {self.tool_counts[tool_name]}, success: {success})")
    
    def get_count(self, tool_name: str) -> int:
        """Get the usage count for a specific tool."""
        return self.tool_counts.get(tool_name, 0)
    
    def has_used_successfully(self, tool_name: str) -> bool:
        """Check if a tool has been used successfully at least once."""
        return tool_name in self.successful_tools

@dataclass
class ConversationStateData:
    """Tracks the current state of the conversation."""
    current_state: str = "investigation"
    round_in_state: int = 0
    total_rounds: int = 0
    tool_tracker: ToolUsageTracker = field(default_factory=ToolUsageTracker)
    investigation_summary: str = ""
    patterns_summary: str = ""
    progress_notes: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage in chat session."""
        return {
            'current_state': self.current_state,
            'round_in_state': self.round_in_state,
            'total_rounds': self.total_rounds,
            'tool_counts': self.tool_tracker.tool_counts,
            'successful_tools': list(self.tool_tracker.successful_tools),
            'failed_tools': list(self.tool_tracker.failed_tools),
            'investigation_summary': self.investigation_summary,
            'patterns_summary': self.patterns_summary,
            'progress_notes': self.progress_notes
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConversationStateData':
        """Create from dictionary loaded from chat session."""
        state = cls()
        state.current_state = data.get('current_state', 'investigation')
        state.round_in_state = data.get('round_in_state', 0)
        state.total_rounds = data.get('total_rounds', 0)
        state.investigation_summary = data.get('investigation_summary', '')
        state.patterns_summary = data.get('patterns_summary', '')
        state.progress_notes = data.get('progress_notes', [])
        
        # Rebuild tool tracker
        state.tool_tracker.tool_counts = data.get('tool_counts', {})
        state.tool_tracker.successful_tools = set(data.get('successful_tools', []))
        state.tool_tracker.failed_tools = set(data.get('failed_tools', []))
        
        return state

class StateMachineFlowManager:
    """
    Manages conversation flow using a state machine approach based on tool usage.
    
    States advance based on actual tool usage patterns rather than just message counts,
    ensuring the AI has gathered sufficient information before being pushed to create hypotheses.
    """
    
    def __init__(self, experiment_config: Dict[str, Any], experiment_context: Dict[str, Any] = None):
        """Initialize with experiment configuration and context."""
        self.config = experiment_config.get('conversation_flow', {})
        self.experiment_context = experiment_context or {}
        self.state_data = ConversationStateData()
        
        # Extract configuration sections
        self.states = self.config.get('states', {})
        self.transition_rules = self.config.get('transition_rules', [])
        self.escalation = self.config.get('escalation', {})
        self.guidance = self.config.get('guidance', {})
        
        # Initialize state from config
        initial_state = self.config.get('initial_state', 'investigation')
        self.state_data.current_state = initial_state
        
        logger.info(f"StateMachine: Initialized with state '{initial_state}', {len(self.transition_rules)} transition rules")
    
    def load_state_from_session(self, session_state_data: Optional[Dict[str, Any]]) -> None:
        """Load conversation state from chat session data."""
        if session_state_data:
            self.state_data = ConversationStateData.from_dict(session_state_data)
            logger.info(f"StateMachine: Loaded state '{self.state_data.current_state}' from session")
        else:
            logger.info("StateMachine: No previous state data found, using initial state")
    
    def update_state(self, 
                    tools_used: List[str] = None,
                    tool_results: Dict[str, bool] = None,
                    response_content: str = "",
                    nodes_created: int = 0) -> Optional[Dict[str, Any]]:
        """
        Update conversation state and check for transitions.
        Returns updated state data for storage in chat session.
        """
        
        # Track tool usage
        if tools_used:
            for tool_name in tools_used:
                success = tool_results.get(tool_name, True) if tool_results else True
                self.state_data.tool_tracker.record_tool_use(tool_name, success)
        
        # Update summaries based on response content
        self._update_summaries_from_response(response_content)
        
        # Check for state transitions based on current progress
        old_state = self.state_data.current_state
        self._check_state_transitions()
        
        # If state changed, reset round counter
        if self.state_data.current_state != old_state:
            self.state_data.round_in_state = 0
            logger.info(f"StateMachine: Transitioned from '{old_state}' to '{self.state_data.current_state}'")
        
        # Update round counters
        self.state_data.total_rounds += 1
        self.state_data.round_in_state += 1
        
        logger.info(f"StateMachine: State='{self.state_data.current_state}', Round={self.state_data.round_in_state}, Total={self.state_data.total_rounds}")
        
        return self.state_data.to_dict()
    
    def get_next_guidance(self) -> Optional[str]:
        """Get the next guidance prompt based on current state and progress."""
        current_state_config = self.states.get(self.state_data.current_state, {})
        prompt_template = current_state_config.get('prompt_template', '')
        
        if not prompt_template:
            logger.warning(f"No prompt template found for state '{self.state_data.current_state}'")
            return None
        
        # Generate context variables for template
        context_vars = self._build_template_context()
        
        try:
            # Format the template with context variables
            formatted_prompt = prompt_template.format(**context_vars)
            return formatted_prompt
            
        except KeyError as e:
            logger.error(f"Template formatting error for state '{self.state_data.current_state}': {e}")
            return f"Error: Missing template variable {e}"
    
    def should_continue(self) -> bool:
        """Check if the conversation should continue."""
        max_total = self.escalation.get('max_total_rounds', 15)
        
        # Check completion state
        if self.state_data.current_state == 'complete':
            return False
        
        # Check if we've hit the maximum rounds
        if self.state_data.total_rounds >= max_total:
            logger.warning(f"StateMachine: Reached maximum rounds ({max_total})")
            return False
        
        # Continue if we haven't reached completion
        return True
    
    def _check_state_transitions(self) -> None:
        """Check all transition rules and apply the first matching one."""
        current_state = self.state_data.current_state
        
        for rule in self.transition_rules:
            if rule.get('from_state') == current_state:
                if self._evaluate_transition_conditions(rule.get('conditions', [])):
                    new_state = rule.get('to_state')
                    description = rule.get('description', 'No description')
                    
                    logger.info(f"StateMachine: Transition triggered - {description}")
                    self.state_data.current_state = new_state
                    self.state_data.progress_notes.append(f"Transitioned to {new_state}: {description}")
                    break
    
    def _evaluate_transition_conditions(self, conditions: List[Dict[str, Any]]) -> bool:
        """Evaluate if all transition conditions are met."""
        for condition in conditions:
            condition_type = condition.get('type')
            
            if condition_type == 'tool_usage_count':
                tool = condition.get('tool')
                min_count = condition.get('min_count', 1)
                actual_count = self.state_data.tool_tracker.get_count(tool)
                
                if actual_count < min_count:
                    logger.debug(f"Condition failed: {tool} count {actual_count} < {min_count}")
                    return False
                    
            elif condition_type == 'round_in_state':
                min_rounds = condition.get('min_rounds', 1)
                
                if self.state_data.round_in_state < min_rounds:
                    logger.debug(f"Condition failed: round_in_state {self.state_data.round_in_state} < {min_rounds}")
                    return False
                    
            elif condition_type == 'total_rounds':
                min_total = condition.get('min_total', 1)
                
                if self.state_data.total_rounds < min_total:
                    logger.debug(f"Condition failed: total_rounds {self.state_data.total_rounds} < {min_total}")
                    return False
                    
            else:
                logger.warning(f"Unknown condition type: {condition_type}")
                return False
        
        return True
    
    def _update_summaries_from_response(self, content: str) -> None:
        """Update investigation and pattern summaries based on AI response content."""
        content_lower = content.lower()
        
        # Update investigation summary with key findings
        if self.state_data.current_state == 'investigation':
            key_phrases = []
            if 'false positive' in content_lower:
                key_phrases.append("false positive analysis")
            if 'false negative' in content_lower:
                key_phrases.append("false negative analysis")
            if 'item_id' in content_lower or 'item id' in content_lower:
                key_phrases.append("item detail examination")
            if 'pattern' in content_lower:
                key_phrases.append("pattern identification")
                
            if key_phrases:
                new_notes = f"Round {self.state_data.round_in_state}: {', '.join(key_phrases)}"
                self.state_data.investigation_summary += f"\n- {new_notes}"
        
        # Update patterns summary during analysis phase
        elif self.state_data.current_state == 'pattern_analysis':
            if 'root cause' in content_lower or 'pattern' in content_lower or 'hypothesis' in content_lower:
                summary_excerpt = content[:200] + "..." if len(content) > 200 else content
                self.state_data.patterns_summary += f"\n- Analysis round {self.state_data.round_in_state}: {summary_excerpt}"
    
    def _build_template_context(self) -> Dict[str, str]:
        """Build context variables for prompt template formatting."""
        # Basic experiment context
        context = {
            'scorecard_name': self.experiment_context.get('scorecard_name', 'Unknown'),
            'score_name': self.experiment_context.get('score_name', 'Unknown'),
            'experiment_id': self.experiment_context.get('experiment_id', 'UNKNOWN'),
        }
        
        # Progress summary
        context['progress_summary'] = self._generate_progress_summary()
        
        # Next action guidance
        context['next_action_guidance'] = self._generate_next_action_guidance()
        
        # Investigation summary
        context['investigation_summary'] = self.state_data.investigation_summary or "No investigation summary yet"
        
        # Patterns summary
        context['patterns_summary'] = self.state_data.patterns_summary or "No pattern analysis yet"
        
        return context
    
    def _generate_progress_summary(self) -> str:
        """Generate a summary of current progress."""
        tracker = self.state_data.tool_tracker
        summary_lines = []
        
        # Tool usage summary
        if tracker.tool_counts:
            tool_summary = []
            for tool, count in tracker.tool_counts.items():
                status = "✅" if tool in tracker.successful_tools else "❌"
                tool_summary.append(f"{status} {tool} ({count}x)")
            summary_lines.append("Tools used: " + ", ".join(tool_summary))
        else:
            summary_lines.append("⚠️ No tools used yet")
        
        # Current state info
        summary_lines.append(f"State: {self.state_data.current_state} (round {self.state_data.round_in_state})")
        
        return "\n".join(summary_lines)
    
    def _generate_next_action_guidance(self) -> str:
        """Generate specific guidance for what to do next."""
        tracker = self.state_data.tool_tracker
        current_state = self.state_data.current_state
        
        if current_state == 'investigation':
            # Recommend specific tools that haven't been used yet
            missing_tools = []
            if not tracker.has_used_successfully('plexus_feedback_analysis'):
                missing_tools.append("Get the overall feedback summary first")
            if tracker.get_count('plexus_feedback_find') < 2:
                missing_tools.append("Find specific correction cases (both false positives and false negatives)")
            if tracker.get_count('plexus_item_info') < 3:
                missing_tools.append("Examine individual item details to understand error patterns")
                
            if missing_tools:
                return "Priority actions:\n" + "\n".join(f"- {action}" for action in missing_tools)
            else:
                return "Good progress! Continue investigating or move to pattern analysis."
                
        elif current_state == 'pattern_analysis':
            return "Synthesize your findings into clear patterns and root causes for the misalignment."
            
        elif current_state == 'hypothesis_creation':
            nodes_created = tracker.get_count('create_experiment_node')
            if nodes_created == 0:
                return "Create your first experiment node based on the strongest pattern you identified."
            elif nodes_created == 1:
                return "Create 1-2 more experiment nodes testing different approaches."
            else:
                return "You've created multiple nodes - great work!"
                
        return "Continue with your current analysis."
    
    def get_completion_summary(self) -> str:
        """Get a summary when the conversation is complete."""
        tracker = self.state_data.tool_tracker
        nodes_created = tracker.get_count('create_experiment_node')
        
        if nodes_created >= 2:
            return f"""
🎉 **HYPOTHESIS GENERATION COMPLETE** 🎉

Successfully created {nodes_created} experiment nodes after {self.state_data.total_rounds} rounds of analysis.

Tools used: {', '.join(f"{tool}({count})" for tool, count in tracker.tool_counts.items())}

Investigation summary: {self.state_data.investigation_summary.strip()}

The hypotheses are ready for testing!
"""
        else:
            return f"""
⏰ **CONVERSATION ENDED** ⏰

Reached {self.state_data.total_rounds} rounds. Created {nodes_created} experiment nodes.

Tools used: {', '.join(f"{tool}({count})" for tool, count in tracker.tool_counts.items())}

Consider running the experiment again for more thorough analysis.
"""

