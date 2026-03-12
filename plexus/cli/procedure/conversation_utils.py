"""
Conversation utilities for procedure AI execution.

This module provides utilities for managing conversation history, including
filtering and processing messages for AI model context limits.
"""

import logging
from typing import List, Optional
try:
    import tiktoken
except ImportError:
    tiktoken = None

logger = logging.getLogger(__name__)


class ConversationUtils:
    """Utility class for conversation management in procedure execution."""
    
    @staticmethod
    def _count_tokens_in_conversation(conversation_history: List, model: str = "gpt-4") -> int:
        """
        Count the total number of tokens in a conversation history using TikToken.
        
        Args:
            conversation_history: List of conversation messages
            model: Model name for token encoding (default: "gpt-4")
            
        Returns:
            Total token count for the conversation
        """
        if not tiktoken:
            logger.warning("TikToken not available - cannot count tokens accurately")
            return 0
        
        try:
            encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            logger.warning(f"Model '{model}' not recognized by tiktoken, using cl100k_base encoding")
            encoding = tiktoken.get_encoding("cl100k_base")
        
        total_tokens = 0
        
        for message in conversation_history:
            if hasattr(message, 'content') and message.content:
                # Count tokens in message content
                content_tokens = len(encoding.encode(message.content))
                total_tokens += content_tokens
                
                # Add overhead tokens for message structure (role, etc.)
                # Based on OpenAI's token counting recommendations
                total_tokens += 4  # Every message follows <im_start>{role/name}\n{content}<im_end>\n
        
        # Add overhead for conversation structure
        total_tokens += 2  # Every conversation has additional overhead
        
        return total_tokens
    
    @staticmethod
    def filter_conversation_history_for_model(full_conversation_history: List, max_tokens: Optional[int] = None) -> List:
        """
        Filter the conversation history for the AI model to prevent context overflow.
        
        CRITICAL: This function creates a FILTERED representation of the conversation
        that is sent to the AI model. It is NOT the same as the complete conversation
        history that we maintain for chat recording and orchestration purposes.
        
        Filtering Rules:
        1. Keep all non-tool messages (SystemMessage, HumanMessage, AIMessage) intact
        2. Keep the most recent 2 tool result messages in full
        3. Truncate all older tool result messages to 500 characters + truncation notice
        4. This forces the AI to summarize its learnings since older tool details become ephemeral
        
        Token Counting (when max_tokens is provided):
        - Uses TikToken to count tokens in conversation
        - Currently logs token usage for monitoring (future: implement token-based filtering)
        
        Args:
            full_conversation_history: Complete conversation history with all messages
            max_tokens: Optional maximum token limit for the conversation
            
        Returns:
            Filtered conversation history suitable for model context limits
        """
        try:
            from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
        except ImportError:
            from langchain.schema import SystemMessage, HumanMessage, AIMessage
        
        filtered_history = []
        tool_result_messages = []
        
        logger.info("🔍 FILTERING CONVERSATION HISTORY FOR MODEL")
        logger.info(f"   Original history: {len(full_conversation_history)} messages")
        
        # Token counting (if max_tokens is provided)
        if max_tokens is not None:
            original_token_count = ConversationUtils._count_tokens_in_conversation(full_conversation_history)
            logger.info(f"   📊 Token analysis - Original: {original_token_count} tokens, Limit: {max_tokens} tokens")
            if original_token_count > max_tokens:
                logger.info(f"   ⚠️  Token limit exceeded by {original_token_count - max_tokens} tokens - filtering needed")
            else:
                logger.info(f"   ✅ Token count within limit ({max_tokens - original_token_count} tokens remaining)")
        
        # First pass: identify all tool result messages (SystemMessages containing tool results)
        for i, message in enumerate(full_conversation_history):
            if (isinstance(message, SystemMessage) and 
                message.content and 
                ("Tool " in message.content and " result:" in message.content)):
                tool_result_messages.append((i, message))
        
        logger.info(f"   Found {len(tool_result_messages)} tool result messages")
        
        # Second pass: build filtered history with truncation rules
        for i, message in enumerate(full_conversation_history):
            if isinstance(message, SystemMessage) and (i, message) in tool_result_messages:
                # This is a tool result message - apply truncation rules
                tool_result_index = next(idx for idx, (msg_i, msg) in enumerate(tool_result_messages) if msg_i == i)
                recent_tool_results_count = len(tool_result_messages)
                
                # Keep the most recent 2 tool results in full, truncate older ones
                if tool_result_index >= recent_tool_results_count - 2:
                    # This is one of the most recent 2 tool results - keep in full
                    filtered_history.append(message)
                    logger.info(f"   ✅ Keeping recent tool result #{tool_result_index + 1} in full ({len(message.content)} chars)")
                else:
                    # This is an older tool result - only truncate if it exceeds the limit
                    if len(message.content) > 500:
                        # Truncate large tool results
                        truncated_content = message.content[:500]
                        truncation_notice = f"\n\n[TOOL RESULT TRUNCATED at 500 chars - original was {len(message.content)} chars. You must summarize your key learnings from this tool call in your response since you will not see these details again.]"
                        
                        truncated_message = SystemMessage(content=truncated_content + truncation_notice)
                        filtered_history.append(truncated_message)
                        logger.info(f"   ✂️  Truncated older tool result #{tool_result_index + 1} ({len(message.content)} → 500 + notice chars)")
                    else:
                        # Small tool result - keep as-is (no point in adding overhead)
                        filtered_history.append(message)
                        logger.info(f"   ➡️  Keeping small tool result #{tool_result_index + 1} as-is ({len(message.content)} chars - under limit)")
            else:
                # Non-tool message - keep as-is
                filtered_history.append(message)
                msg_type = type(message).__name__.replace("Message", "")
                logger.info(f"   ➡️  Keeping {msg_type} message as-is ({len(message.content)} chars)")
        
        logger.info(f"   Filtered history: {len(filtered_history)} messages")
        
        # Token counting for filtered history (if max_tokens was provided)
        if max_tokens is not None:
            filtered_token_count = ConversationUtils._count_tokens_in_conversation(filtered_history)
            token_reduction = original_token_count - filtered_token_count
            logger.info(f"   📊 Token analysis - Filtered: {filtered_token_count} tokens (reduced by {token_reduction})")
            if filtered_token_count > max_tokens:
                logger.info(f"   ⚠️  Filtered conversation still exceeds limit by {filtered_token_count - max_tokens} tokens")
            else:
                logger.info(f"   ✅ Filtered conversation within limit ({max_tokens - filtered_token_count} tokens remaining)")
        
        logger.info("🔍 CONVERSATION FILTERING COMPLETE")
        
        return filtered_history