from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Iterable, Optional

from graphql import parse, print_ast
from graphql.language.ast import (
    BooleanValueNode,
    DocumentNode,
    FieldNode,
    FloatValueNode,
    FragmentDefinitionNode,
    IntValueNode,
    ListValueNode,
    NullValueNode,
    ObjectFieldNode,
    ObjectValueNode,
    OperationDefinitionNode,
    SelectionSetNode,
    StringValueNode,
    VariableNode,
)


PRIVATE_MODELS = {"Item", "ScoreResult", "FeedbackItem", "Identifier"}
PRIVATE_PLURALS = {
    "Item": "Items",
    "ScoreResult": "ScoreResults",
    "FeedbackItem": "FeedbackItems",
    "Identifier": "Identifiers",
}
CONTROL_MODELS = {
    "Account",
    "Scorecard",
    "Score",
    "ScoreVersion",
    "Evaluation",
    "Task",
    "TaskStage",
    "ScoringJob",
    "BatchJob",
    "Report",
    "ReportBlock",
    "ReportConfiguration",
    "DataSource",
    "DataSourceVersion",
    "Procedure",
    "ProcedureTemplate",
}


@dataclass(frozen=True)
class RootField:
    node: FieldNode
    name: str
    response_key: str
    classification: str
    model: Optional[str]


@dataclass(frozen=True)
class OperationPlan:
    document: DocumentNode
    operation: OperationDefinitionNode
    root_fields: tuple[RootField, ...]

    @property
    def operation_type(self) -> str:
        return self.operation.operation.value

    @property
    def private_fields(self) -> tuple[RootField, ...]:
        return tuple(field for field in self.root_fields if field.classification == "private")

    @property
    def control_fields(self) -> tuple[RootField, ...]:
        return tuple(field for field in self.root_fields if field.classification == "control")

    @property
    def blocked_fields(self) -> tuple[RootField, ...]:
        return tuple(field for field in self.root_fields if field.classification == "blocked")


def build_operation_plan(query: str, operation_name: Optional[str]) -> OperationPlan:
    document = parse(query)
    operation = _select_operation(document, operation_name)
    root_fields = tuple(_root_field(operation, node) for node in operation.selection_set.selections)
    return OperationPlan(document=document, operation=operation, root_fields=root_fields)


def build_root_only_query(plan: OperationPlan, fields: Iterable[RootField]) -> str:
    selected_names = {field.name for field in fields}
    selected_nodes = tuple(
        field.node
        for field in plan.root_fields
        if field.name in selected_names
    )
    used_variables = set()
    for node in selected_nodes:
        used_variables.update(_variable_names(node))

    operation = copy.copy(plan.operation)
    operation.variable_definitions = tuple(
        definition
        for definition in operation.variable_definitions or ()
        if definition.variable.name.value in used_variables
    )
    operation.selection_set = SelectionSetNode(selections=selected_nodes)
    fragments = tuple(
        definition
        for definition in plan.document.definitions
        if isinstance(definition, FragmentDefinitionNode)
    )
    return print_ast(DocumentNode(definitions=(operation, *fragments)))


def argument_value(field: FieldNode, name: str, variables: dict[str, Any]) -> Any:
    for argument in field.arguments or ():
        if argument.name.value == name:
            return value_from_ast(argument.value, variables)
    return None


def all_argument_values(field: FieldNode, variables: dict[str, Any]) -> dict[str, Any]:
    return {
        argument.name.value: value_from_ast(argument.value, variables)
        for argument in field.arguments or ()
    }


def value_from_ast(node: Any, variables: dict[str, Any]) -> Any:
    if isinstance(node, VariableNode):
        return variables.get(node.name.value)
    if isinstance(node, StringValueNode):
        return node.value
    if isinstance(node, IntValueNode):
        return int(node.value)
    if isinstance(node, FloatValueNode):
        return float(node.value)
    if isinstance(node, BooleanValueNode):
        return bool(node.value)
    if isinstance(node, NullValueNode):
        return None
    if isinstance(node, ListValueNode):
        return [value_from_ast(value, variables) for value in node.values]
    if isinstance(node, ObjectValueNode):
        return {
            field.name.value: value_from_ast(field.value, variables)
            for field in node.fields
            if isinstance(field, ObjectFieldNode)
        }
    return None


def project_value(value: Any, selection_set: Optional[SelectionSetNode]) -> Any:
    if value is None or selection_set is None:
        return value
    if isinstance(value, list):
        return [project_value(item, selection_set) for item in value]
    if not isinstance(value, dict):
        return value

    projected: dict[str, Any] = {}
    for selection in selection_set.selections:
        if not isinstance(selection, FieldNode):
            continue
        field_name = selection.name.value
        response_key = selection.alias.value if selection.alias else field_name
        child = value.get(field_name)
        if isinstance(child, list):
            projected[response_key] = [
                project_value(item, selection.selection_set)
                for item in child
            ]
        elif isinstance(child, dict):
            projected[response_key] = project_value(child, selection.selection_set)
        else:
            projected[response_key] = child
    return projected


def project_list_connection(
    connection: dict[str, Any],
    selection_set: Optional[SelectionSetNode],
) -> dict[str, Any]:
    if selection_set is None:
        return connection

    projected: dict[str, Any] = {}
    for selection in selection_set.selections:
        if not isinstance(selection, FieldNode):
            continue
        field_name = selection.name.value
        response_key = selection.alias.value if selection.alias else field_name
        if field_name == "items":
            projected[response_key] = [
                project_value(item, selection.selection_set)
                for item in connection.get("items", [])
            ]
        else:
            projected[response_key] = connection.get(field_name)
    return projected


def model_from_private_root(root_name: str) -> Optional[str]:
    for model in sorted(PRIVATE_MODELS, key=len, reverse=True):
        plural = PRIVATE_PLURALS[model]
        if root_name in {
            f"get{model}",
            f"create{model}",
            f"update{model}",
            f"delete{model}",
            f"list{plural}",
        }:
            return model
        if root_name.startswith(f"list{model}By"):
            return model
    return None


def is_control_read_root(root_name: str) -> bool:
    for model in sorted(CONTROL_MODELS, key=len, reverse=True):
        if root_name == f"get{model}":
            return True
        if root_name == f"list{model}s":
            return True
        if root_name.startswith(f"list{model}By"):
            return True
    return False


def _select_operation(
    document: DocumentNode,
    operation_name: Optional[str],
) -> OperationDefinitionNode:
    operations = [
        definition
        for definition in document.definitions
        if isinstance(definition, OperationDefinitionNode)
    ]
    if operation_name:
        for operation in operations:
            if operation.name and operation.name.value == operation_name:
                return operation
        raise ValueError(f"GraphQL operation '{operation_name}' was not found")
    if len(operations) != 1:
        raise ValueError("operationName is required when multiple operations are present")
    return operations[0]


def _root_field(operation: OperationDefinitionNode, node: Any) -> RootField:
    if not isinstance(node, FieldNode):
        raise ValueError("Only root GraphQL fields are supported by the prototype proxy")

    name = node.name.value
    response_key = node.alias.value if node.alias else name
    private_model = model_from_private_root(name)
    if private_model:
        return RootField(node, name, response_key, "private", private_model)

    if operation.operation.value == "query" and is_control_read_root(name):
        return RootField(node, name, response_key, "control", None)

    return RootField(node, name, response_key, "blocked", None)


def _variable_names(node: Any) -> set[str]:
    if isinstance(node, VariableNode):
        return {node.name.value}
    if isinstance(node, (str, int, float, bool)) or node is None:
        return set()
    if isinstance(node, (list, tuple)):
        names = set()
        for child in node:
            names.update(_variable_names(child))
        return names
    if hasattr(node, "keys"):
        names = set()
        for key in node.keys:
            names.update(_variable_names(getattr(node, key)))
        return names
    return set()
