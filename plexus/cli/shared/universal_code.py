"""
Universal Code generator for task outputs.

Converts command outputs to Universal Code YAML format with contextual comments
for use with AI tools, documentation, and sharing.
"""

import json
import yaml
import logging
from typing import Dict, Any, Optional
from datetime import datetime


def generate_universal_code_yaml(
    command: str,
    output_data: Any,
    task_type: str,
    task_description: Optional[str] = None,
    scorecard_name: Optional[str] = None,
    score_name: Optional[str] = None
) -> str:
    """
    Generate Universal Code YAML from command output.
    
    Args:
        command: The command that was executed
        output_data: The parsed output data (dict, list, or string)
        task_type: Type of task (e.g., "Prediction", "Evaluation", "Analysis")
        task_description: Optional description of what the task does
        scorecard_name: Optional scorecard name for context
        score_name: Optional score name for context
        
    Returns:
        str: YAML formatted Universal Code with contextual comments
    """
    
    # Create the header comment with context
    header_lines = [
        f"# {task_type} Task Output",
        "#",
        f"# This is the structured output from a {task_type.lower()} task that executed:",
        f"# Command: {command}",
        "#"
    ]
    
    if task_description:
        header_lines.extend([
            f"# Task Description: {task_description}",
            "#"
        ])
    
    if scorecard_name:
        header_lines.extend([
            f"# Scorecard: {scorecard_name}",
        ])
        
    if score_name:
        header_lines.extend([
            f"# Score: {score_name}",
        ])
    
    if scorecard_name or score_name:
        header_lines.append("#")
    
    header_lines.extend([
        f"# Generated: {datetime.now().isoformat()}",
        f"# Format: Universal Code YAML - compatible with AI tools, documentation, and sharing",
        "#",
        ""
    ])
    
    # Parse the output data if it's a JSON string
    if isinstance(output_data, str):
        try:
            parsed_data = json.loads(output_data)
        except json.JSONDecodeError:
            # If it's not JSON, treat as plain text
            parsed_data = {"output": output_data}
    else:
        parsed_data = output_data
    
    # Add metadata about the task
    yaml_data = {
        "task_info": {
            "command": command,
            "type": task_type,
            "generated_at": datetime.now().isoformat(),
            "format": "Universal Code YAML"
        }
    }
    
    if task_description:
        yaml_data["task_info"]["description"] = task_description
    if scorecard_name:
        yaml_data["task_info"]["scorecard"] = scorecard_name
    if score_name:
        yaml_data["task_info"]["score"] = score_name
    
    # Add the actual output data
    if isinstance(parsed_data, dict):
        yaml_data.update(parsed_data)
    elif isinstance(parsed_data, list):
        yaml_data["results"] = parsed_data
    else:
        yaml_data["output"] = parsed_data
    
    # Convert to YAML with nice formatting
    try:
        yaml_content = yaml.dump(
            yaml_data,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
            width=120,
            indent=2
        )
    except Exception as e:
        logging.error(f"Failed to generate YAML: {e}")
        # Fallback to basic YAML
        yaml_content = yaml.dump(yaml_data, default_flow_style=False)
    
    # Combine header and content
    full_content = "\n".join(header_lines) + yaml_content
    
    return full_content


def generate_prediction_universal_code(
    command: str,
    json_output: str,
    scorecard_name: Optional[str] = None,
    score_name: Optional[str] = None
) -> str:
    """
    Generate Universal Code specifically for prediction tasks.
    
    Args:
        command: The prediction command that was executed
        json_output: JSON output from the prediction
        scorecard_name: Name of the scorecard used
        score_name: Name of the score predicted
        
    Returns:
        str: Universal Code YAML for the prediction
    """
    
    try:
        prediction_data = json.loads(json_output)
    except json.JSONDecodeError:
        prediction_data = {"raw_output": json_output}
    
    task_description = (
        "Executes a prediction using Plexus scorecards and scores to analyze content. "
        "Returns structured predictions with values, explanations, costs, and trace information."
    )
    
    return generate_universal_code_yaml(
        command=command,
        output_data=prediction_data,
        task_type="Prediction",
        task_description=task_description,
        scorecard_name=scorecard_name,
        score_name=score_name
    )


def generate_evaluation_universal_code(
    command: str,
    output_data: Any,
    scorecard_name: Optional[str] = None
) -> str:
    """
    Generate Universal Code specifically for evaluation tasks.
    
    Args:
        command: The evaluation command that was executed
        output_data: Output data from the evaluation
        scorecard_name: Name of the scorecard evaluated
        
    Returns:
        str: Universal Code YAML for the evaluation
    """
    
    task_description = (
        "Executes a scorecard evaluation to measure accuracy and performance metrics. "
        "Analyzes agreement between different scoring methods and provides statistical insights."
    )
    
    return generate_universal_code_yaml(
        command=command,
        output_data=output_data,
        task_type="Evaluation",
        task_description=task_description,
        scorecard_name=scorecard_name
    )


def detect_task_type_from_command(command: str) -> str:
    """
    Detect the task type based on the command.
    
    Args:
        command: The command string
        
    Returns:
        str: The detected task type
    """
    command_lower = command.lower()
    
    if 'predict' in command_lower:
        return "Prediction"
    elif 'evaluate' in command_lower or 'evaluation' in command_lower:
        return "Evaluation"
    elif 'analyze' in command_lower or 'analysis' in command_lower:
        return "Analysis"
    elif 'train' in command_lower or 'training' in command_lower:
        return "Training"
    elif 'batch' in command_lower:
        return "Batch Processing"
    else:
        return "Command Execution"


def extract_scorecard_from_command(command: str) -> Optional[str]:
    """
    Extract scorecard name from command arguments.
    
    Args:
        command: The command string
        
    Returns:
        Optional[str]: The scorecard name if found
    """
    import re
    
    # Look for --scorecard "name" or --scorecard name patterns
    patterns = [
        r'--scorecard\s+"([^"]+)"',
        r'--scorecard\s+([^\s]+)',
        r'--scorecard-name\s+"([^"]+)"',
        r'--scorecard-name\s+([^\s]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, command)
        if match:
            return match.group(1)
    
    return None


def extract_score_from_command(command: str) -> Optional[str]:
    """
    Extract score name from command arguments.
    
    Args:
        command: The command string
        
    Returns:
        Optional[str]: The score name if found
    """
    import re
    
    # Look for --score "name" or --score name patterns
    patterns = [
        r'--score\s+"([^"]+)"',
        r'--score\s+([^\s]+)',
        r'--scores\s+"([^"]+)"',
        r'--scores\s+([^\s]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, command)
        if match:
            return match.group(1)
    
    return None