from unittest.mock import Mock, patch

from plexus.cli.shared.identifier_resolution import (
    resolve_item_identifier,
    resolve_item_reference,
)


def setup_function():
    resolve_item_reference.cache_clear()
    resolve_item_identifier.cache_clear()


def test_resolve_item_reference_returns_direct_item_id():
    client = Mock()

    with patch("plexus.dashboard.api.models.item.Item.get_by_id", return_value=Mock(id="item-123")):
        resolved = resolve_item_reference(client, "item-123", "account-1")

    assert resolved == ("item-123", "item_id")


def test_resolve_item_reference_uses_identifier_value_lookup():
    client = Mock()
    found_item = Mock(id="item-456")

    with patch("plexus.dashboard.api.models.item.Item.get_by_id", return_value=None), patch(
        "plexus.utils.identifier_search.find_item_by_identifier",
        return_value=found_item,
    ), patch(
        "plexus.dashboard.api.models.item.Item._lookup_item_by_external_id",
        return_value=None,
    ):
        resolved = resolve_item_reference(client, "CUSTOMER-42", "account-1")

    assert resolved == ("item-456", "identifier_value")


def test_resolve_item_reference_falls_back_to_external_id():
    client = Mock()

    with patch("plexus.dashboard.api.models.item.Item.get_by_id", return_value=None), patch(
        "plexus.utils.identifier_search.find_item_by_identifier",
        return_value=None,
    ), patch(
        "plexus.dashboard.api.models.item.Item._lookup_item_by_external_id",
        return_value={"id": "item-789"},
    ):
        resolved = resolve_item_reference(client, "EXT-123", "account-1")

    assert resolved == ("item-789", "external_id")


def test_resolve_item_identifier_returns_only_item_id():
    client = Mock()

    with patch(
        "plexus.cli.shared.identifier_resolution.resolve_item_reference",
        return_value=("item-999", "identifier_value"),
    ):
        resolved = resolve_item_identifier(client, "CASE-123", "account-1")

    assert resolved == "item-999"
