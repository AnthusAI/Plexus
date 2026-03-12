"""
Test Phase Agent - Creates ScoreVersions from hypotheses

This agent handles the test phase of the SOP procedure workflow:
1. Pulls baseline score YAML to local cache
2. Creates temp copy of YAML for editing
3. Uses LLM with file editing tools to modify YAML based on hypothesis
4. Validates edited YAML via syntax check and predict tool
5. Pushes valid YAML to new ScoreVersion
6. Updates GraphNode metadata with scoreVersionId
"""

import asyncio
import logging
import os
import tempfile
import uuid
import yaml
import re
from typing import Dict, Any, Optional, List
from pathlib import Path

logger = logging.getLogger(__name__)


class TestPhaseAgent:
    """Agent for creating ScoreVersions that implement hypothesis ideas."""

    def __init__(self, client):
        """
        Initialize the TestPhaseAgent.

        Args:
            client: PlexusDashboardClient for API operations
        """
        self.client = client
        self.temp_dir = None

    async def execute(
        self,
        hypothesis_node,
        score_version_id: str,
        procedure_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute the test phase for a single hypothesis node.

        This creates a new ScoreVersion with YAML code that implements
        the hypothesis, validates it, and updates the node metadata.

        Args:
            hypothesis_node: GraphNode containing the hypothesis
            score_version_id: ID of baseline ScoreVersion to start from
            procedure_context: Context dict with scorecard/score info, docs, etc.

        Returns:
            Dict with success status, new score_version_id, and node_id
        """
        try:
            logger.info(f"Starting test phase execution for hypothesis node {hypothesis_node.id}")

            # 1. Pull score YAML to local cache
            logger.info(f"Pulling ScoreVersion {score_version_id} YAML to local cache")
            yaml_path = await self._pull_score_yaml(score_version_id, procedure_context)

            if not yaml_path:
                return {
                    "success": False,
                    "error": "Failed to pull score YAML to local cache",
                    "node_id": hypothesis_node.id
                }

            # 2. Create temp copy for editing
            logger.info(f"Creating temporary copy of YAML for editing")
            temp_yaml_path = self._create_temp_copy(yaml_path)

            # 3. Run LLM editing process
            logger.info(f"Running LLM-based YAML editing for hypothesis")
            edit_success = await self._edit_yaml_with_llm(
                temp_yaml_path,
                hypothesis_node,
                procedure_context
            )

            if not edit_success:
                return {
                    "success": False,
                    "error": "LLM failed to edit YAML successfully",
                    "node_id": hypothesis_node.id,
                    "temp_yaml_path": temp_yaml_path
                }

            # 4. Validate edited YAML with auto-fix attempt
            logger.info(f"Validating edited YAML")
            validation_result = await self._validate_yaml(temp_yaml_path, procedure_context)

            if not validation_result["success"]:
                logger.warning(f"Initial YAML validation failed. Attempting auto-fix reformat: {validation_result['error']}")
                auto_fix_ok = self._attempt_yaml_autofix(temp_yaml_path)
                if auto_fix_ok:
                    logger.info("Re-validating after auto-fix")
                    validation_result = await self._validate_yaml(temp_yaml_path, procedure_context)

            if not validation_result["success"]:
                return {
                    "success": False,
                    "error": f"YAML validation failed: {validation_result['error']}",
                    "node_id": hypothesis_node.id,
                    "temp_yaml_path": temp_yaml_path
                }

            # 5. Push to new ScoreVersion
            logger.info(f"Pushing edited YAML to new ScoreVersion")
            new_version_id = await self._push_new_version(
                temp_yaml_path,
                score_version_id,
                procedure_context,
                hypothesis_node
            )

            if not new_version_id:
                return {
                    "success": False,
                    "error": "Failed to push new ScoreVersion",
                    "node_id": hypothesis_node.id,
                    "temp_yaml_path": temp_yaml_path
                }

            # 6. Update GraphNode metadata
            logger.info(f"Updating GraphNode metadata with new ScoreVersion ID and parent version ID")
            await self._update_node_metadata(hypothesis_node.id, new_version_id, score_version_id)

            logger.info(f"✓ Successfully created ScoreVersion {new_version_id} for hypothesis node {hypothesis_node.id}")

            return {
                "success": True,
                "score_version_id": new_version_id,
                "node_id": hypothesis_node.id,
                "temp_yaml_path": temp_yaml_path
            }

        except Exception as e:
            logger.error(f"Error in test phase execution: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "node_id": hypothesis_node.id
            }

    async def _pull_score_yaml(self, score_version_id: str, context: Dict[str, Any]) -> Optional[str]:
        """
        Pull score YAML to local cache.

        Args:
            score_version_id: ID of the ScoreVersion to pull
            context: Procedure context with scorecard/score info

        Returns:
            Path to local YAML file, or None on failure
        """
        try:
            # Fetch the specific version's configuration via GraphQL query
            query = f"""
            query GetScoreVersionCode {{
                getScoreVersion(id: "{score_version_id}") {{
                    id
                    configuration
                }}
            }}
            """

            result = self.client.execute(query)
            if not result or 'getScoreVersion' not in result or not result['getScoreVersion']:
                logger.error(f"Failed to fetch ScoreVersion {score_version_id}")
                return None

            code = result['getScoreVersion'].get('configuration')
            if not code:
                logger.error(f"No configuration found in ScoreVersion {score_version_id}")
                return None

            # Save to local file in standard location
            import os
            from plexus.cli.shared import get_score_yaml_path

            local_yaml_path = get_score_yaml_path(
                context['scorecard_name'],
                context['score_name']
            )

            # Ensure directory exists
            os.makedirs(os.path.dirname(local_yaml_path), exist_ok=True)

            # Write the YAML content
            with open(local_yaml_path, 'w') as f:
                f.write(code)

            logger.info(f"Successfully pulled YAML to: {local_yaml_path}")
            return local_yaml_path

        except Exception as e:
            logger.error(f"Error pulling score YAML: {e}", exc_info=True)
            return None

    def _create_temp_copy(self, yaml_path: str) -> str:
        """
        Create a temporary copy of the YAML file for editing.

        Args:
            yaml_path: Path to original YAML file

        Returns:
            Path to temporary copy
        """
        try:
            # Create temp directory if needed
            if not self.temp_dir:
                self.temp_dir = tempfile.mkdtemp(prefix="plexus_test_phase_")
                logger.info(f"Created temp directory: {self.temp_dir}")

            # Generate unique filename
            temp_filename = f"hypothesis_{uuid.uuid4().hex[:8]}.yaml"
            temp_path = os.path.join(self.temp_dir, temp_filename)

            # Copy original to temp location
            with open(yaml_path, 'r') as src:
                yaml_content = src.read()

            with open(temp_path, 'w') as dst:
                dst.write(yaml_content)

            logger.info(f"Created temp copy: {temp_path}")
            return temp_path

        except Exception as e:
            logger.error(f"Error creating temp copy: {e}", exc_info=True)
            raise

    async def _edit_yaml_with_llm(
        self,
        yaml_path: str,
        hypothesis_node,
        context: Dict[str, Any]
    ) -> bool:
        """
        Use LLM with file editing tools to modify YAML based on hypothesis.

        Args:
            yaml_path: Path to YAML file to edit
            hypothesis_node: GraphNode with hypothesis description
            context: Procedure context with documentation

        Returns:
            True if editing succeeded, False otherwise
        """
        try:
            from langchain_openai import ChatOpenAI
            from langchain_core.tools import tool
            from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage

            # Extract hypothesis from node metadata
            hypothesis_text = "No hypothesis description available"
            if hypothesis_node.metadata:
                import json
                try:
                    metadata = json.loads(hypothesis_node.metadata) if isinstance(hypothesis_node.metadata, str) else hypothesis_node.metadata
                    hypothesis_text = metadata.get('hypothesis', hypothesis_text)
                except:
                    pass

            # Build system prompt with documentation
            score_yaml_docs = context.get('score_yaml_format_docs', 'Documentation not available')

            system_prompt = f"""You are a score configuration editor. Your task is to make FOCUSED YAML edits to implement a hypothesis.

CURRENT FILE TO EDIT:
{yaml_path}

HYPOTHESIS TO IMPLEMENT:
{hypothesis_text}

## What You Can Change

You can ONLY edit the YAML score configuration. Specifically:

**✅ YOU CAN:**
- Edit prompts (make clearer, add examples, adjust instructions)
- Modify valid_classes lists (add/remove/rename classifier options)
- Adjust node logic (add preprocessing, modify conditions)
- Change thresholds or criteria in prompts

**❌ YOU CANNOT:**
- Add features that require new code
- Change system architecture
- Modify data sources or collection
- Go outside YAML capabilities

## Your Process

1. read_file({yaml_path}) - See the current configuration
2. Find the relevant section (which prompt or node needs editing)
3. Make MINIMAL, TARGETED edits using edit_file
4. Call stop_procedure("Brief summary of changes made")

## Editing Strategy

**For prompt improvements:**
- Make prompts more specific and clear
- Add concrete examples to illustrate criteria
- Clarify edge cases or ambiguous situations

**For classifier adjustments:**
- Add/remove valid_classes options if hypothesis suggests it
- Rename classes for clarity

**For logic changes:**
- Add preprocessing steps if needed
- Modify decision flow between nodes
- Adjust conditional logic in prompts

## Critical Rules

- Make SMALL, INCREMENTAL edits - don't rewrite everything
- Use edit_file for each distinct change (old_content must match exactly)
- Keep changes focused on the hypothesis - don't make unrelated improvements
- Call stop_procedure when done - don't over-edit

## Example Workflow

1. read_file({yaml_path})
2. Identify target (e.g., "verification_check node prompt")
3. edit_file(path={yaml_path}, old_content="[exact text from prompt]", new_content="[updated prompt with pharmacy requirement]")
4. stop_procedure("Added pharmacy verification requirement to prompt")

START NOW: Use read_file to see the configuration, then make focused edits."""

            # Define tools
            @tool
            def read_file(path: str) -> str:
                """Read file contents from the specified path."""
                try:
                    with open(path, 'r') as f:
                        return f.read()
                except Exception as e:
                    return f"Error reading file: {e}"

            @tool
            def edit_file(path: str, old_content: str, new_content: str) -> str:
                """
                Edit file by replacing old_content with new_content.

                Args:
                    path: File path to edit
                    old_content: Content to find and replace (must be exact match)
                    new_content: Content to replace with
                """
                try:
                    with open(path, 'r') as f:
                        content = f.read()

                    if old_content not in content:
                        # Help the LLM understand what went wrong
                        return f"Error: old_content not found in file. The exact text you provided doesn't match anything in the file. Make sure to copy the exact text from the file, including all whitespace and formatting. First 100 chars of what you tried to match: {old_content[:100]}..."

                    updated = content.replace(old_content, new_content)

                    with open(path, 'w') as f:
                        f.write(updated)

                    return "Success: File updated successfully"
                except Exception as e:
                    return f"Error editing file: {e}"

            @tool
            def check_yaml_syntax(path: str) -> str:
                """Validate YAML syntax for the file at path. Returns 'OK' or an error message."""
                try:
                    with open(path, 'r') as f:
                        content = f.read()
                    yaml.safe_load(content)
                    return "OK"
                except Exception as e:
                    return f"YAML Error: {e}"

            @tool
            def stop_procedure(reason: str) -> str:
                """
                Signal that editing is complete.

                Args:
                    reason: Brief explanation of what changes were made
                """
                return f"Editing complete: {reason}"

            # Get OpenAI API key
            from plexus.config.loader import load_config
            load_config()
            import os
            api_key = os.getenv('OPENAI_API_KEY')

            if not api_key:
                logger.error("No OpenAI API key available")
                return False

            # Create LLM with tools (using gpt-4o for larger context window)
            llm = ChatOpenAI(model="gpt-4o", temperature=0.1, openai_api_key=api_key)
            tools = [read_file, edit_file, check_yaml_syntax, stop_procedure]
            llm_with_tools = llm.bind_tools(tools)

            # Run ReAct loop
            messages = [SystemMessage(content=system_prompt)]
            max_iterations = 50
            stop_called = False
            validation_repair_attempts = 0
            max_repair_attempts = 5

            for iteration in range(max_iterations):
                logger.info(f"LLM editing iteration {iteration + 1}/{max_iterations}")

                # Get LLM response
                response = llm_with_tools.invoke(messages)
                messages.append(response)

                # Check for tool calls
                if not hasattr(response, 'tool_calls') or not response.tool_calls:
                    # No tool calls - agent might be stuck
                    logger.warning(f"No tool calls in iteration {iteration + 1}")
                    # Give it a nudge
                    messages.append(HumanMessage(content="Please use the available tools to complete the task. Start by reading the file, then make necessary edits, and finally call stop_procedure."))
                    continue

                # Execute tool calls
                for tool_call in response.tool_calls:
                    tool_name = tool_call['name']
                    tool_args = tool_call['args']

                    logger.info(f"Executing tool: {tool_name}")

                    if tool_name == 'stop_procedure':
                        logger.info(f"stop_procedure called: {tool_args.get('reason', 'No reason')}")
                        stop_called = True
                        result = stop_procedure.func(**tool_args)
                    elif tool_name == 'read_file':
                        result = read_file.func(**tool_args)
                    elif tool_name == 'edit_file':
                        logger.info(f"edit_file args: path={tool_args.get('path')}, old_content length={len(tool_args.get('old_content', ''))}, new_content length={len(tool_args.get('new_content', ''))}")
                        result = edit_file.func(**tool_args)
                    elif tool_name == 'check_yaml_syntax':
                        result = check_yaml_syntax.func(**tool_args)
                    else:
                        result = f"Unknown tool: {tool_name}"

                    # Add tool result to conversation
                    messages.append(ToolMessage(content=str(result), tool_call_id=tool_call['id']))

                    if stop_called:
                        # Instead of immediately finishing, run validation and feed errors back for iterative repair
                        logger.info("Validating YAML after stop signal")
                        validation = await self._validate_yaml(yaml_path, context)
                        if validation.get('success'):
                            logger.info("✓ YAML validation passed after stop_procedure")
                            return True
                        else:
                            validation_repair_attempts += 1
                            if validation_repair_attempts > max_repair_attempts:
                                logger.error("Maximum validation repair attempts reached; failing editing loop")
                                return False

                            # Prepare helpful feedback with error details and code excerpt
                            error_msg = validation.get('error', 'Unknown validation error')
                            excerpt = ''
                            try:
                                # Attempt to extract line number from error message
                                line_match = re.search(r"line\s+(\d+)", error_msg)
                                line_num = int(line_match.group(1)) if line_match else None
                                with open(yaml_path, 'r') as f:
                                    file_lines = f.readlines()
                                if line_num is not None and 1 <= line_num <= len(file_lines):
                                    start = max(1, line_num - 3)
                                    end = min(len(file_lines), line_num + 3)
                                    snippet = ''.join(file_lines[start-1:end])
                                    excerpt = f"\nHere is a code excerpt around the error (lines {start}-{end}):\n" + snippet
                            except Exception:
                                pass

                            feedback = (
                                "Validation failed for the YAML you produced. Please fix the issues and try again.\n"
                                f"Error details: {error_msg}{excerpt}\n\n"
                                "Instructions:\n"
                                "1) Use read_file to inspect the YAML.\n"
                                "2) Apply targeted edits with edit_file.\n"
                                "3) Optionally call check_yaml_syntax to verify syntax before stopping.\n"
                                "4) When confident, call stop_procedure again to re-run validation.\n"
                            )
                            # Feed back as a human message to continue the loop
                            messages.append(HumanMessage(content=feedback))
                            stop_called = False

            # Max iterations reached without stop
            logger.error(f"Max iterations ({max_iterations}) reached without stop_procedure call")
            return False

        except Exception as e:
            logger.error(f"Error in LLM editing: {e}", exc_info=True)
            return False

    async def _validate_yaml(self, yaml_path: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate YAML by checking syntax and running predictions.

        Args:
            yaml_path: Path to YAML file to validate
            context: Procedure context with evaluation results

        Returns:
            Dict with success status and optional error message
        """
        try:
            # 1. Check YAML syntax
            logger.info("Validating YAML syntax")
            with open(yaml_path, 'r') as f:
                yaml_content = f.read()

            try:
                yaml.safe_load(yaml_content)
                logger.info("✓ YAML syntax is valid")
            except yaml.YAMLError as e:
                return {
                    "success": False,
                    "error": f"Invalid YAML syntax: {e}"
                }

            # 2. Run predictions on sample items (iterative check)
            logger.info("Running predictions on sample items")

            # Get sample items from evaluation results
            evaluation_results = context.get('evaluation_results', '')

            # Extract a few item IDs from evaluation results
            # For now, use a simple approach - get from context if available
            test_item_ids = []

            # Try to get item IDs from evaluation data
            if evaluation_results:
                try:
                    import json
                    eval_data = json.loads(evaluation_results) if isinstance(evaluation_results, str) else evaluation_results

                    # Look for sample items in various places
                    if 'sample_items' in eval_data:
                        test_item_ids = eval_data['sample_items'][:3]
                    elif 'evaluation_id' in eval_data:
                        # Get items from the evaluation
                        # For now, skip this - would require additional API call
                        pass
                except:
                    pass

            # If we have test items, run predictions
            if test_item_ids:
                logger.info(f"Testing with {len(test_item_ids)} sample items")

                # Import MCP predict tool
                from MCP.tools.prediction.predictions import register_prediction_tools
                from fastmcp import FastMCP

                # Create temporary MCP instance to get predict function
                temp_mcp = FastMCP("temp")
                register_prediction_tools(temp_mcp)

                # Get the predict function
                predict_fn = None
                for tool in temp_mcp.list_tools():
                    if tool.name == 'plexus_predict':
                        predict_fn = tool.fn
                        break

                if predict_fn:
                    prediction_errors: List[str] = []
                    for item_id in test_item_ids:
                        try:
                            result = await predict_fn(
                                scorecard_name=context['scorecard_name'],
                                score_name=context['score_name'],
                                item_id=item_id,
                                yaml_path=yaml_path  # Use our new parameter!
                            )

                            # Check for errors
                            if isinstance(result, str) and result.startswith("Error"):
                                prediction_errors.append(f"{item_id}: {result}")
                            elif isinstance(result, dict) and not result.get('success', True):
                                prediction_errors.append(f"{item_id}: {result.get('error', 'Unknown error')}")
                            else:
                                logger.info(f"✓ Prediction succeeded for item {item_id}")

                        except Exception as e:
                            prediction_errors.append(f"{item_id}: {e}")

                    if prediction_errors:
                        return {
                            "success": False,
                            "error": "One or more predictions failed: " + "; ".join(prediction_errors)
                        }
                else:
                    logger.warning("Could not find plexus_predict function for validation")
            else:
                logger.info("No test items available, skipping prediction validation")

            return {"success": True}

        except Exception as e:
            logger.error(f"Error validating YAML: {e}", exc_info=True)
            return {
                "success": False,
                "error": f"Validation error: {e}"
            }

    def _attempt_yaml_autofix(self, yaml_path: str) -> bool:
        """
        Attempt minimal YAML auto-fixes for common issues:
        - Ensure document has a single top-level mapping
        - Remove trailing BOM or non-printable characters
        - Normalize indentation and line endings

        Returns True if a change was made that might fix syntax; False otherwise.
        """
        try:
            with open(yaml_path, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()

            original_content = content

            # Strip BOM
            if content.startswith('\ufeff'):
                content = content.lstrip('\ufeff')

            # Normalize Windows newlines to Unix
            content = content.replace('\r\n', '\n').replace('\r', '\n')

            # Trim leading/trailing whitespace-only lines
            lines = content.split('\n')
            # Drop completely empty lines at start and end which can confuse block mappings
            while lines and lines[0].strip() == '':
                lines.pop(0)
            while lines and lines[-1].strip() == '':
                lines.pop()
            content = '\n'.join(lines) + ('\n' if lines else '')

            if content != original_content:
                with open(yaml_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                return True

            return False
        except Exception as e:
            logger.warning(f"YAML auto-fix attempt failed: {e}")
            return False

    async def _push_new_version(
        self,
        yaml_path: str,
        parent_version_id: str,
        context: Dict[str, Any],
        hypothesis_node
    ) -> Optional[str]:
        """
        Push edited YAML to a new ScoreVersion.

        Args:
            yaml_path: Path to edited YAML file
            parent_version_id: ID of parent ScoreVersion
            context: Procedure context with scorecard/score info
            hypothesis_node: GraphNode with hypothesis (for version note)

        Returns:
            ID of new ScoreVersion, or None on failure
        """
        try:
            from plexus.dashboard.api.models.score import Score

            # Read YAML content
            with open(yaml_path, 'r') as f:
                yaml_content = f.read()

            # Extract hypothesis for version note
            hypothesis_text = "Hypothesis implementation"
            if hypothesis_node.metadata:
                import json
                try:
                    metadata = json.loads(hypothesis_node.metadata) if isinstance(hypothesis_node.metadata, str) else hypothesis_node.metadata
                    hypothesis_text = metadata.get('hypothesis', hypothesis_text)[:200]  # Truncate for version note
                except:
                    pass

            # Get the Score object
            score = Score.get_by_id(context['score_id'], self.client)

            # Create new version directly from code content
            result = score.create_version_from_code(
                code_content=yaml_content,
                note=f"Test phase: {hypothesis_text}"
            )

            if result.get('success') and result.get('version_id'):
                new_version_id = result['version_id']
                logger.info(f"✓ Created new ScoreVersion: {new_version_id}")
                return new_version_id
            else:
                error_msg = result.get('message', 'Unknown error')
                logger.error(f"Failed to create new version: {error_msg}")
                return None

        except Exception as e:
            logger.error(f"Error pushing new version: {e}", exc_info=True)
            return None

    async def _update_node_metadata(self, node_id: str, score_version_id: str, parent_version_id: Optional[str] = None) -> bool:
        """
        Update GraphNode metadata with scoreVersionId, parent_version_id, and code_diff.

        Args:
            node_id: ID of GraphNode to update
            score_version_id: ID of ScoreVersion to store in metadata
            parent_version_id: Optional ID of the baseline/parent version used for comparison

        Returns:
            True if successful, False otherwise
        """
        try:
            from plexus.dashboard.api.models.graph_node import GraphNode
            import json
            import difflib

            # Get node
            node = GraphNode.get_by_id(node_id, self.client)

            # Parse existing metadata
            metadata = {}
            if node.metadata:
                try:
                    metadata = json.loads(node.metadata) if isinstance(node.metadata, str) else node.metadata
                except:
                    pass

            # Add scoreVersionId and parent_version_id
            metadata['scoreVersionId'] = score_version_id
            if parent_version_id:
                metadata['parent_version_id'] = parent_version_id

            # Generate code diff if we have both parent and new version
            if parent_version_id:
                try:
                    logger.info(f"Generating code diff between parent {parent_version_id} and new {score_version_id}")

                    # Fetch parent version code
                    parent_query = f"""
                    query GetScoreVersionCode {{
                        getScoreVersion(id: "{parent_version_id}") {{
                            id
                            configuration
                        }}
                    }}
                    """
                    parent_result = self.client.execute(parent_query)
                    parent_code = parent_result.get('getScoreVersion', {}).get('configuration', '')

                    # Fetch new version code
                    new_query = f"""
                    query GetScoreVersionCode {{
                        getScoreVersion(id: "{score_version_id}") {{
                            id
                            configuration
                        }}
                    }}
                    """
                    new_result = self.client.execute(new_query)
                    new_code = new_result.get('getScoreVersion', {}).get('configuration', '')

                    if parent_code and new_code:
                        # Generate unified diff
                        parent_lines = parent_code.splitlines(keepends=True)
                        new_lines = new_code.splitlines(keepends=True)

                        diff = difflib.unified_diff(
                            parent_lines,
                            new_lines,
                            fromfile=f'version_{parent_version_id[:8]}',
                            tofile=f'version_{score_version_id[:8]}',
                            lineterm=''
                        )

                        diff_text = ''.join(diff)

                        if diff_text:
                            metadata['code_diff'] = diff_text
                            logger.info(f"✓ Generated code diff ({len(diff_text)} chars)")
                        else:
                            logger.warning("No differences found between versions")
                    else:
                        logger.warning(f"Could not fetch code for diff generation (parent: {bool(parent_code)}, new: {bool(new_code)})")

                except Exception as diff_error:
                    logger.error(f"Error generating code diff: {diff_error}", exc_info=True)
                    # Continue even if diff generation fails - don't block the update

            # Update node
            node.update_content(metadata=metadata)

            logger.info(f"✓ Updated node {node_id} with scoreVersionId: {score_version_id}, parent: {parent_version_id}, code_diff: {'yes' if 'code_diff' in metadata else 'no'}")
            return True

        except Exception as e:
            logger.error(f"Error updating node metadata: {e}", exc_info=True)
            return False

    def cleanup(self):
        """Clean up temporary directory."""
        if self.temp_dir and os.path.exists(self.temp_dir):
            import shutil
            try:
                shutil.rmtree(self.temp_dir)
                logger.info(f"Cleaned up temp directory: {self.temp_dir}")
            except Exception as e:
                logger.warning(f"Failed to clean up temp directory: {e}")
