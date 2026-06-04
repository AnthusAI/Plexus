from proxy.graphql_tools import build_operation_plan, build_root_only_query
from proxy.schema_contract import get_schema_contract


def test_classifies_private_and_control_roots():
    plan = build_operation_plan(
        """
        query Mixed($itemId: ID!, $scoreId: ID!) {
            getItem(id: $itemId) { id text }
            getScore(id: $scoreId) { id name }
        }
        """,
        "Mixed",
    )

    assert [field.name for field in plan.private_fields] == ["getItem"]
    assert [field.name for field in plan.control_fields] == ["getScore"]
    assert not plan.blocked_fields


def test_blocks_control_plane_mutations():
    plan = build_operation_plan(
        """
        mutation Unsafe($input: CreateScoreInput!) {
            createScore(input: $input) { id name }
        }
        """,
        "Unsafe",
    )

    assert [field.name for field in plan.blocked_fields] == ["createScore"]


def test_local_backend_mode_classifies_all_manifest_model_roots_as_private(monkeypatch):
    monkeypatch.setenv("PLEXUS_BACKEND_MODE", "local")

    plan = build_operation_plan(
        """
        mutation LocalControlPlane($input: CreateScoreInput!) {
            createScore(input: $input) { id name }
        }
        """,
        "LocalControlPlane",
    )

    assert [(field.name, field.model) for field in plan.private_fields] == [
        ("createScore", "Score")
    ]
    assert not plan.blocked_fields


def test_classifies_manifest_index_roots_without_hard_coded_prefixes():
    plan = build_operation_plan(
        """
        query ScoreResultIndex($itemId: String!) {
            listScoreResultByItemIdAndTypeAndScoreIdAndUpdatedAt(itemId: $itemId) {
                items { id itemId scoreId type }
                nextToken
            }
        }
        """,
        "ScoreResultIndex",
    )

    assert [(field.name, field.model) for field in plan.private_fields] == [
        ("listScoreResultByItemIdAndTypeAndScoreIdAndUpdatedAt", "ScoreResult")
    ]


def test_manifest_exposes_custom_share_token_operation_as_control_read():
    operation = get_schema_contract().root_operation("getResourceByShareToken")

    assert operation is not None
    assert operation.action == "custom"
    assert operation.operation_type == "query"


def test_classifies_legacy_index_root_aliases_for_backward_compatibility(monkeypatch):
    monkeypatch.setenv("PLEXUS_BACKEND_MODE", "local")
    plan = build_operation_plan(
        """
        query LegacyIndexAlias($accountId: String!) {
            listItemByAccountIdAndCreatedAt(accountId: $accountId) {
                items { id accountId createdAt }
                nextToken
            }
        }
        """,
        "LegacyIndexAlias",
    )

    assert [(field.name, field.model) for field in plan.private_fields] == [
        ("listItemByAccountIdAndCreatedAt", "Item")
    ]
    assert not plan.blocked_fields


def test_classifies_synthetic_legacy_index_roots_not_in_manifest(monkeypatch):
    monkeypatch.setenv("PLEXUS_BACKEND_MODE", "local")
    plan = build_operation_plan(
        """
        query LegacySyntheticIndex($scorecardId: String!) {
            listScoreByScorecardIdAndOrder(scorecardId: $scorecardId, sortDirection: ASC) {
                items { id scorecardId order }
                nextToken
            }
        }
        """,
        "LegacySyntheticIndex",
    )

    assert [(field.name, field.model) for field in plan.private_fields] == [
        ("listScoreByScorecardIdAndOrder", "Score")
    ]
    assert not plan.blocked_fields


def test_local_backend_mode_routes_every_manifest_model_root_locally(monkeypatch):
    monkeypatch.setenv("PLEXUS_BACKEND_MODE", "local")
    contract = get_schema_contract()

    for model_name, model in contract.models.items():
        for root_name in model["operations"]["indexes"]:
            classification = contract.classify_root(root_name, "query")
            assert classification.classification == "private"
            assert classification.model == model_name

        for action, operation_type in {
            "get": "query",
            "list": "query",
            "create": "mutation",
            "update": "mutation",
            "delete": "mutation",
        }.items():
            classification = contract.classify_root(
                model["operations"][action],
                operation_type,
            )
            assert classification.classification == "private"
            assert classification.model == model_name


def test_builds_control_only_query_for_mixed_operation():
    plan = build_operation_plan(
        """
        query Mixed($itemId: ID!, $scoreId: ID!) {
            getItem(id: $itemId) { id text }
            getScore(id: $scoreId) { id name }
        }
        """,
        "Mixed",
    )

    control_query = build_root_only_query(plan, plan.control_fields)

    assert "getScore" in control_query
    assert "getItem" not in control_query
    assert "$scoreId" in control_query
    assert "$itemId" not in control_query
