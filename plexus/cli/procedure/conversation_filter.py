"""
Token-aware conversation filtering for procedure AI execution.

This module provides specialized conversation filtering that considers both
message content and token limits for optimal model context management.
"""

import logging
from typing import List, Optional, Dict, Any
from abc import ABC, abstractmethod

try:
    import tiktoken
except ImportError:
    tiktoken = None

logger = logging.getLogger(__name__)


class ConversationFilter(ABC):
    """Abstract base class for conversation filtering strategies."""
    
    @abstractmethod
    def filter_conversation(self, conversation_history: List, max_tokens: Optional[int] = None) -> List:
        """Filter conversation history according to specific strategy."""
        pass


class ConversationFilterBase:
    """
    Base class for conversation filtering with token measurement capabilities.
    
    This class provides token counting and measurement functionality without
    performing any actual filtering. Other filters can inherit from this class
    to get token measurement capabilities and then implement their own filtering logic.
    """
    
    def __init__(self, model: str = "gpt-4o"):
        """
        Initialize the base conversation filter.
        
        Args:
            model: Model name for token encoding (default: "gpt-4o")
        """
        self.model = model
        self._setup_tokenizer()
    
    def _setup_tokenizer(self):
        """Setup the tokenizer for the specified model."""
        self.encoding = None
        if tiktoken:
            try:
                self.encoding = tiktoken.encoding_for_model(self.model)
            except KeyError:
                logger.warning(f"Model '{self.model}' not recognized by tiktoken, using cl100k_base encoding")
                self.encoding = tiktoken.get_encoding("cl100k_base")
        else:
            logger.warning("TikToken not available - token counting will be approximate")
    
    def _count_message_tokens(self, message) -> int:
        """
        Count tokens in a single message.
        
        Args:
            message: Message object with content attribute
            
        Returns:
            Token count for the message
        """
        if not self.encoding or not hasattr(message, 'content') or not message.content:
            return 0
        
        try:
            content_tokens = len(self.encoding.encode(message.content))
            # Add overhead tokens for message structure (role, etc.)
            return content_tokens + 4  # OpenAI message formatting overhead
        except Exception as e:
            logger.warning(f"Error counting tokens for message: {e}")
            return len(message.content) // 4  # Rough approximation: 4 chars per token
    
    def _count_conversation_tokens(self, conversation_history: List) -> int:
        """
        Count total tokens in conversation history.
        
        Args:
            conversation_history: List of conversation messages
            
        Returns:
            Total token count
        """
        total_tokens = sum(self._count_message_tokens(msg) for msg in conversation_history)
        return total_tokens + 2  # Conversation overhead
    
    def _get_message_type_name(self, message) -> str:
        """Get human-readable message type name."""
        if hasattr(message, '__class__'):
            return message.__class__.__name__.replace("Message", "")
        return "Unknown"
    
    def analyze_conversation_tokens(self, conversation_history: List, max_tokens: Optional[int] = None) -> Dict[str, Any]:
        """
        Analyze token usage in conversation history without modifying it.
        
        This method provides pure measurement and analysis functionality.
        It reports on token usage, message breakdown, and whether limits are exceeded,
        but does not perform any filtering or modification of the conversation.
        
        Args:
            conversation_history: List of conversation messages
            max_tokens: Optional maximum token limit for analysis
            
        Returns:
            Dictionary with token analysis results
        """
        logger.info("📊 TOKEN ANALYSIS (Measurement Only)")
        logger.info(f"   Conversation: {len(conversation_history)} messages")
        
        # Count total tokens
        total_tokens = self._count_conversation_tokens(conversation_history)
        
        # Per-message token breakdown
        message_breakdown = []
        for i, message in enumerate(conversation_history):
            message_tokens = self._count_message_tokens(message)
            message_type = self._get_message_type_name(message)
            content_length = len(message.content) if hasattr(message, 'content') and message.content else 0
            
            message_info = {
                "index": i,
                "type": message_type,
                "tokens": message_tokens,
                "content_length": content_length
            }
            message_breakdown.append(message_info)
            
            logger.info(f"   [{i}] {message_type}: {message_tokens} tokens ({content_length} chars)")
        
        # Token limit analysis
        analysis_result = {
            "total_messages": len(conversation_history),
            "total_tokens": total_tokens,
            "message_breakdown": message_breakdown,
            "model": self.model
        }
        
        if max_tokens:
            within_limit = total_tokens <= max_tokens
            tokens_remaining = max_tokens - total_tokens if within_limit else 0
            tokens_over = total_tokens - max_tokens if not within_limit else 0
            
            analysis_result.update({
                "max_tokens": max_tokens,
                "within_limit": within_limit,
                "tokens_remaining": tokens_remaining,
                "tokens_over": tokens_over
            })
            
            logger.info(f"   📊 Total: {total_tokens} tokens, Limit: {max_tokens} tokens")
            if within_limit:
                logger.info(f"   ✅ Within limit ({tokens_remaining} tokens remaining)")
            else:
                logger.info(f"   ⚠️  Exceeds limit by {tokens_over} tokens")
        else:
            logger.info(f"   📊 Total: {total_tokens} tokens (no limit specified)")
        
        logger.info("📊 TOKEN ANALYSIS COMPLETE")
        return analysis_result


class TokenAwareConversationFilter(ConversationFilterBase, ConversationFilter):
    """
    Token-aware conversation filter that combines character-based and token-based filtering.
    
    This filter implements intelligent conversation management by:
    1. Identifying tool result messages (ToolMessage or SystemMessage with tool patterns)
    2. Counting tokens per message for precise context management (inherited from base)
    3. Applying filtering rules based on both content size and token limits
    4. Preserving recent tool results while truncating older ones
    """
    
    def __init__(self, model: str = "gpt-4o"):
        """
        Initialize the token-aware filter.
        
        Args:
            model: Model name for token encoding (default: "gpt-4o")
        """
        super().__init__(model)
    
    def _is_tool_result_message(self, message) -> bool:
        """
        Determine if a message is a tool result.
        
        Args:
            message: Message to check
            
        Returns:
            True if message is a tool result
        """
        try:
            # Import message types dynamically to handle different langchain versions
            from langchain_core.messages import ToolMessage, SystemMessage
        except ImportError:
            try:
                from langchain.schema.messages import ToolMessage, SystemMessage
            except ImportError:
                from langchain.schema import ToolMessage, SystemMessage
        
        # Check for ToolMessage type
        if hasattr(message, '__class__') and message.__class__.__name__ == 'ToolMessage':
            return True
        
        # Check for SystemMessage with tool result pattern
        if (hasattr(message, '__class__') and message.__class__.__name__ == 'SystemMessage' and
            hasattr(message, 'content') and message.content and
            ("Tool " in message.content and " result:" in message.content)):
            return True
        
        return False
    
    def _create_truncated_message(self, original_message, truncated_content: str):
        """
        Create a truncated version of a message, preserving as much metadata as possible.
        
        Args:
            original_message: Original message to truncate
            truncated_content: New truncated content
            
        Returns:
            New message with truncated content and preserved metadata
        """
        try:
            # Import message types dynamically to handle different langchain versions
            from langchain_core.messages import ToolMessage, SystemMessage
        except ImportError:
            try:
                from langchain.schema.messages import ToolMessage, SystemMessage
            except ImportError:
                from langchain.schema import ToolMessage, SystemMessage
        
        # Handle different message types with their specific constructors
        if hasattr(original_message, '__class__'):
            message_class = original_message.__class__
            
            try:
                # For ToolMessage, preserve tool_call_id if it exists
                if message_class.__name__ == 'ToolMessage':
                    if hasattr(original_message, 'tool_call_id'):
                        return message_class(content=truncated_content, tool_call_id=original_message.tool_call_id)
                    else:
                        return message_class(content=truncated_content)
                
                # For SystemMessage and other basic message types
                else:
                    return message_class(content=truncated_content)
                    
            except Exception as e:
                logger.warning(f"Failed to create truncated message of type {message_class.__name__}: {e}")
                # Fallback to SystemMessage if we can't create the original type
                return SystemMessage(content=truncated_content)
        
        # Ultimate fallback
        return SystemMessage(content=truncated_content)
    
    def filter_conversation(self, conversation_history: List, max_tokens: Optional[int] = None) -> List:
        """
        Filter conversation history with token awareness.
        
        Behavior Driven Design:
        GIVEN a conversation history with tool result messages
        WHEN the conversation exceeds token limits
        THEN filter by keeping recent tool results full and truncating older ones
        AND provide detailed per-message token reporting
        
        Args:
            conversation_history: Complete conversation history
            max_tokens: Optional maximum token limit
            
        Returns:
            Filtered conversation history
        """
        logger.info("🔍 TOKEN-AWARE CONVERSATION FILTERING")
        logger.info(f"   Original history: {len(conversation_history)} messages")
        
        # Phase 1: Analyze original conversation
        original_tokens = self._count_conversation_tokens(conversation_history) if max_tokens else 0
        if max_tokens:
            logger.info(f"   📊 Original: {original_tokens} tokens, Limit: {max_tokens} tokens")
            if original_tokens > max_tokens:
                logger.info(f"   ⚠️  Exceeds limit by {original_tokens - max_tokens} tokens")
            else:
                logger.info(f"   ✅ Within limit ({max_tokens - original_tokens} tokens remaining)")
        
        # Phase 2: Identify tool result messages
        tool_result_indices = []
        for i, message in enumerate(conversation_history):
            if self._is_tool_result_message(message):
                tool_result_indices.append(i)
        
        logger.info(f"   🔧 Found {len(tool_result_indices)} tool result messages at indices: {tool_result_indices}")
        
        # Phase 3: Apply filtering rules with per-message logging
        filtered_history = []
        for i, message in enumerate(conversation_history):
            message_tokens = self._count_message_tokens(message) if max_tokens else 0
            message_type = self._get_message_type_name(message)
            content_length = len(message.content) if hasattr(message, 'content') and message.content else 0
            
            if i in tool_result_indices:
                # This is a tool result message
                tool_index = tool_result_indices.index(i)
                # Keep most recent 2 tool results (or all if <= 2 total)
                is_recent = tool_index >= max(0, len(tool_result_indices) - 2)
                
                if is_recent:
                    # Keep recent tool results in full
                    filtered_history.append(message)
                    token_info = f", {message_tokens} tokens" if max_tokens else ""
                    logger.info(f"   ✅ Keeping recent tool result #{tool_index + 1} in full ({content_length} chars{token_info})")
                else:
                    # Apply truncation to older tool results
                    if content_length > 500:
                        # Truncate large tool results
                        truncated_content = message.content[:500]
                        truncation_notice = f"\n\n[TOOL RESULT TRUNCATED at 500 chars - original was {content_length} chars, {message_tokens} tokens. Summarize key learnings since you won't see these details again.]"
                        
                        # Create new message with same type but truncated content
                        truncated_message = self._create_truncated_message(message, truncated_content + truncation_notice)
                        
                        filtered_history.append(truncated_message)
                        new_tokens = self._count_message_tokens(truncated_message) if max_tokens else 0
                        token_info = f", {message_tokens}→{new_tokens} tokens" if max_tokens else ""
                        logger.info(f"   ✂️  Truncated older tool result #{tool_index + 1} ({content_length}→{len(truncated_content + truncation_notice)} chars{token_info})")
                    else:
                        # Small tool result - keep as-is
                        filtered_history.append(message)
                        token_info = f", {message_tokens} tokens" if max_tokens else ""
                        logger.info(f"   ➡️  Keeping small tool result #{tool_index + 1} as-is ({content_length} chars{token_info})")
            else:
                # Non-tool message - keep as-is
                filtered_history.append(message)
                token_info = f", {message_tokens} tokens" if max_tokens else ""
                logger.info(f"   ➡️  Keeping {message_type} as-is ({content_length} chars{token_info})")
        
        # Phase 4: Final analysis
        filtered_tokens = self._count_conversation_tokens(filtered_history) if max_tokens else 0
        logger.info(f"   Filtered history: {len(filtered_history)} messages")
        
        if max_tokens:
            token_reduction = original_tokens - filtered_tokens
            logger.info(f"   📊 Filtered: {filtered_tokens} tokens (reduced by {token_reduction})")
            if filtered_tokens > max_tokens:
                logger.info(f"   ⚠️  Still exceeds limit by {filtered_tokens - max_tokens} tokens")
            else:
                logger.info(f"   ✅ Now within limit ({max_tokens - filtered_tokens} tokens remaining)")
        
        logger.info("🔍 TOKEN-AWARE FILTERING COMPLETE")
        return filtered_history


class WorkerAgentConversationFilter(TokenAwareConversationFilter):
    """
    Specialized conversation filter for worker agents that performs specific filtering:
    
    1. Filters tool result messages (keeps most recent 2, truncates older ones)
    2. Filters empty AI messages that contain only tool calls (no text content)
    
    This filter is designed for coding assistant workers that make tool calls
    but may produce empty reasoning messages that just contain tool calls.
    """
    
    def _is_empty_tool_call_message(self, message) -> bool:
        """
        Determine if a message is an AI message with only tool calls and no content.
        
        Args:
            message: Message to check
            
        Returns:
            True if message is an AI message with tool calls but no meaningful content
        """
        try:
            # Import message types dynamically to handle different langchain versions
            from langchain_core.messages import AIMessage
        except ImportError:
            try:
                from langchain.schema.messages import AIMessage
            except ImportError:
                from langchain.schema import AIMessage
        
        # Check if it's an AI message
        if not (hasattr(message, '__class__') and message.__class__.__name__ == 'AIMessage'):
            return False
        
        # Check if it has tool calls
        has_tool_calls = hasattr(message, 'tool_calls') and message.tool_calls
        
        # Check if content is empty or whitespace only
        content = getattr(message, 'content', '') or ''
        has_empty_content = not content.strip()
        
        return has_tool_calls and has_empty_content
    
    def _find_tool_result_for_ai_message(self, conversation_history: List, ai_message_index: int):
        """
        Find the tool result message that corresponds to an AI message with tool calls.
        
        Args:
            conversation_history: Complete conversation history
            ai_message_index: Index of the AI message with tool calls
            
        Returns:
            Index of the corresponding tool result message, or None if not found
        """
        # Look for the next tool result message after the AI message
        for i in range(ai_message_index + 1, len(conversation_history)):
            message = conversation_history[i]
            if self._is_tool_result_message(message):
                return i
        return None

    def filter_conversation(self, conversation_history: List, max_tokens: Optional[int] = None) -> List:
        """
        Filter conversation history for worker agents with enhanced filtering.
        
        This method applies both tool result filtering and empty AI message filtering
        while maintaining OpenAI API requirements and preserving the current conversation state:
        1. Applies the standard tool result filtering (most recent 2 kept, others truncated)
        2. Removes OLD AI messages that contain only tool calls with no text content
        3. CRITICAL: Preserves the MOST RECENT AI message (current tool call) to avoid infinite loops
        4. Also removes corresponding tool results to maintain API compliance
        
        Args:
            conversation_history: Complete conversation history
            max_tokens: Optional maximum token limit
            
        Returns:
            Filtered conversation history with both tool result and empty AI message filtering
        """
        logger.info("🔍 WORKER AGENT CONVERSATION FILTERING")
        logger.info(f"   Original history: {len(conversation_history)} messages")
        
        # Phase 1: Identify OLD empty AI messages (not the most recent one)
        messages_to_skip = set()
        empty_ai_indices = []
        
        # First, find all empty AI messages
        for i, message in enumerate(conversation_history):
            if self._is_empty_tool_call_message(message):
                empty_ai_indices.append(i)
        
        # Only filter empty AI messages that are NOT the most recent one
        # The most recent empty AI message represents the current tool call we're responding to
        if empty_ai_indices:
            most_recent_empty_ai_index = max(empty_ai_indices)
            for i in empty_ai_indices:
                if i != most_recent_empty_ai_index:
                    # This is an OLD empty AI message - filter it
                    messages_to_skip.add(i)
                    
                    # Find and mark its corresponding tool result for removal too
                    tool_result_index = self._find_tool_result_for_ai_message(conversation_history, i)
                    if tool_result_index is not None:
                        messages_to_skip.add(tool_result_index)
                        logger.info(f"   🔗 Will filter OLD AI message #{i} and its tool result #{tool_result_index}")
                    else:
                        logger.info(f"   ⚠️  Old AI message #{i} has tool calls but no following tool result found")
                else:
                    logger.info(f"   ✅ Preserving most recent AI message #{i} (current tool call)")
        
        # Phase 2: Apply standard token-aware filtering for remaining tool results
        if messages_to_skip:
            # Create a temporary history without the messages we're going to skip
            temp_history = [msg for i, msg in enumerate(conversation_history) if i not in messages_to_skip]
            logger.info(f"   Pre-filtering: removed {len(messages_to_skip)} old AI+tool pairs")
        else:
            temp_history = conversation_history
            logger.info("   No old empty AI messages to filter")
        
        tool_filtered_history = super().filter_conversation(temp_history, max_tokens)
        
        # Phase 3: Report final filtering results
        logger.info("   🤖 Empty AI message filtering complete")
        
        empty_ai_pairs_filtered = len([i for i in messages_to_skip if self._is_empty_tool_call_message(conversation_history[i])])
        logger.info(f"   Filtered {empty_ai_pairs_filtered} old empty AI messages and their tool results")
        logger.info(f"   Final history: {len(tool_filtered_history)} messages")
        logger.info("🔍 WORKER AGENT FILTERING COMPLETE")
        
        return tool_filtered_history


class ManagerAgentConversationFilter(ConversationFilterBase, ConversationFilter):
    """
    Specialized conversation filter for manager/orchestration agents that provides high-level oversight.
    
    The manager agent needs a strategic overview of the conversation rather than detailed technical execution.
    This filter creates a filtered message list optimized for orchestration decisions, with proper
    system message setup for manager-style responses.
    
    This filter is designed for SOP (Standard Operating Procedure) agents and other manager-level
    agents that need to understand conversation flow and guide the overall process.
    """

    def __init__(self, model: str = "gpt-4o"):
        """
        Initialize the manager agent filter.
        
        Args:
            model: Model name for token encoding (default: "gpt-4o")
        """
        super().__init__(model)
    
    def _create_message_summary(self, message, index: int) -> str:
        """
        Create a summary of a message for manager agent consumption.
        
        Args:
            message: Message to summarize
            index: Index of message in conversation
            
        Returns:
            Summarized message content
        """
        if not hasattr(message, 'content') or not message.content:
            return f"[{index}] {self._get_message_type_name(message)}: <empty>"
        
        # Different summary lengths based on message type
        message_type = self._get_message_type_name(message)
        
        if message_type == "System":
            # System messages - very brief summary focused on setup
            content_preview = message.content[:80] + "..." if len(message.content) > 80 else message.content
            return f"[{index}] System: {content_preview}"
        
        elif message_type == "Human":
            # Human messages - preserve key requests and instructions
            content_preview = message.content[:150] + "..." if len(message.content) > 150 else message.content
            return f"[{index}] User: {content_preview}"
        
        elif message_type == "AI":
            # AI messages - focus on key insights and decisions, detect tool calls
            has_tool_calls = hasattr(message, 'tool_calls') and message.tool_calls
            if has_tool_calls:
                # For AI messages with tool calls, show reasoning + tool names
                tool_names = [tc.get('name', 'unknown') if isinstance(tc, dict) else str(tc) for tc in message.tool_calls]
                content_preview = message.content[:100] + "..." if len(message.content) > 100 else message.content
                return f"[{index}] Assistant: {content_preview} [Tools: {', '.join(tool_names)}]"
            else:
                # Regular AI messages - show key insights
                content_preview = message.content[:200] + "..." if len(message.content) > 200 else message.content
                return f"[{index}] Assistant: {content_preview}"
        
        elif message_type == "Tool":
            # Tool messages - very brief summary of results
            if self._is_tool_result_message(message):
                # Extract tool result type and brief summary
                lines = message.content.split('\n')[:3]  # First 3 lines only
                brief_result = ' '.join(lines)[:100] + "..." if len(' '.join(lines)) > 100 else ' '.join(lines)
                return f"[{index}] Tool Result: {brief_result}"
            else:
                content_preview = message.content[:80] + "..." if len(message.content) > 80 else message.content
                return f"[{index}] Tool: {content_preview}"
        
        else:
            # Unknown message types
            content_preview = message.content[:100] + "..." if len(message.content) > 100 else message.content
            return f"[{index}] {message_type}: {content_preview}"
    
    def _is_tool_result_message(self, message) -> bool:
        """
        Determine if a message is a tool result.
        
        Args:
            message: Message to check
            
        Returns:
            True if message is a tool result
        """
        try:
            # Import message types dynamically to handle different langchain versions
            from langchain_core.messages import ToolMessage, SystemMessage
        except ImportError:
            try:
                from langchain.schema.messages import ToolMessage, SystemMessage
            except ImportError:
                from langchain.schema import ToolMessage, SystemMessage
        
        # Check for ToolMessage type
        if hasattr(message, '__class__') and message.__class__.__name__ == 'ToolMessage':
            return True
        
        # Check for SystemMessage with tool result pattern
        if (hasattr(message, '__class__') and message.__class__.__name__ == 'SystemMessage' and
            hasattr(message, 'content') and message.content and
            ("Tool " in message.content and " result:" in message.content)):
            return True
        
        return False
    
    def filter_conversation(self, conversation_history: List, max_tokens: Optional[int] = None, 
                          manager_system_prompt: Optional[str] = None) -> List:
        """
        Filter conversation history for manager agent consumption.
        
        This creates a filtered message list that:
        1. Replaces the original system message with a manager-specific system prompt
        2. Preserves recent messages in full (last 3-5 messages)
        3. Summarizes older messages for context
        4. Adds a final system message instructing manager-style response
        
        Args:
            conversation_history: Complete conversation history
            max_tokens: Optional maximum token limit (affects summary length)
            manager_system_prompt: System prompt specifically for the manager agent
            
        Returns:
            Filtered list of messages optimized for manager agent oversight
        """
        logger.info("🔍 MANAGER AGENT CONVERSATION FILTERING")
        logger.info(f"   Original history: {len(conversation_history)} messages")
        
        # Phase 1: Analyze original conversation tokens
        original_tokens = self._count_conversation_tokens(conversation_history) if max_tokens else 0
        if max_tokens:
            logger.info(f"   📊 Original: {original_tokens} tokens, Target: {max_tokens} tokens")
        
        # Phase 2: Create filtered conversation for manager oversight
        if not conversation_history:
            return []
        
        # Determine how much of the conversation to include based on token limits
        if max_tokens and max_tokens < 2000:
            # Very tight token limit - focus on most recent interactions
            recent_count = min(3, len(conversation_history))
            logger.info(f"   📋 Tight token limit: focusing on most recent {recent_count} messages")
        elif max_tokens and max_tokens < 5000:
            # Moderate token limit - include recent plus key earlier messages
            recent_count = min(5, len(conversation_history))
            logger.info(f"   📋 Moderate token limit: including recent {recent_count} messages")
        else:
            # Generous or no token limit - include broader context
            recent_count = min(8, len(conversation_history))
            logger.info(f"   📋 Generous token limit: including recent {recent_count} messages")
        
        # Phase 3: Build filtered message list
        try:
            from langchain_core.messages import SystemMessage, HumanMessage
        except ImportError:
            try:
                from langchain.schema.messages import SystemMessage, HumanMessage
            except ImportError:
                from langchain.schema import SystemMessage, HumanMessage
        
        filtered_messages = []
        
        # 1. Replace original system message with manager-specific prompt
        if manager_system_prompt:
            manager_system_msg = SystemMessage(content=manager_system_prompt)
            filtered_messages.append(manager_system_msg)
            logger.info("   ✅ Added manager-specific system prompt")
        
        # 2. Add conversation overview as a summarized context message
        total_messages = len(conversation_history)
        tool_message_count = sum(1 for msg in conversation_history if self._is_tool_result_message(msg))
        ai_message_count = sum(1 for msg in conversation_history 
                              if hasattr(msg, '__class__') and msg.__class__.__name__ == 'AIMessage')
        
        context_lines = [
            f"📊 CONVERSATION OVERVIEW: {total_messages} messages ({tool_message_count} tool results, {ai_message_count} AI responses)",
            "",
            f"📋 RECENT CONVERSATION ({min(recent_count, len(conversation_history))} messages):"
        ]
        
        # 3. Add recent messages (preserve in full or with light summarization)
        recent_messages = conversation_history[-recent_count:] if recent_count < len(conversation_history) else conversation_history
        
        for i, msg in enumerate(recent_messages):
            # Calculate the actual index in the full conversation
            actual_index = len(conversation_history) - len(recent_messages) + i
            
            # Skip the original system message since we replaced it
            if actual_index == 0 and hasattr(msg, '__class__') and msg.__class__.__name__ == 'SystemMessage':
                continue
            
            # For recent messages, preserve them in full
            # Don't truncate - the manager needs full context to coach effectively
            if hasattr(msg, 'content') and msg.content:
                content = msg.content
                
                # Add to context summary
                message_summary = self._create_message_summary(msg, actual_index)
                context_lines.append(f"   {message_summary}")
        
        # 4. Add context as a system message
        context_content = "\n".join(context_lines)
        context_msg = SystemMessage(content=context_content)
        filtered_messages.append(context_msg)
        
        # 5. Add the most recent assistant message if it exists (what we're responding to)
        last_ai_message = None
        for msg in reversed(conversation_history):
            if hasattr(msg, '__class__') and msg.__class__.__name__ == 'AIMessage':
                last_ai_message = msg
                break
        
        if last_ai_message:
            filtered_messages.append(last_ai_message)
            logger.info("   ✅ Added most recent assistant message for context")
        
        # 6. Add SOP agent explanation and instruction for manager-style response
        # Simple SOP agent explanation message
        sop_explanation = "You are a coaching manager who helps AI assistants by asking thoughtful questions about their next steps. Ask questions that help the assistant think through what they should do next, rather than giving direct orders. Be supportive and give the assistant agency to decide based on your coaching questions."
        manager_instruction = SystemMessage(content=sop_explanation)
        filtered_messages.append(manager_instruction)
        
        # Phase 4: Final token analysis
        filtered_tokens = self._count_conversation_tokens(filtered_messages) if max_tokens else 0
        logger.info(f"   Filtered history: {len(filtered_messages)} messages")
        
        if max_tokens:
            token_reduction = original_tokens - filtered_tokens
            logger.info(f"   📊 Filtered: {filtered_tokens} tokens (reduced by {token_reduction})")
            if filtered_tokens > max_tokens:
                logger.info(f"   ⚠️  Still exceeds limit by {filtered_tokens - max_tokens} tokens")
            else:
                logger.info(f"   ✅ Now within limit ({max_tokens - filtered_tokens} tokens remaining)")
        
        logger.info("🔍 MANAGER AGENT FILTERING COMPLETE")
        return filtered_messages


class SOPAgentConversationFilter(ConversationFilterBase, ConversationFilter):
    """
    Specialized conversation filter for SOP (Standard Operating Procedure) agents that need 
    minimal conversation context to make orchestration decisions.
    
    This filter is designed to prevent the SOP agent from getting overwhelmed by detailed 
    conversation history while still providing enough context to make informed guidance decisions.
    
    Key behaviors:
    1. Preserves only the most recent message (last assistant or user message)
    2. Truncates all other messages to brief summaries
    3. Maintains conversation flow indicators for stage awareness
    4. Optimized for orchestration/guidance rather than detailed technical work
    """
    
    def __init__(self, model: str = "gpt-4o"):
        """
        Initialize the SOP agent conversation filter.
        
        Args:
            model: Model name for token encoding (default: "gpt-4o")
        """
        super().__init__(model)
    
    def _is_tool_result_message(self, message) -> bool:
        """
        Determine if a message is a tool result.
        
        Args:
            message: Message to check
            
        Returns:
            True if message is a tool result
        """
        try:
            # Import message types dynamically to handle different langchain versions
            from langchain_core.messages import ToolMessage, SystemMessage
        except ImportError:
            try:
                from langchain.schema.messages import ToolMessage, SystemMessage
            except ImportError:
                from langchain.schema import ToolMessage, SystemMessage
        
        # Check for ToolMessage type
        if hasattr(message, '__class__') and message.__class__.__name__ == 'ToolMessage':
            return True
        
        # Check for SystemMessage with tool result pattern
        if (hasattr(message, '__class__') and message.__class__.__name__ == 'SystemMessage' and
            hasattr(message, 'content') and message.content and
            ("Tool " in message.content and " result:" in message.content)):
            return True
        
        return False
    
    def _create_truncated_summary(self, message, index: int) -> str:
        """
        Create a very brief summary of a message for SOP agent consumption.
        
        Args:
            message: Message to summarize
            index: Index of message in conversation
            
        Returns:
            Brief summarized message content
        """
        if not hasattr(message, 'content') or not message.content:
            message_type = self._get_message_type_name(message)
            return f"[{index}] {message_type}: <empty>"
        
        message_type = self._get_message_type_name(message)
        
        if message_type == "System":
            # System messages - very brief, focus on role/setup
            return f"[{index}] System: Initial setup and role definition"
        
        elif message_type == "Human":
            # Human messages - preserve key requests but very brief
            content_preview = message.content[:60] + "..." if len(message.content) > 60 else message.content
            return f"[{index}] User: {content_preview}"
        
        elif message_type == "AI":
            # AI messages - detect stage and tool usage
            has_tool_calls = hasattr(message, 'tool_calls') and message.tool_calls
            content = message.content or ""
            
            # Detect conversation stage from content
            stage_indicator = ""
            if any(keyword in content.lower() for keyword in ['procedure', 'hypothesis', 'configuration', 'yaml']):
                stage_indicator = " [HYPOTHESIS_STAGE]"
            elif any(keyword in content.lower() for keyword in ['pattern', 'root cause', 'synthesis', 'analysis shows']):
                stage_indicator = " [SYNTHESIS_STAGE]"
            elif any(keyword in content.lower() for keyword in ['examining', 'found feedback', 'analyzing']):
                stage_indicator = " [EXPLORATION_STAGE]"
            
            if has_tool_calls:
                tool_names = [tc.get('name', 'unknown') if isinstance(tc, dict) else str(tc) for tc in message.tool_calls]
                return f"[{index}] Assistant: Used tools: {', '.join(tool_names)}{stage_indicator}"
            else:
                content_preview = content[:40] + "..." if len(content) > 40 else content
                return f"[{index}] Assistant: {content_preview}{stage_indicator}"
        
        elif message_type == "Tool":
            # Tool messages - very brief result summary
            if self._is_tool_result_message(message):
                return f"[{index}] Tool Result: <data returned>"
            else:
                return f"[{index}] Tool: <executed>"
        
        else:
            # Unknown message types - minimal summary
            return f"[{index}] {message_type}: <content>"
    
    def filter_conversation(self, conversation_history: List, max_tokens: Optional[int] = None) -> List:
        """
        Filter conversation history for SOP agent consumption.
        
        This creates a minimal context that preserves:
        1. The most recent message in full (for immediate context)
        2. Brief summaries of earlier messages (for flow awareness)
        3. Stage transition indicators
        
        Args:
            conversation_history: Complete conversation history
            max_tokens: Optional maximum token limit
            
        Returns:
            Filtered conversation history with minimal context for SOP oversight
        """
        logger.info("🔍 SOP AGENT CONVERSATION FILTERING")
        logger.info(f"   Original history: {len(conversation_history)} messages")
        
        if not conversation_history:
            logger.info("   No messages to filter")
            return []
        
        # Phase 1: Analyze original conversation
        original_tokens = self._count_conversation_tokens(conversation_history) if max_tokens else 0
        if max_tokens:
            logger.info(f"   📊 Original: {original_tokens} tokens, Target: {max_tokens} tokens")
        
        # Phase 2: Determine how many messages to preserve in full
        # Always preserve the most recent message in full for immediate context
        messages_to_preserve_full = 1
        
        # Phase 3: Create filtered conversation
        filtered_history = []
        
        for i, message in enumerate(conversation_history):
            is_recent = i >= len(conversation_history) - messages_to_preserve_full
            
            if is_recent:
                # Keep recent messages in full
                filtered_history.append(message)
                message_tokens = self._count_message_tokens(message) if max_tokens else 0
                message_type = self._get_message_type_name(message)
                content_length = len(message.content) if hasattr(message, 'content') and message.content else 0
                token_info = f", {message_tokens} tokens" if max_tokens else ""
                logger.info(f"   ✅ Preserving recent message [{i}] {message_type} in full ({content_length} chars{token_info})")
            else:
                # Create truncated summary for older messages
                summary_content = self._create_truncated_summary(message, i)
                
                # Create a SystemMessage with the summary to avoid type issues
                try:
                    from langchain_core.messages import SystemMessage
                except ImportError:
                    try:
                        from langchain.schema.messages import SystemMessage
                    except ImportError:
                        from langchain.schema import SystemMessage
                
                summary_message = SystemMessage(content=summary_content)
                filtered_history.append(summary_message)
                
                summary_tokens = self._count_message_tokens(summary_message) if max_tokens else 0
                original_tokens = self._count_message_tokens(message) if max_tokens else 0
                token_info = f", {original_tokens}→{summary_tokens} tokens" if max_tokens else ""
                logger.info(f"   ✂️  Summarized message [{i}] ({len(summary_content)} chars{token_info})")
        
        # Phase 4: Final analysis
        filtered_tokens = self._count_conversation_tokens(filtered_history) if max_tokens else 0
        logger.info(f"   Filtered history: {len(filtered_history)} messages")
        
        if max_tokens:
            token_reduction = original_tokens - filtered_tokens
            logger.info(f"   📊 Filtered: {filtered_tokens} tokens (reduced by {token_reduction})")
            if filtered_tokens > max_tokens:
                logger.info(f"   ⚠️  Still exceeds limit by {filtered_tokens - max_tokens} tokens")
            else:
                logger.info(f"   ✅ Now within limit ({max_tokens - filtered_tokens} tokens remaining)")
        
        logger.info("🔍 SOP AGENT FILTERING COMPLETE")
        return filtered_history
    