"""
Procedure Executor - Routes procedure execution based on class field.

Supports multiple procedure execution engines:
- LuaDSL: New Lua-based DSL runtime
- SOPAgent: Existing SOP agent system (default)
"""

import logging
import yaml
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


async def execute_procedure(
    procedure_id: str,
    procedure_code: str,
    client,
    mcp_server,
    context: Optional[Dict[str, Any]] = None,
    **options
) -> Dict[str, Any]:
    """
    Execute a procedure using the appropriate engine.

    Args:
        procedure_id: Procedure ID
        procedure_code: Procedure code (Lua DSL format or legacy YAML)
        client: PlexusDashboardClient instance
        mcp_server: MCP server for tool access
        context: Optional context dict with pre-loaded data
        **options: Additional execution options (openai_api_key, etc.)

    Returns:
        Execution results dict
    """
    try:
        # Auto-detect format: Lua DSL vs legacy YAML
        code_stripped = procedure_code.strip()
        is_lua_dsl = (
            code_stripped.startswith('--') or  # Lua comment
            'name(' in code_stripped or  # Lua DSL declaration
            'procedure(function' in code_stripped or  # Old Lua DSL procedure syntax
            'procedure({' in code_stripped or  # Old Lua DSL procedure syntax
            'procedure("' in code_stripped or  # New Lua DSL procedure syntax with name
            'agent(' in code_stripped  # Lua DSL agent
        )

        if is_lua_dsl:
            # Route to Lua DSL runtime
            logger.info(f"Routing procedure {procedure_id} to executor: LuaDSL (auto-detected)")
            return await _execute_lua_dsl(
                procedure_id,
                procedure_code,
                client,
                mcp_server,
                context,
                **options
            )

        # Try parsing as legacy YAML
        config = yaml.safe_load(procedure_code)

        if not isinstance(config, dict):
            raise ValueError("Invalid YAML: root must be a dictionary")

        # Check class field to determine executor
        procedure_class = config.get('class', 'SOPAgent')  # Default to SOPAgent for backward compatibility

        logger.info(f"Routing procedure {procedure_id} to executor: {procedure_class}")

        if procedure_class == 'LuaDSL':
            # Route to Lua DSL runtime
            return await _execute_lua_dsl(
                procedure_id,
                procedure_code,
                client,
                mcp_server,
                context,
                **options
            )

        elif procedure_class == 'SOPAgent' or not procedure_class:
            # Route to existing SOP agent system
            return await _execute_sop_agent(
                procedure_id,
                procedure_code,
                client,
                mcp_server,
                context,
                **options
            )

        else:
            # Unknown class
            error_msg = f"Unknown procedure class: {procedure_class}. Supported: LuaDSL, SOPAgent"
            logger.error(error_msg)
            return {
                'success': False,
                'procedure_id': procedure_id,
                'error': error_msg
            }

    except yaml.YAMLError as e:
        error_msg = f"Failed to parse procedure configuration: {e}"
        logger.error(error_msg)
        return {
            'success': False,
            'procedure_id': procedure_id,
            'error': error_msg
        }

    except Exception as e:
        error_msg = f"Procedure execution failed: {e}"
        logger.error(error_msg, exc_info=True)
        return {
            'success': False,
            'procedure_id': procedure_id,
            'error': error_msg
        }


async def _execute_lua_dsl(
    procedure_id: str,
    procedure_code: str,
    client,
    mcp_server,
    context: Optional[Dict[str, Any]],
    **options
) -> Dict[str, Any]:
    """
    Execute procedure using Tactus runtime with Plexus adapters.

    Args:
        procedure_id: Procedure ID
        procedure_code: Lua DSL procedure code
        client: PlexusDashboardClient
        mcp_server: MCP server
        context: Optional context
        **options: Additional options (openai_api_key, etc.)

    Returns:
        Execution results
    """
    logger.info(f"Executing procedure {procedure_id} with Tactus runtime")

    try:
        from tactus.core import TactusRuntime
        from .tactus_adapters import PlexusStorageAdapter, PlexusHITLAdapter, PlexusChatAdapter
        from .chat_recorder import ProcedureChatRecorder

        # Get OpenAI API key from options or environment
        openai_api_key = options.get('openai_api_key')

        if not openai_api_key:
            from plexus.config.loader import load_config
            load_config()
            import os
            openai_api_key = os.getenv('OPENAI_API_KEY')

        # Create Plexus adapters
        storage = PlexusStorageAdapter(client, procedure_id)
        chat_recorder = ProcedureChatRecorder(client, procedure_id)
        hitl = PlexusHITLAdapter(client, procedure_id, chat_recorder, storage)
        chat = PlexusChatAdapter(chat_recorder)

        # Create Tactus runtime with Plexus adapters
        runtime = TactusRuntime(
            procedure_id=procedure_id,
            storage_backend=storage,
            hitl_handler=hitl,
            chat_recorder=chat,
            mcp_server=mcp_server,
            openai_api_key=openai_api_key
        )

        # Execute workflow with Lua DSL format
        result = await runtime.execute(procedure_code, context, format="lua")

        logger.info(f"Tactus execution complete: {result.get('success')}")
        return result

    except Exception as e:
        logger.error(f"Lua DSL execution error: {e}", exc_info=True)
        return {
            'success': False,
            'procedure_id': procedure_id,
            'error': f"Lua DSL execution error: {e}"
        }


async def _execute_sop_agent(
    procedure_id: str,
    procedure_code: str,
    client,
    mcp_server,
    context: Optional[Dict[str, Any]],
    **options
) -> Dict[str, Any]:
    """
    Execute procedure using existing SOP agent system (legacy).

    Args:
        procedure_id: Procedure ID
        procedure_code: YAML configuration (legacy format)
        client: PlexusDashboardClient
        mcp_server: MCP server
        context: Optional context
        **options: Additional options

    Returns:
        Execution results
    """
    logger.info(f"Executing procedure {procedure_id} with SOP Agent system")

    try:
        from .procedure_sop_agent import run_sop_guided_procedure

        # Get OpenAI API key
        openai_api_key = options.get('openai_api_key')

        # Execute with SOP agent
        result = await run_sop_guided_procedure(
            procedure_id=procedure_id,
            experiment_yaml=procedure_code,
            mcp_server=mcp_server,
            openai_api_key=openai_api_key,
            experiment_context=context,
            client=client,
            model_config=options.get('model_config')
        )

        logger.info(f"SOP Agent execution complete: {result.get('success')}")
        return result

    except Exception as e:
        logger.error(f"SOP Agent execution error: {e}", exc_info=True)
        return {
            'success': False,
            'procedure_id': procedure_id,
            'error': f"SOP Agent execution error: {e}"
        }
