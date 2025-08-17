"""
Chat recording callbacks for LangChain AI interactions.

Handles recording of LLM messages, tool calls, and tool responses to the chat recorder.
"""

import json
import logging
from langchain.callbacks.base import BaseCallbackHandler

logger = logging.getLogger(__name__)


def truncate_content(content: str, max_length: int = 100) -> str:
    """Truncate content to max_length with ellipsis."""
    if len(content) <= max_length:
        return content
    return content[:max_length] + "..."


class ChatRecordingCallback(BaseCallbackHandler):
    """
    Streamlined callback to record LLM messages and tool calls.
    
    Clear responsibilities:
    - on_agent_action: Record tool calls only
    - on_tool_end: Record tool responses only  
    - on_llm_end: Record assistant messages only
    - on_agent_finish: Record final agent responses only
    """
    
    def __init__(self, recorder, mcp_adapter=None):
        super().__init__()
        self.recorder = recorder
        self.mcp_adapter = mcp_adapter  # Reference to the MCP tools adapter
        self.tool_call_messages = {}  # Maps run_id to (tool_call_id, tool_name)
        logger.info("CALLBACK INIT: Streamlined ChatRecordingCallback initialized")
        
        # Import json at class level for use in methods
        self.json = json

    def on_chain_start(self, serialized, inputs, **kwargs):
        """Called when chain starts - verify callback is working."""
        logger.info(f"CALLBACK: Chain starting - callback system active")

    def on_agent_action(self, action, **kwargs):
        """Record tool calls when agent decides to use a tool."""
        run_id = kwargs.get('run_id')
        input_preview = str(action.tool_input)[:200] + "..." if len(str(action.tool_input)) > 200 else str(action.tool_input)
        logger.info(f"CALLBACK: Agent action - tool: {action.tool}, run_id: {run_id}")
        logger.info(f"CALLBACK: Tool input: {input_preview}")
        
        if self.recorder:
            try:
                # Check if there's reasoning/thought content in the action log
                reasoning_content = None
                if hasattr(action, 'log') and action.log:
                    # Extract reasoning from the action log
                    log_text = action.log.strip()
                    if log_text and len(log_text) > 20:  # Meaningful content
                        # Split on common patterns to extract just the reasoning part
                        if "Action:" in log_text:
                            reasoning_part = log_text.split("Action:")[0].strip()
                            if reasoning_part and len(reasoning_part) > 20:
                                reasoning_content = reasoning_part
                        elif "Thought:" in log_text:
                            thought_part = log_text.split("Thought:")[1].strip() if "Thought:" in log_text else ""
                            if thought_part and len(thought_part) > 20:
                                reasoning_content = thought_part
                
                # Record assistant reasoning if found
                if reasoning_content:
                    reasoning_preview = reasoning_content[:150] + "..." if len(reasoning_content) > 150 else reasoning_content
                    logger.info(f"CALLBACK: Recording assistant reasoning ({len(reasoning_content)} chars): {reasoning_preview}")
                    
                    reasoning_id = self.recorder.record_message_sync(
                        role='ASSISTANT',
                        content=reasoning_content,
                        message_type='MESSAGE'
                    )
                    
                    if reasoning_id:
                        logger.info(f"CALLBACK: ✅ Recorded assistant reasoning {reasoning_id}")
                    else:
                        logger.error(f"CALLBACK: ❌ Failed to record assistant reasoning")
                
                # Record the tool call
                param_str = self.json.dumps(action.tool_input, indent=2) if isinstance(action.tool_input, dict) else str(action.tool_input)
                content = f"Agent calling tool: {action.tool}\n\nParameters:\n{param_str}"
                
                tool_call_id = self.recorder.record_message_sync(
                    role='ASSISTANT',
                    content=content,
                    message_type='TOOL_CALL',
                    tool_name=action.tool
                )
                
                if tool_call_id and run_id:
                    self.tool_call_messages[run_id] = (tool_call_id, action.tool)
                    # Also store for MCP wrapper to use
                    if self.mcp_adapter and hasattr(self.mcp_adapter, 'pending_tool_calls'):
                        self.mcp_adapter.pending_tool_calls[action.tool] = tool_call_id
                    logger.info(f"CALLBACK: ✅ Recorded tool call {tool_call_id} for run {run_id}")
                else:
                    logger.error(f"CALLBACK: ❌ Failed to record tool call")
                
            except Exception as e:
                logger.error(f"CALLBACK: ❌ Failed to record tool call: {e}")
                import traceback
                logger.error(f"CALLBACK: Full traceback: {traceback.format_exc()}")

    def on_tool_end(self, output, **kwargs):
        """Record tool responses when tools finish executing."""
        run_id = kwargs.get('run_id')
        output_preview = truncate_content(str(output), 150)
        logger.info(f"CALLBACK: Tool end - run_id: {run_id}")
        logger.info(f"CALLBACK: Tool output: {output_preview}")
        
        if self.recorder and run_id in self.tool_call_messages:
            tool_call_id, tool_name = self.tool_call_messages[run_id]
            logger.info(f"CALLBACK: ✅ Found matching tool call {tool_call_id} for tool {tool_name}")
            
            try:
                response_str = self.json.dumps(output, indent=2) if isinstance(output, dict) else str(output)
                content = f"Response from tool: {tool_name}\n\nResponse:\n{response_str}"
                
                response_id = self.recorder.record_message_sync(
                    role='TOOL',
                    content=content,
                    message_type='TOOL_RESPONSE',
                    tool_name=tool_name,
                    parent_message_id=tool_call_id
                )
                
                if response_id:
                    logger.info(f"CALLBACK: ✅ Successfully recorded tool response {response_id}")
                else:
                    logger.error(f"CALLBACK: ❌ Failed to record tool response")
                
                # Clean up the stored tool call info
                del self.tool_call_messages[run_id]
                
            except Exception as e:
                logger.error(f"CALLBACK: ❌ Failed to record tool response: {e}")
                import traceback
                logger.error(f"CALLBACK: Full traceback: {traceback.format_exc()}")
        else:
            if not self.recorder:
                logger.warning("CALLBACK: ❌ No recorder available")
            elif run_id not in self.tool_call_messages:
                logger.warning(f"CALLBACK: ❌ No tool call found for run_id {run_id}")
                logger.warning(f"CALLBACK: Available runs: {list(self.tool_call_messages.keys())}")

    def on_agent_finish(self, finish, **kwargs):
        """Record final agent responses when agent completes.""" 
        run_id = kwargs.get('run_id')
        logger.info(f"CALLBACK: Agent finish - run_id: {run_id}")
        
        if not self.recorder:
            return
        
        try:
            agent_output = None
            
            # Extract final response from agent finish object
            if hasattr(finish, 'return_values') and finish.return_values:
                if isinstance(finish.return_values, dict):
                    # Look for common output keys
                    for key in ['output', 'result', 'text', 'answer']:
                        if key in finish.return_values and finish.return_values[key]:
                            agent_output = finish.return_values[key]
                            break
                elif isinstance(finish.return_values, str):
                    agent_output = finish.return_values
            elif hasattr(finish, 'log') and finish.log:
                agent_output = finish.log
            
            # Record meaningful final responses
            if agent_output and agent_output.strip() and len(agent_output.strip()) > 10:
                full_text = agent_output.strip()
                content_preview = full_text[:200] + "..." if len(full_text) > 200 else full_text
                logger.info(f"CALLBACK: Recording final agent response ({len(full_text)} chars): {content_preview}")
                
                result = self.recorder.record_message_sync(
                    role='ASSISTANT',
                    content=full_text,
                    message_type='MESSAGE'
                )
                
                if result:
                    logger.info(f"CALLBACK: ✅ Recorded final agent message {result}")
                else:
                    logger.error(f"CALLBACK: ❌ Failed to record final agent message")
        
        except Exception as e:
            logger.error(f"CALLBACK: ❌ Error in on_agent_finish: {e}")
            import traceback
            logger.error(f"CALLBACK: Full traceback: {traceback.format_exc()}")

    def on_llm_end(self, response, **kwargs):
        """Record LLM responses - captures all assistant messages."""
        run_id = kwargs.get('run_id')
        logger.info(f"CALLBACK: LLM end - run_id: {run_id}, response type: {type(response)}")
        logger.info(f"CALLBACK: LLM response object: {response}")
        
        if not self.recorder or not response:
            logger.info(f"CALLBACK: Skipping LLM end - recorder: {bool(self.recorder)}, response: {bool(response)}")
            return
        
        try:
            extracted_text = None
            
            # Extract text from LangChain response object
            if hasattr(response, 'generations') and response.generations:
                for generation_list in response.generations:
                    for generation in generation_list:
                        if hasattr(generation, 'text') and generation.text:
                            extracted_text = generation.text.strip()
                            break
                        elif hasattr(generation, 'message') and hasattr(generation.message, 'content'):
                            extracted_text = generation.message.content.strip()
                            break
                    if extracted_text:
                        break
            elif hasattr(response, 'content') and response.content:
                extracted_text = response.content.strip()
            elif hasattr(response, 'text') and response.text:
                extracted_text = response.text.strip()
            elif isinstance(response, str):
                extracted_text = response.strip()
            
            # Record meaningful assistant responses
            if extracted_text and len(extracted_text) > 10:
                content_preview = extracted_text[:200] + "..." if len(extracted_text) > 200 else extracted_text
                logger.info(f"CALLBACK: Recording assistant response ({len(extracted_text)} chars): {content_preview}")
                
                response_id = self.recorder.record_message_sync(
                    role='ASSISTANT',
                    content=extracted_text,
                    message_type='MESSAGE'
                )
                
                if response_id:
                    logger.info(f"CALLBACK: ✅ Recorded assistant message {response_id}")
                else:
                    logger.error(f"CALLBACK: ❌ Failed to record assistant message")
            
        except Exception as e:
            logger.error(f"CALLBACK: ❌ Error recording LLM response: {e}")
            import traceback
            logger.error(f"CALLBACK: Full traceback: {traceback.format_exc()}")
