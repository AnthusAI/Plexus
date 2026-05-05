from proxy.graphql_tools import build_operation_plan, build_root_only_query


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
