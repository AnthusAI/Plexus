"""
Interactive parameter collection for CLI report execution.

This module provides functions to prompt users for report parameters
when running reports from the command line.
"""

import click
from typing import Dict, Any, List, Optional
from rich.console import Console
from rich.prompt import Prompt, Confirm
from plexus.reports.parameter_utils import (
    extract_parameters_from_config,
    validate_parameter_value,
    normalize_parameter_value
)

console = Console()


def collect_parameters_interactively(
    configuration: str,
    provided_params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Collect parameter values interactively from the user.
    
    Prompts for any parameters that weren't provided via CLI options.
    
    Args:
        configuration: The report configuration string
        provided_params: Dictionary of parameters already provided via CLI options
        
    Returns:
        Complete dictionary of parameter name -> value mappings
    """
    provided_params = provided_params or {}
    param_defs, _ = extract_parameters_from_config(configuration)
    
    if not param_defs:
        return {}
    
    console.print("\n[bold cyan]Report Parameters[/bold cyan]")
    console.print("Please provide values for the following parameters:\n")
    
    collected_params = {}
    
    for param_def in param_defs:
        param_name = param_def.get('name')
        if not param_name:
            continue
        
        # Skip if already provided
        if param_name in provided_params:
            value = provided_params[param_name]
            collected_params[param_name] = value
            console.print(f"[dim]✓ {param_def.get('label', param_name)}: {value} (provided)[/dim]")
            continue
        
        # Prompt for value
        value = prompt_for_parameter(param_def)
        
        if value is not None:
            collected_params[param_name] = value
    
    console.print()  # Empty line
    return collected_params


def prompt_for_parameter(param_def: Dict[str, Any]) -> Any:
    """
    Prompt user for a single parameter value.
    
    Args:
        param_def: Parameter definition dict
        
    Returns:
        The collected value (appropriate type)
    """
    param_name = param_def.get('name')
    param_type = param_def.get('type', 'text')
    param_label = param_def.get('label', param_name)
    param_description = param_def.get('description', '')
    required = param_def.get('required', False)
    default = param_def.get('default')
    
    # Show description if available
    if param_description:
        console.print(f"[dim]{param_description}[/dim]")
    
    # Type-specific prompting
    if param_type == 'boolean':
        return prompt_boolean(param_label, required, default)
    
    elif param_type == 'number':
        return prompt_number(param_label, param_def, required, default)
    
    elif param_type == 'select':
        return prompt_select(param_label, param_def, required, default)
    
    elif param_type in ('scorecard_select', 'score_select', 'score_version_select'):
        # These would need API calls - for now, just collect as text/ID
        console.print(f"[yellow]Note: '{param_type}' requires manual entry in CLI mode[/yellow]")
        return prompt_text(param_label, required, default)
    
    else:  # text, date, etc.
        return prompt_text(param_label, required, default)


def prompt_text(label: str, required: bool = False, default: Any = None) -> Optional[str]:
    """Prompt for text input."""
    prompt_text = f"{label}"
    if not required and default:
        prompt_text += f" [{default}]"
    elif not required:
        prompt_text += " (optional)"
    
    while True:
        value = Prompt.ask(prompt_text, default=str(default) if default else "")
        
        if not value and not required:
            return None
        elif not value and required:
            console.print("[red]This parameter is required[/red]")
            continue
        else:
            return value


def prompt_boolean(label: str, required: bool = False, default: Any = None) -> bool:
    """Prompt for boolean input (Y/n)."""
    default_bool = True if default is True else (False if default is False else None)
    
    prompt_text = f"{label}"
    if default_bool is not None:
        suffix = " (Y/n)" if default_bool else " (y/N)"
        prompt_text += suffix
    else:
        prompt_text += " (y/n)"
    
    return Confirm.ask(prompt_text, default=default_bool)


def prompt_number(label: str, param_def: Dict[str, Any], required: bool = False, default: Any = None) -> Optional[float]:
    """Prompt for number input with validation."""
    min_val = param_def.get('min')
    max_val = param_def.get('max')
    
    prompt_text = f"{label}"
    if min_val is not None and max_val is not None:
        prompt_text += f" ({min_val}-{max_val})"
    elif min_val is not None:
        prompt_text += f" (min: {min_val})"
    elif max_val is not None:
        prompt_text += f" (max: {max_val})"
    
    if not required and default is not None:
        prompt_text += f" [{default}]"
    elif not required:
        prompt_text += " (optional)"
    
    while True:
        value_str = Prompt.ask(prompt_text, default=str(default) if default is not None else "")
        
        if not value_str and not required:
            return None
        
        try:
            value = float(value_str)
            
            # Validate
            is_valid, error = validate_parameter_value(param_def, value)
            if not is_valid:
                console.print(f"[red]{error}[/red]")
                continue
            
            # Return as int if it's a whole number
            return int(value) if value.is_integer() else value
            
        except ValueError:
            console.print("[red]Please enter a valid number[/red]")
            continue


def prompt_select(label: str, param_def: Dict[str, Any], required: bool = False, default: Any = None) -> Optional[str]:
    """Prompt for select input with options."""
    options = param_def.get('options', [])
    
    if not options:
        # No options defined, fall back to text
        return prompt_text(label, required, default)
    
    # Format options for display
    console.print(f"\n{label}:")
    for i, option in enumerate(options, 1):
        if isinstance(option, dict):
            opt_label = option.get('label', option.get('value', ''))
            opt_value = option.get('value', '')
            console.print(f"  {i}. {opt_label}")
        else:
            console.print(f"  {i}. {option}")
    
    # Prompt for selection
    while True:
        choice_str = Prompt.ask(
            "Select option number" + (" (optional)" if not required else ""),
            default=str(default) if default else ""
        )
        
        if not choice_str and not required:
            return None
        
        try:
            choice_num = int(choice_str)
            if 1 <= choice_num <= len(options):
                selected = options[choice_num - 1]
                if isinstance(selected, dict):
                    return selected.get('value')
                else:
                    return str(selected)
            else:
                console.print(f"[red]Please enter a number between 1 and {len(options)}[/red]")
        except ValueError:
            console.print("[red]Please enter a valid number[/red]")


def parse_cli_parameter_options(ctx_params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract --param-* options from click context parameters.
    
    Args:
        ctx_params: Dictionary of all CLI parameters (from click.Context.params)
        
    Returns:
        Dictionary of parameter name -> value for parameters that were provided
    """
    param_values = {}
    
    # Look for keys starting with 'param_'
    for key, value in ctx_params.items():
        if key.startswith('param_') and value is not None:
            # Remove 'param_' prefix to get actual parameter name
            param_name = key[6:]  # len('param_') = 6
            param_values[param_name] = value
    
    return param_values


def display_collected_parameters(parameters: Dict[str, Any]):
    """
    Display collected parameters in a formatted table.
    
    Args:
        parameters: Dictionary of parameter name -> value
    """
    if not parameters:
        return
    
    console.print("\n[bold]Running report with parameters:[/bold]")
    for name, value in parameters.items():
        console.print(f"  [cyan]{name}[/cyan]: {value}")
    console.print()

