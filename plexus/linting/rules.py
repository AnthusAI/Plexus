"""
Domain-specific validation rules for YAML DSL linter.

Provides a flexible rule engine for implementing custom validation logic.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from dataclasses import dataclass

if TYPE_CHECKING:
    from .yaml_linter import LintMessage


@dataclass
class ValidationRule(ABC):
    """Abstract base class for validation rules."""
    
    rule_id: str
    description: str
    severity: str = 'error'  # 'error', 'warning', 'info'
    
    @abstractmethod
    def validate(self, data: Dict[str, Any]) -> List['LintMessage']:
        """
        Validate the data against this rule.
        
        Args:
            data: Parsed YAML data to validate
            
        Returns:
            List of LintMessage objects for any violations
        """
        pass


class RuleEngine:
    """Engine for running validation rules against YAML data."""
    
    def __init__(self, rules: List[ValidationRule]):
        """
        Initialize the rule engine.
        
        Args:
            rules: List of validation rules to apply
        """
        self.rules = rules
    
    def validate(self, data: Dict[str, Any]) -> List['LintMessage']:
        """
        Run all rules against the provided data.
        
        Args:
            data: Parsed YAML data to validate
            
        Returns:
            List of all LintMessage objects from rule violations
        """
        # Import here to avoid circular imports
        from .yaml_linter import LintMessage
        
        messages = []
        
        for rule in self.rules:
            try:
                rule_messages = rule.validate(data)
                messages.extend(rule_messages)
            except Exception as e:
                # If a rule fails, generate an error message
                messages.append(LintMessage(
                    level='error',
                    code='RULE_ENGINE_ERROR',
                    title='Rule Validation Error',
                    message=f"Error running rule '{rule.rule_id}': {str(e)}",
                    suggestion="Please check the rule configuration or report this as a bug.",
                    context={'rule_id': rule.rule_id, 'error': str(e)}
                ))
        
        return messages


# Example domain-specific rules

class RequiredFieldRule(ValidationRule):
    """Rule that validates required fields exist."""
    
    def __init__(self, field_path: str, rule_id: Optional[str] = None):
        """
        Initialize the required field rule.
        
        Args:
            field_path: Dot-separated path to the required field (e.g., 'config.name')
            rule_id: Optional custom rule ID
        """
        self.field_path = field_path
        super().__init__(
            rule_id=rule_id or f"REQUIRED_FIELD_{field_path.upper().replace('.', '_')}",
            description=f"Field '{field_path}' is required",
            severity='error'
        )
    
    def validate(self, data: Dict[str, Any]) -> List['LintMessage']:
        from .yaml_linter import LintMessage
        
        messages = []
        
        # Navigate to the field using dot notation
        current = data
        path_parts = self.field_path.split('.')
        
        try:
            for part in path_parts[:-1]:
                if not isinstance(current, dict) or part not in current:
                    raise KeyError(f"Path not found: {part}")
                current = current[part]
            
            # Check if the final field exists
            final_field = path_parts[-1]
            if not isinstance(current, dict) or final_field not in current:
                messages.append(LintMessage(
                    level=self.severity,
                    code=self.rule_id,
                    title='Required Field Missing',
                    message=f"Required field '{self.field_path}' is missing.",
                    suggestion=f"Please add the '{self.field_path}' field to your configuration.",
                    doc_url="https://docs.plexus.ai/yaml-dsl/required-fields",
                    context={'field_path': self.field_path}
                ))
            elif current[final_field] is None or current[final_field] == '':
                messages.append(LintMessage(
                    level=self.severity,
                    code=self.rule_id,
                    title='Required Field Empty',
                    message=f"Required field '{self.field_path}' is empty.",
                    suggestion=f"Please provide a value for the '{self.field_path}' field.",
                    doc_url="https://docs.plexus.ai/yaml-dsl/required-fields",
                    context={'field_path': self.field_path}
                ))
                
        except (KeyError, TypeError):
            messages.append(LintMessage(
                level=self.severity,
                code=self.rule_id,
                title='Required Field Missing',
                message=f"Required field '{self.field_path}' is missing.",
                suggestion=f"Please add the '{self.field_path}' field to your configuration.",
                doc_url="https://docs.plexus.ai/yaml-dsl/required-fields",
                context={'field_path': self.field_path}
            ))
        
        return messages


class AllowedValuesRule(ValidationRule):
    """Rule that validates field values are from allowed set."""
    
    def __init__(self, field_path: str, allowed_values: List[Any], rule_id: Optional[str] = None):
        """
        Initialize the allowed values rule.
        
        Args:
            field_path: Dot-separated path to the field
            allowed_values: List of allowed values
            rule_id: Optional custom rule ID
        """
        self.field_path = field_path
        self.allowed_values = allowed_values
        super().__init__(
            rule_id=rule_id or f"ALLOWED_VALUES_{field_path.upper().replace('.', '_')}",
            description=f"Field '{field_path}' must be one of: {allowed_values}",
            severity='error'
        )
    
    def validate(self, data: Dict[str, Any]) -> List['LintMessage']:
        from .yaml_linter import LintMessage
        
        messages = []
        
        # Navigate to the field
        current = data
        path_parts = self.field_path.split('.')
        
        try:
            for part in path_parts:
                if not isinstance(current, dict) or part not in current:
                    # Field doesn't exist - not our concern
                    return messages
                current = current[part]
            
            # Check if value is allowed
            if current not in self.allowed_values:
                messages.append(LintMessage(
                    level=self.severity,
                    code=self.rule_id,
                    title='Invalid Field Value',
                    message=f"Field '{self.field_path}' has invalid value '{current}'.",
                    suggestion=f"Please use one of the allowed values: {', '.join(map(str, self.allowed_values))}",
                    doc_url="https://docs.plexus.ai/yaml-dsl/field-values",
                    context={
                        'field_path': self.field_path,
                        'current_value': current,
                        'allowed_values': self.allowed_values
                    }
                ))
                
        except (KeyError, TypeError):
            # Field path is invalid - not our concern
            pass
        
        return messages


class TypeValidationRule(ValidationRule):
    """Rule that validates field types."""
    
    def __init__(self, field_path: str, expected_type: type, rule_id: Optional[str] = None):
        """
        Initialize the type validation rule.
        
        Args:
            field_path: Dot-separated path to the field
            expected_type: Expected Python type
            rule_id: Optional custom rule ID
        """
        self.field_path = field_path
        self.expected_type = expected_type
        super().__init__(
            rule_id=rule_id or f"TYPE_VALIDATION_{field_path.upper().replace('.', '_')}",
            description=f"Field '{field_path}' must be of type {expected_type.__name__}",
            severity='error'
        )
    
    def validate(self, data: Dict[str, Any]) -> List['LintMessage']:
        from .yaml_linter import LintMessage
        
        messages = []
        
        # Navigate to the field
        current = data
        path_parts = self.field_path.split('.')
        
        try:
            for part in path_parts:
                if not isinstance(current, dict) or part not in current:
                    # Field doesn't exist - not our concern
                    return messages
                current = current[part]
            
            # Check type
            if not isinstance(current, self.expected_type):
                messages.append(LintMessage(
                    level=self.severity,
                    code=self.rule_id,
                    title='Invalid Field Type',
                    message=f"Field '{self.field_path}' should be {self.expected_type.__name__}, but got {type(current).__name__}.",
                    suggestion=f"Please ensure '{self.field_path}' is a {self.expected_type.__name__}.",
                    doc_url="https://docs.plexus.ai/yaml-dsl/data-types",
                    context={
                        'field_path': self.field_path,
                        'expected_type': self.expected_type.__name__,
                        'actual_type': type(current).__name__
                    }
                ))

        except (KeyError, TypeError):
            # Field path is invalid - not our concern
            pass

        return messages


class ConfidenceConfigurationRule(ValidationRule):
    """Rule that validates confidence configuration requirements."""

    def __init__(self):
        super().__init__(
            rule_id="CONFIDENCE_REQUIRES_PARSE_FROM_START",
            description="enable_confidence requires parse_from_start: true",
            severity='error'
        )

    def validate(self, data: Dict[str, Any]) -> List['LintMessage']:
        from .yaml_linter import LintMessage

        messages = []

        # Check if data has scores configuration
        scores = data.get('scores', [])
        if not isinstance(scores, list):
            return messages

        # Check each score
        for i, score in enumerate(scores):
            if not isinstance(score, dict):
                continue

            # Check if score has a graph with nodes
            graph = score.get('graph', [])
            if not isinstance(graph, list):
                continue

            # Check each node in the graph
            for j, node in enumerate(graph):
                if not isinstance(node, dict):
                    continue

                # Check if this is a Classifier node with enable_confidence
                node_class = node.get('class', '')
                enable_confidence = node.get('enable_confidence', False)
                parse_from_start = node.get('parse_from_start', False)

                if (node_class == 'Classifier' and
                    enable_confidence and
                    not parse_from_start):

                    node_name = node.get('name', f'node_{j}')
                    messages.append(LintMessage(
                        level=self.severity,
                        code=self.rule_id,
                        title='Invalid Confidence Configuration',
                        message=f"Node '{node_name}' has 'enable_confidence: true' but 'parse_from_start' is not true.",
                        suggestion="Set 'parse_from_start: true' when using 'enable_confidence: true' for Classifier nodes.",
                        doc_url="https://docs.plexus.ai/yaml-dsl/confidence-scoring",
                        context={
                            'score_index': i,
                            'node_index': j,
                            'node_name': node_name,
                            'node_class': node_class
                        }
                    ))

        return messages


class ProcessorValidationRule(ValidationRule):
    """Rule that validates item.processors entries reference known classes with required parameters."""

    # Map of processor class name → list of required-parameter groups.
    # Each group is a set of param names; at least one member must be present.
    # Empty list = no required params.
    _KNOWN_PROCESSORS = {
        "RelevantWindowsTranscriptFilter": [{"keywords", "classifier"}],
        "FilterCustomerOnlyProcessor": [],
        "RemoveSpeakerIdentifiersTranscriptFilter": [],
        "AddUnknownSpeakerIdentifiersTranscriptFilter": [],
        "AddEnumeratedSpeakerIdentifiersTranscriptFilter": [],
        "RemoveStopWordsTranscriptFilter": [],
        "ExpandContractionsProcessor": [],
        "DeepgramFormatProcessor": [],
        "DeepgramTimeSliceProcessor": [],
    }

    # Hand-written fix examples for required-param errors (keyed by class name).
    # These are shown verbatim in the suggestion so the agent can copy-paste.
    _FIX_EXAMPLES = {
        "RelevantWindowsTranscriptFilter": (
            "  - class: RelevantWindowsTranscriptFilter\n"
            "    parameters:\n"
            '      keywords: ["keyword1", "keyword2"]   # REQUIRED\n'
            "      fuzzy_match: true                     # optional\n"
            "      fuzzy_threshold: 80                   # optional, 0-100\n"
            "      prev_count: 1                         # optional, sentences before match\n"
            "      next_count: 1                         # optional, sentences after match"
        ),
    }

    def __init__(self):
        super().__init__(
            rule_id="PROCESSOR_VALIDATION",
            description="item.processors entries must reference known classes with valid parameters",
            severity='error'
        )

    def validate(self, data: Dict[str, Any]) -> List['LintMessage']:
        from .yaml_linter import LintMessage

        messages = []

        item = data.get("item", {})
        if not isinstance(item, dict):
            return messages

        processors = item.get("processors")
        if not processors:
            return messages

        if not isinstance(processors, list):
            messages.append(LintMessage(
                level='error',
                code='PROCESSOR_NOT_A_LIST',
                title='processors must be a list',
                message="item.processors must be a YAML list (sequence of mappings).",
                suggestion="Use:\n  item:\n    processors:\n      - class: FilterCustomerOnlyProcessor",
            ))
            return messages

        known = self._KNOWN_PROCESSORS

        for i, entry in enumerate(processors):
            if not isinstance(entry, dict):
                continue

            class_name = entry.get("class")
            if not class_name:
                messages.append(LintMessage(
                    level='error',
                    code='PROCESSOR_MISSING_CLASS',
                    title='Processor entry missing class',
                    message=f"item.processors[{i}] has no 'class' field.",
                    suggestion="Each processor entry must have a 'class' key naming the processor class.",
                ))
                continue

            if class_name not in known:
                messages.append(LintMessage(
                    level='error',
                    code='PROCESSOR_UNKNOWN_CLASS',
                    title='Unknown processor class',
                    message=f"'{class_name}' is not a recognised processor class.",
                    suggestion=(
                        "Available item processors:\n"
                        + "\n".join(f"  - {k}" for k in sorted(known))
                        + "\nCheck for typos or use a processor from the list above."
                    ),
                ))
                continue

            # Check required parameter groups
            params = entry.get("parameters") or {}
            if not isinstance(params, dict):
                params = {}

            required_groups = known[class_name]
            for group in required_groups:
                if not any(p in params for p in group):
                    sorted_group = sorted(group)

                    # Use a hand-written fix example if available; otherwise generate one
                    fix_example = self._FIX_EXAMPLES.get(class_name)
                    if fix_example:
                        suggestion = f"Add the required parameter. Working example:\n{fix_example}"
                    else:
                        suggestion = (
                            f"Add a 'parameters' block with one of {sorted_group}. Example:\n"
                            f"  - class: {class_name}\n"
                            f"    parameters:\n"
                            f"      {sorted_group[0]}: <value>"
                        )

                    messages.append(LintMessage(
                        level='error',
                        code='PROCESSOR_MISSING_REQUIRED_PARAM',
                        title=f"Missing required parameter for {class_name}",
                        message=(
                            f"item.processors[{i}] ({class_name}) requires at least one of: "
                            f"{', '.join(sorted_group)}."
                        ),
                        suggestion=suggestion,
                    ))

        return messages

class DeepgramInputSourcePlacementRule(ValidationRule):
    """Rule that detects item processor/input-source configuration placed in the wrong location.

    Item processors and input sources (DeepgramInputSource, processors: lists, input_source: keys,
    etc.) must live in the top-level `item:` section, NOT nested under `data:` or any other section.

    Correct structure:

        data:
          class: CallCriteriaDBCache
          searches: ...          # dataset config only — no input_source, no processors here

        item:                    # ← all item config lives here at the top level
          class: DeepgramInputSource
          options:
            pattern: ".*deepgram.*\\.json$"
          processors:
            - class: DeepgramFormatProcessor
              parameters:
                format: words
                speaker_labels: true
                include_timestamps: true

    Common mistakes:
      - Placing `input_source:` as a nested key inside `data:`
      - Placing a `processors:` list inside `data:` or any other non-`item:` section
      - Using a known processor class name (DeepgramFormatProcessor, RelevantWindowsTranscriptFilter,
        etc.) as `class:` inside `data:` or other wrong sections
    """

    # Item input-source classes (the class of the top-level `item:` section)
    _INPUT_SOURCE_CLASSES = {
        "DeepgramInputSource",
    }

    # Keys that belong exclusively in `item:`, never in `data:` or other sections
    _ITEM_ONLY_KEYS = {"processors", "input_source"}

    _CORRECT_YAML = (
        "data:\n"
        "  class: CallCriteriaDBCache\n"
        "  searches: ...    # dataset config only — no input_source or processors here\n\n"
        "item:              # ← NEW top-level section (same indent level as data:)\n"
        "  class: DeepgramInputSource\n"
        "  options:\n"
        '    pattern: ".*deepgram.*\\.json$"\n'
        "  processors:\n"
        "    - class: DeepgramFormatProcessor\n"
        "      parameters:\n"
        "        format: words          # or 'sentences' or 'paragraphs'\n"
        "        speaker_labels: true\n"
        "        include_timestamps: true"
    )

    def __init__(self):
        super().__init__(
            rule_id="ITEM_PROCESSOR_PLACEMENT",
            description=(
                "Item processors and input sources must be in the top-level `item:` section, "
                "not nested under `data:` or other sections"
            ),
            severity='error'
        )

    def _find_misplaced(self, obj, path=""):
        """Recursively find processor/input-source config placed in the wrong section.

        Returns a list of (path_str, reason) tuples describing each violation found.
        """
        violations = []
        if isinstance(obj, dict):
            cls = obj.get("class")
            # Known processor class used somewhere it shouldn't be
            known_processors = ProcessorValidationRule._KNOWN_PROCESSORS
            if cls and (cls in self._INPUT_SOURCE_CLASSES or cls in known_processors):
                violations.append((path, f"class: {cls}"))
            # `processors:` or `input_source:` key present in wrong section
            for key in self._ITEM_ONLY_KEYS:
                if key in obj:
                    violations.append((f"{path}.{key}" if path else key, f"key '{key}'"))
            # Recurse into values (but don't re-flag the same dict for its children)
            for k, v in obj.items():
                child_path = f"{path}.{k}" if path else k
                violations.extend(self._find_misplaced(v, child_path))
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                violations.extend(self._find_misplaced(v, f"{path}[{i}]"))
        return violations

    def validate(self, data: Dict[str, Any]) -> List['LintMessage']:
        from .yaml_linter import LintMessage

        messages = []

        # Scan every top-level section except `item:` itself
        for section_key, section_value in data.items():
            if section_key == "item":
                continue  # correct location — skip

            violations = self._find_misplaced(section_value, section_key)
            if not violations:
                continue

            # Emit one error per section summarising everything that was found
            found_summary = "; ".join(
                f"{reason} at {path}" for path, reason in violations[:3]
            )
            if len(violations) > 3:
                found_summary += f" (and {len(violations) - 3} more)"

            if section_key == "data":
                code = "PROCESSOR_UNDER_DATA"
                title = "Item processor/source config found in `data:` — must be in `item:`"
                message = (
                    f"Found processor/input-source configuration inside the `data:` section: "
                    f"{found_summary}. "
                    "The `data:` section defines the dataset source (e.g. CallCriteriaDBCache) "
                    "and must not contain processor classes, `processors:` lists, or "
                    "`input_source:` keys. All of that belongs in a top-level `item:` section."
                )
            else:
                code = "PROCESSOR_WRONG_SECTION"
                title = f"Item processor/source config found in `{section_key}:` — must be in `item:`"
                message = (
                    f"Found processor/input-source configuration inside the `{section_key}:` "
                    f"section: {found_summary}. "
                    "Processor classes, `processors:` lists, and `input_source:` keys all "
                    "belong in the top-level `item:` section, not in other sections."
                )

            messages.append(LintMessage(
                level='error',
                code=code,
                title=title,
                message=message,
                suggestion=f"Add a top-level `item:` block. Correct structure:\n\n{self._CORRECT_YAML}",
            ))

        return messages
