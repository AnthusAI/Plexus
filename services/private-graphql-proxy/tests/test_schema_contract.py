from __future__ import annotations

from proxy.schema_contract import get_schema_contract


EXPECTED_MODELS = {
    "Account",
    "Scorecard",
    "ScorecardSection",
    "Score",
    "ScoreVersion",
    "Evaluation",
    "Item",
    "Identifier",
    "ScoringJob",
    "ScoreResult",
    "Task",
    "TaskStage",
    "ShareLink",
    "ReportConfiguration",
    "Report",
    "ReportBlock",
    "FeedbackItem",
    "ScorecardExampleItem",
    "AggregatedMetrics",
    "DataSource",
    "DataSourceVersion",
    "DataSet",
    "Procedure",
    "ChatSession",
    "ChatMessage",
    "User",
}


def test_generated_manifest_contains_amplify_models_and_operations():
    contract = get_schema_contract()
    models = contract.manifest["models"]

    assert EXPECTED_MODELS.issubset(models)
    assert models["ScoreResult"]["operations"]["get"] == "getScoreResult"
    assert models["ScoreResult"]["operations"]["list"] == "listScoreResults"
    assert models["ScoreResult"]["operations"]["create"] == "createScoreResult"
    assert contract.manifest["subscriptions"]["ScoreResult"] == {
        "model": "ScoreResult",
        "onCreate": "onCreateScoreResult",
        "onUpdate": "onUpdateScoreResult",
        "onDelete": "onDeleteScoreResult",
    }


def test_generated_manifest_contains_named_identifiers_indexes_and_arguments():
    contract = get_schema_contract()
    identifier = contract.manifest["models"]["Identifier"]
    score_result_indexes = {
        index["queryField"]: index
        for index in contract.manifest["indexes"]["ScoreResult"]
    }

    assert identifier["primaryKey"] == ["itemId", "name"]
    compound_index = score_result_indexes[
        "listScoreResultByItemIdAndTypeAndScoreIdAndUpdatedAt"
    ]
    assert compound_index["name"] == "byItemIdAndTypeAndScoreIdAndUpdatedAt"
    assert compound_index["partitionField"] == "itemId"
    assert compound_index["sortFields"] == ["type", "scoreId", "updatedAt"]
    assert compound_index["sortArgument"] == "typeScoreIdUpdatedAt"
    assert compound_index["arguments"] == [
        "itemId",
        "typeScoreIdUpdatedAt",
        "filter",
        "sortDirection",
        "limit",
        "nextToken",
    ]


def test_generated_manifest_preserves_relationships_and_auth_rules():
    contract = get_schema_contract()
    relationships = {
        (relationship["model"], relationship["field"]): relationship
        for relationship in contract.manifest["relationships"]
    }

    assert relationships[("ScoreResult", "item")]["kind"] == "belongsTo"
    assert relationships[("ScoreResult", "item")]["targetModel"] == "Item"
    assert relationships[("Item", "scoreResults")]["connectionShape"] == "connection"
    assert contract.manifest["authRules"]["ShareLink"] == ["apiKey", "authenticated"]


def test_generated_manifest_contains_custom_share_token_operation():
    contract = get_schema_contract()
    operation = contract.manifest["customOperations"]["getResourceByShareToken"]

    assert operation["arguments"]["token"]["isRequired"] is True
    assert operation["returnType"] == "ResourceByShareTokenResponse"
    assert operation["authRules"] == ["guest", "apiKey", "authenticated"]
    assert operation["handler"] == "getResourceByShareTokenHandler"


def test_generated_manifest_contains_storage_prefix_policies():
    storage = get_schema_contract().manifest["storage"]

    assert storage["dataSources"]["isDefault"] is True
    assert storage["dataSources"]["access"]["datasources/*"] == [
        {"operations": ["read"], "principal": "guest"},
        {"operations": ["read", "write", "delete"], "principal": "authenticated"},
    ]
    assert storage["rubricMemory"]["access"]["rubric-memory/*"] == [
        {"operations": ["read", "write", "delete"], "principal": "authenticated"}
    ]
