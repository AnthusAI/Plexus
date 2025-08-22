"""
Conversation utilities for experiment AI execution.

This module provides utilities for managing conversation history, including
filtering and processing messages for AI model context limits.
"""

import logging
from typing import List

logger = logging.getLogger(__name__)


class ConversationUtils:
    """Utility class for conversation management in experiment execution."""
    
    @staticmethod
    def filter_conversation_history_for_model(full_conversation_history: List) -> List:
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
        
        Args:
            full_conversation_history: Complete conversation history with all messages
            
        Returns:
            Filtered conversation history suitable for model context limits
        """
        from langchain.schema import SystemMessage, HumanMessage, AIMessage
        
        filtered_history = []
        tool_result_messages = []
        
        logger.info("🔍 FILTERING CONVERSATION HISTORY FOR MODEL")
        logger.info(f"   Original history: {len(full_conversation_history)} messages")
        
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
        logger.info("🔍 CONVERSATION FILTERING COMPLETE")
        
        return filtered_history