"""
YAML Parameter Parser for Procedures

Extracts configurable parameter values from procedure YAML code.
This allows procedures to have dynamic parameters (like scorecard_id, score_id, score_version_id)
that are stored within the YAML code rather than as fixed fields on the Procedure model.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


@dataclass
class ParameterDefinition:
    """Definition of a configurable parameter from YAML."""

    name: str
    type: str
    label: str
    input: Optional[str] = None
    required: bool = False
    default: Optional[Any] = None
    options: Optional[List[str]] = None
    rows: Optional[int] = None


class ProcedureParameterParser:
    """
    Parses configurable parameters from procedure YAML code.

    Supports both the legacy list-based parameter formats and the Tactus
    `params:` mapping format.
    """

    @staticmethod
    def _humanize_label(name: str) -> str:
        return name.replace("_", " ").replace("-", " ").title()

    @staticmethod
    def parse_parameter_definitions(yaml_code: str) -> List[ParameterDefinition]:
        """
        Extract parameter definitions from YAML code.

        Args:
            yaml_code: The procedure YAML configuration

        Returns:
            List of ParameterDefinition objects
        """
        try:
            yaml_data = yaml.safe_load(yaml_code)
            if not yaml_data or not isinstance(yaml_data, dict):
                logger.warning("Invalid YAML structure for parameter parsing")
                return []

            params_config = yaml_data.get("params")
            if isinstance(params_config, dict):
                parameters: List[ParameterDefinition] = []
                for param_name, param_config in params_config.items():
                    if not isinstance(param_config, dict):
                        logger.warning(
                            "Invalid params definition for '%s': %s",
                            param_name,
                            param_config,
                        )
                        continue

                    parameters.append(
                        ParameterDefinition(
                            name=param_name,
                            type=param_config.get("type", "string"),
                            label=param_config.get(
                                "label", ProcedureParameterParser._humanize_label(param_name)
                            ),
                            input=param_config.get("input"),
                            required=param_config.get("required", False),
                            default=param_config.get("default"),
                            options=param_config.get("options") or param_config.get("enum"),
                            rows=param_config.get("rows"),
                        )
                    )

                logger.debug("Parsed %s params definitions from YAML", len(parameters))
                return parameters

            param_configs = yaml_data.get("configurable_parameters") or yaml_data.get(
                "parameters", []
            )
            if not param_configs:
                logger.debug("No params/configurable_parameters/parameters found in YAML")
                return []

            parameters = []
            for param_config in param_configs:
                if not isinstance(param_config, dict):
                    logger.warning("Invalid parameter configuration: %s", param_config)
                    continue

                param_name = param_config.get("name", "")
                param = ParameterDefinition(
                    name=param_name,
                    type=param_config.get("type", "string"),
                    label=param_config.get(
                        "label", ProcedureParameterParser._humanize_label(param_name)
                    ),
                    input=param_config.get("input"),
                    required=param_config.get("required", False),
                    default=param_config.get("default"),
                    options=param_config.get("options"),
                    rows=param_config.get("rows"),
                )

                if param.name:
                    parameters.append(param)
                else:
                    logger.warning("Parameter missing name: %s", param_config)

            logger.debug("Parsed %s parameter definitions from YAML", len(parameters))
            return parameters

        except yaml.YAMLError as exc:
            logger.error("YAML parsing error: %s", exc)
            return []
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Unexpected error parsing parameter definitions: %s", exc)
            return []

    @staticmethod
    def extract_parameter_values(yaml_code: str) -> Dict[str, Any]:
        """
        Extract actual parameter values from YAML code.

        Args:
            yaml_code: The procedure YAML configuration with values injected

        Returns:
            Dictionary mapping parameter names to their current values
        """
        values: Dict[str, Any] = {}

        try:
            yaml_data = yaml.safe_load(yaml_code)
            if not yaml_data or not isinstance(yaml_data, dict):
                return values

            params_config = yaml_data.get("params")
            if isinstance(params_config, dict):
                for param_name, param_def in params_config.items():
                    if not isinstance(param_def, dict):
                        continue
                    if "value" in param_def and param_def["value"] is not None:
                        values[param_name] = param_def["value"]
                    elif "default" in param_def and param_def["default"] is not None:
                        values[param_name] = param_def["default"]

            param_list = yaml_data.get("parameters") or yaml_data.get(
                "configurable_parameters", []
            )
            if param_list and isinstance(param_list, list):
                for param_obj in param_list:
                    if (
                        isinstance(param_obj, dict)
                        and "name" in param_obj
                        and "value" in param_obj
                    ):
                        param_name = param_obj["name"]
                        param_value = param_obj["value"]
                        if param_value is not None:
                            values[param_name] = param_value
                            logger.debug(
                                "Found value for parameter '%s': %s",
                                param_name,
                                param_value,
                            )

            if not values:
                parameters = ProcedureParameterParser.parse_parameter_definitions(yaml_code)
                for param in parameters:
                    value = ProcedureParameterParser._find_parameter_value_in_yaml(
                        yaml_data, param.name
                    )
                    if value is not None:
                        values[param.name] = value
                        logger.debug(
                            "Found value for parameter '%s': %s", param.name, value
                        )

            return values

        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Error extracting parameter values: %s", exc)
            return values

    @staticmethod
    def _find_parameter_value_in_yaml(
        data: Any, param_name: str, depth: int = 0
    ) -> Optional[Any]:
        """
        Recursively search YAML data structure for a parameter value.

        Args:
            data: YAML data structure to search
            param_name: Name of the parameter to find
            depth: Current recursion depth (safety limit)

        Returns:
            The parameter value if found, None otherwise
        """
        if depth > 10:
            return None

        if isinstance(data, dict):
            for key, value in data.items():
                if key == param_name:
                    return value

                result = ProcedureParameterParser._find_parameter_value_in_yaml(
                    value, param_name, depth + 1
                )
                if result is not None:
                    return result

        elif isinstance(data, list):
            for item in data:
                result = ProcedureParameterParser._find_parameter_value_in_yaml(
                    item, param_name, depth + 1
                )
                if result is not None:
                    return result

        return None

    @staticmethod
    def get_required_parameters(yaml_code: str) -> Dict[str, ParameterDefinition]:
        """
        Get all required parameters that must have values.

        Args:
            yaml_code: The procedure YAML configuration

        Returns:
            Dictionary mapping parameter names to their definitions (required only)
        """
        parameters = ProcedureParameterParser.parse_parameter_definitions(yaml_code)
        return {param.name: param for param in parameters if param.required}

    @staticmethod
    def validate_parameter_values(
        yaml_code: str, provided_values: Optional[Dict[str, Any]] = None
    ) -> tuple[bool, List[str]]:
        """
        Validate that all required parameters have values.

        Args:
            yaml_code: The procedure YAML configuration
            provided_values: Optional dict of externally provided values to check

        Returns:
            Tuple of (is_valid, list_of_missing_parameters)
        """
        required_params = ProcedureParameterParser.get_required_parameters(yaml_code)

        if provided_values is None:
            provided_values = ProcedureParameterParser.extract_parameter_values(yaml_code)

        missing: List[str] = []
        for param_name, param_def in required_params.items():
            value = provided_values.get(param_name)
            if value is None or (isinstance(value, str) and not value.strip()):
                missing.append(param_name)
                logger.warning(
                    "Required parameter '%s' (%s) is missing or empty",
                    param_name,
                    param_def.label,
                )

        is_valid = len(missing) == 0
        return is_valid, missing
