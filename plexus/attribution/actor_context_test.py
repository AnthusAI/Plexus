import pytest

from plexus.attribution.actor_context import (
    apply_actor_attribution,
    resolve_actor_context,
    set_runtime_actor_context,
)


pytestmark = pytest.mark.unit


def test_resolve_actor_context_prefers_request_user_over_env(monkeypatch):
    monkeypatch.setenv("PLEXUS_ACTOR_USER_ID", "env-user")
    actor = resolve_actor_context(request_user_id="request-user", explicit_source="execute_tactus")
    assert actor.user_id == "request-user"
    assert actor.actor_source == "execute_tactus"


def test_resolve_actor_context_uses_runtime_override_before_env(monkeypatch):
    monkeypatch.setenv("PLEXUS_ACTOR_USER_ID", "env-user")
    runtime = {
        "actor_user_id": "runtime-user",
        "actor_type": "agent",
        "actor_key": "runtime-key",
        "actor_source": "agent",
    }
    with set_runtime_actor_context(runtime):
        actor = resolve_actor_context(explicit_source="cli")
    assert actor.user_id == "runtime-user"
    assert actor.actor_key == "runtime-key"
    assert actor.actor_source == "agent"


def test_apply_actor_attribution_merges_existing_metadata(monkeypatch):
    monkeypatch.setenv("PLEXUS_ACTOR_USER_ID", "env-user")
    input_data = {"metadata": {"existing": True}}
    output = apply_actor_attribution(input_data, source="cli")
    assert output["createdByUserId"] == "env-user"
    assert output["metadata"]["existing"] is True
    assert output["metadata"]["attribution"]["requestUserId"] == "env-user"
