"""GraphQL implementation of the durable optimizer-dispatch backend protocol.

The optimizer dispatch coordinator is deliberately independent of the
dashboard client.  This adapter is its single production boundary: it creates
durable Procedure/Task rows, stores procedure code through the existing
authorized procedure-artifact route, and never starts work locally.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Iterator, Mapping, Sequence

from plexus.cli.procedure.tactus_adapters.storage import (
    download_procedure_attachment,
    upload_procedure_attachment,
)


_PROCEDURE_FIELDS = """
  id accountId scorecardId scoreId name category version featured isTemplate
  status metadata createdAt updatedAt
"""
_TASK_FIELDS = """
  id accountId scorecardId scoreId type status target command dispatchStatus
  celeryTaskId metadata createdAt updatedAt
"""
_TASK_STAGE_FIELDS = """
  id taskId name order status statusMessage startedAt completedAt
  estimatedCompletionAt processedItems totalItems
"""


class OptimizerDispatchBackendError(RuntimeError):
    """A durable dispatch operation could not be proved safe."""


def _metadata(value: Any, *, resource: str) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError as exc:
            raise OptimizerDispatchBackendError(
                f"{resource} metadata is not valid JSON"
            ) from exc
        if isinstance(parsed, Mapping):
            return dict(parsed)
    raise OptimizerDispatchBackendError(f"{resource} metadata is malformed")


def _json_metadata(value: Any, *, resource: str) -> str:
    return json.dumps(_metadata(value, resource=resource), sort_keys=True, separators=(",", ":"))


def _normalise_record(value: Any, *, resource: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise OptimizerDispatchBackendError(f"{resource} response is malformed")
    result = dict(value)
    if not isinstance(result.get("id"), str) or not result["id"]:
        raise OptimizerDispatchBackendError(f"{resource} response omitted its generated id")
    # Preserve raw legacy metadata.  The coordinator applies physical filters
    # before deciding whether a value is optimizer-shaped and must fail closed.
    return result


def _page_connection(
    response: Any,
    *,
    field: str,
    resource: str,
) -> tuple[list[dict[str, Any]], str | None]:
    if not isinstance(response, Mapping) or not isinstance(response.get(field), Mapping):
        raise OptimizerDispatchBackendError(f"{resource} scan page is missing its connection")
    connection = response[field]
    items = connection.get("items")
    token = connection.get("nextToken")
    if not isinstance(items, list):
        raise OptimizerDispatchBackendError(f"{resource} scan page items are malformed")
    if token is not None and (not isinstance(token, str) or not token):
        raise OptimizerDispatchBackendError(f"{resource} scan page token is malformed")
    return [
        _normalise_record(item, resource=resource)
        for item in items
    ], token


class GraphQLOptimizerDispatchBackend:
    """Production GraphQL adapter for :class:`OptimizerTaskDispatchService`.

    IDs are intentionally omitted from all create inputs.  The account scans
    are exhaustive and stop with an exception on an invalid response or a
    pagination cycle, allowing the coordinator to remain fail closed.
    """

    def __init__(self, client: Any, *, artifact_store: Any | None = None, page_size: int = 100) -> None:
        if not callable(getattr(client, "execute", None)):
            raise TypeError("client must provide execute(query, variables)")
        if not isinstance(page_size, int) or page_size < 1 or page_size > 1000:
            raise ValueError("page_size must be between 1 and 1000")
        self._client = client
        self._artifact_store = artifact_store
        self._page_size = page_size

    def procedure_pages_for_account(self, account_id: str) -> Iterator[dict[str, Any]]:
        yield from self._account_pages(
            account_id,
            field="listProcedureByAccountIdUpdatedAt",
            resource="procedure account",
            query=f"""
              query ListProcedureByAccountIdUpdatedAt(
                $accountId: String!, $sortDirection: ModelSortDirection,
                $limit: Int, $nextToken: String
              ) {{
                listProcedureByAccountIdUpdatedAt(
                  accountId: $accountId,
                  sortDirection: $sortDirection, limit: $limit, nextToken: $nextToken
                ) {{ items {{ {_PROCEDURE_FIELDS} }} nextToken }}
              }}
            """,
        )

    def task_pages_for_account(self, account_id: str) -> Iterator[dict[str, Any]]:
        yield from self._account_pages(
            account_id,
            field="listTaskByAccountIdUpdatedAt",
            resource="task account",
            query=f"""
              query ListTaskByAccountIdUpdatedAt(
                $accountId: String!, $sortDirection: ModelSortDirection,
                $limit: Int, $nextToken: String
              ) {{
                listTaskByAccountIdUpdatedAt(
                  accountId: $accountId,
                  sortDirection: $sortDirection, limit: $limit, nextToken: $nextToken
                ) {{ items {{ {_TASK_FIELDS} }} nextToken }}
              }}
            """,
        )

    def _account_pages(
        self, account_id: str, *, field: str, resource: str, query: str,
    ) -> Iterator[dict[str, Any]]:
        if not isinstance(account_id, str) or not account_id:
            raise ValueError("account_id is required")
        token: str | None = None
        seen_tokens: set[str] = set()
        while True:
            response = self._client.execute(query, {
                "accountId": account_id,
                "sortDirection": "DESC",
                "limit": self._page_size,
                "nextToken": token,
            })
            items, next_token = _page_connection(response, field=field, resource=resource)
            yield {"items": items, "next_token": next_token}
            if next_token is None:
                return
            if next_token in seen_tokens:
                raise OptimizerDispatchBackendError(f"{resource} scan pagination token cycle")
            seen_tokens.add(next_token)
            token = next_token

    def get_procedure(self, procedure_id: str) -> dict[str, Any] | None:
        response = self._client.execute(f"""
          query GetProcedure($id: ID!) {{ getProcedure(id: $id) {{ {_PROCEDURE_FIELDS} }} }}
        """, {"id": procedure_id})
        if not isinstance(response, Mapping) or "getProcedure" not in response:
            raise OptimizerDispatchBackendError("procedure readback response is malformed")
        value = response["getProcedure"]
        return None if value is None else _normalise_record(value, resource="procedure")

    def create_procedure(self, record: Mapping[str, Any]) -> dict[str, Any]:
        input_data = self._procedure_input(record)
        response = self._client.execute(f"""
          mutation CreateProcedure($input: CreateProcedureInput!) {{
            createProcedure(input: $input) {{ {_PROCEDURE_FIELDS} }}
          }}
        """, {"input": input_data})
        if not isinstance(response, Mapping) or "createProcedure" not in response:
            raise OptimizerDispatchBackendError("created Procedure response is malformed")
        created = _normalise_record(response["createProcedure"], resource="created Procedure")
        self._validate_procedure(created, record, label="created Procedure")
        return created

    @staticmethod
    def _procedure_input(record: Mapping[str, Any]) -> dict[str, Any]:
        required = (
            "accountId", "scorecardId", "scoreId", "name", "category", "version",
            "featured", "isTemplate", "status", "metadata",
        )
        missing = [key for key in required if key not in record]
        if missing:
            raise ValueError(f"Procedure record is missing required fields: {', '.join(missing)}")
        if "id" in record:
            raise ValueError("Procedure id must be generated by GraphQL")
        result = {key: record[key] for key in required if key != "metadata"}
        result["metadata"] = _json_metadata(record["metadata"], resource="Procedure")
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        result["createdAt"] = now
        result["updatedAt"] = now
        return result

    @staticmethod
    def _validate_procedure(
        actual: Mapping[str, Any], expected: Mapping[str, Any], *, label: str,
    ) -> None:
        for field in (
            "accountId", "scorecardId", "scoreId", "name", "category", "version",
            "featured", "isTemplate", "status",
        ):
            if actual.get(field) != expected.get(field):
                raise OptimizerDispatchBackendError(f"{label} physical identity mismatch: {field}")
        if _metadata(actual.get("metadata"), resource=label) != _metadata(
            expected.get("metadata"), resource=label,
        ):
            raise OptimizerDispatchBackendError(f"{label} launch metadata mismatch")

    def upload_and_verify_procedure_yaml(
        self,
        procedure: Mapping[str, Any],
        optimizer_yaml: str,
        metadata: Mapping[str, Any],
    ) -> dict[str, Any]:
        procedure_id = procedure.get("id") if isinstance(procedure, Mapping) else None
        if not isinstance(procedure_id, str) or not procedure_id:
            raise ValueError("procedure must include its generated id")
        if not isinstance(optimizer_yaml, str) or not optimizer_yaml:
            raise ValueError("optimizer_yaml is required")
        content = optimizer_yaml.encode("utf-8")
        digest = sha256(content).hexdigest()
        supplied_metadata = _metadata(metadata, resource="Procedure")
        if supplied_metadata.get("optimizer_yaml_sha256") != digest:
            raise OptimizerDispatchBackendError("optimizer YAML checksum does not match immutable launch metadata")

        # Procedure code is a pre-existing, distinct artifact contract.  Living
        # Report snapshots use TASK_ATTACHMENT; optimizer source must retain its
        # supported PROCEDURE_ATTACHMENT route and procedures/<id>/code.tac key.
        pointer = upload_procedure_attachment(
            self._client,
            procedure_id,
            "code.tac",
            content,
            content_type="text/plain",
            existing_metadata=None,
            artifact_store=self._artifact_store,
        )
        artifact = self._normalise_procedure_pointer(procedure_id, pointer, digest, len(content))
        updated_metadata = {**supplied_metadata, "code_artifact": artifact}
        updated = self._update_procedure_metadata(procedure_id, updated_metadata)
        persisted = _metadata(updated.get("metadata"), resource="updated Procedure")
        if persisted != updated_metadata:
            raise OptimizerDispatchBackendError("updated Procedure attachment metadata did not read back exactly")
        self._read_procedure_artifact_pointer(procedure_id, artifact, expected_digest=digest)
        return updated

    @staticmethod
    def _normalise_procedure_pointer(
        procedure_id: str, pointer: Any, digest: str, size_bytes: int,
    ) -> dict[str, Any]:
        if not isinstance(pointer, Mapping):
            raise OptimizerDispatchBackendError("procedure attachment upload returned malformed metadata")
        expected_key = f"procedures/{procedure_id}/code.tac"
        object_key = pointer.get("_s3_key") or pointer.get("key")
        if object_key != expected_key:
            raise OptimizerDispatchBackendError("procedure attachment is outside the procedure namespace")
        if pointer.get("sha256") != digest or pointer.get("size_bytes") != size_bytes:
            raise OptimizerDispatchBackendError("procedure attachment integrity metadata does not match source")
        content_type = pointer.get("content_type") or pointer.get("contentType")
        if content_type != "text/plain":
            raise OptimizerDispatchBackendError("procedure attachment content type is not text/plain")
        return {
            "key": expected_key,
            "_s3_key": expected_key,
            "sha256": digest,
            "size_bytes": size_bytes,
            "content_type": "text/plain",
        }

    def _update_procedure_metadata(self, procedure_id: str, metadata: Mapping[str, Any]) -> dict[str, Any]:
        response = self._client.execute(f"""
          mutation UpdateProcedure($input: UpdateProcedureInput!) {{
            updateProcedure(input: $input) {{ {_PROCEDURE_FIELDS} }}
          }}
        """, {"input": {"id": procedure_id, "metadata": _json_metadata(metadata, resource="Procedure")}})
        if not isinstance(response, Mapping) or "updateProcedure" not in response:
            raise OptimizerDispatchBackendError("Procedure metadata update response is malformed")
        updated = _normalise_record(response["updateProcedure"], resource="updated Procedure")
        if updated.get("id") != procedure_id:
            raise OptimizerDispatchBackendError("Procedure metadata update returned a different Procedure")
        return updated

    def read_procedure_artifact(self, key: str) -> bytes:
        procedure_id = self._procedure_id_from_key(key)
        procedure = self.get_procedure(procedure_id)
        if procedure is None:
            raise OptimizerDispatchBackendError("Procedure attachment owner no longer exists")
        pointer = _metadata(procedure.get("metadata"), resource="Procedure").get("code_artifact")
        return self._read_procedure_artifact_pointer(procedure_id, pointer)

    @staticmethod
    def _procedure_id_from_key(key: Any) -> str:
        if not isinstance(key, str):
            raise OptimizerDispatchBackendError("Procedure attachment key is malformed")
        components = key.split("/")
        if len(components) != 3 or components[0] != "procedures" or not components[1] or components[2] != "code.tac":
            raise OptimizerDispatchBackendError("procedure attachment is outside the procedure namespace")
        return components[1]

    def _read_procedure_artifact_pointer(
        self, procedure_id: str, pointer: Any, *, expected_digest: str | None = None,
    ) -> bytes:
        if not isinstance(pointer, Mapping):
            raise OptimizerDispatchBackendError("Procedure attachment pointer is malformed")
        expected_key = f"procedures/{procedure_id}/code.tac"
        if pointer.get("key") != expected_key or pointer.get("_s3_key") != expected_key:
            raise OptimizerDispatchBackendError("procedure attachment is outside the procedure namespace")
        digest = pointer.get("sha256")
        if not isinstance(digest, str) or (expected_digest is not None and digest != expected_digest):
            raise OptimizerDispatchBackendError("Procedure attachment checksum is invalid")
        try:
            payload = download_procedure_attachment(
                self._client,
                procedure_id,
                "code.tac",
                pointer,
                content_type="text/plain",
                artifact_store=self._artifact_store,
            )
        except Exception as exc:
            raise OptimizerDispatchBackendError("Procedure attachment readback failed") from exc
        if not isinstance(payload, bytes) or sha256(payload).hexdigest() != digest:
            raise OptimizerDispatchBackendError("Procedure attachment readback checksum mismatch")
        return payload

    def create_task(self, record: Mapping[str, Any]) -> dict[str, Any]:
        input_data = self._task_input(record)
        response = self._client.execute(f"""
          mutation CreateTask($input: CreateTaskInput!) {{
            createTask(input: $input) {{ {_TASK_FIELDS} }}
          }}
        """, {"input": input_data})
        if not isinstance(response, Mapping) or "createTask" not in response:
            raise OptimizerDispatchBackendError("created Task response is malformed")
        created = _normalise_record(response["createTask"], resource="created Task")
        self._validate_task(created, record, label="created Task")
        return created

    @staticmethod
    def _task_input(record: Mapping[str, Any]) -> dict[str, Any]:
        required = (
            "accountId", "scorecardId", "scoreId", "type", "status", "target",
            "command", "dispatchStatus", "metadata",
        )
        missing = [key for key in required if key not in record]
        if missing:
            raise ValueError(f"Task record is missing required fields: {', '.join(missing)}")
        if "id" in record:
            raise ValueError("Task id must be generated by GraphQL")
        result = {key: record[key] for key in required if key != "metadata"}
        result["metadata"] = _json_metadata(record["metadata"], resource="Task")
        return result

    @staticmethod
    def _validate_task(actual: Mapping[str, Any], expected: Mapping[str, Any], *, label: str) -> None:
        for field in (
            "accountId", "scorecardId", "scoreId", "type", "status", "target",
            "command", "dispatchStatus",
        ):
            if actual.get(field) != expected.get(field):
                raise OptimizerDispatchBackendError(f"{label} physical identity mismatch: {field}")
        actual_metadata = _metadata(actual.get("metadata"), resource=label)
        expected_metadata = _metadata(expected.get("metadata"), resource=label)
        if actual_metadata != expected_metadata:
            raise OptimizerDispatchBackendError(f"{label} launch metadata mismatch")
        if actual_metadata.get("procedure_id") != expected_metadata.get("procedure_id"):
            raise OptimizerDispatchBackendError(f"{label} procedure_id metadata mismatch")

    def get_task(self, task_id: str) -> dict[str, Any] | None:
        response = self._client.execute(f"""
          query GetTask($id: ID!) {{ getTask(id: $id) {{ {_TASK_FIELDS} }} }}
        """, {"id": task_id})
        if not isinstance(response, Mapping) or "getTask" not in response:
            raise OptimizerDispatchBackendError("Task readback response is malformed")
        value = response["getTask"]
        return None if value is None else _normalise_record(value, resource="Task")

    def task_stage_pages_for_task(self, task_id: str) -> Iterator[dict[str, Any]]:
        yield from self._stage_pages(task_id)

    def _stage_pages(self, task_id: str) -> Iterator[dict[str, Any]]:
        if not isinstance(task_id, str) or not task_id:
            raise ValueError("task_id is required")
        token: str | None = None
        seen_tokens: set[str] = set()
        query = f"""
          query ListTaskStageByTaskId($taskId: String!, $limit: Int, $nextToken: String) {{
            listTaskStageByTaskId(taskId: $taskId, limit: $limit, nextToken: $nextToken) {{
              items {{ {_TASK_STAGE_FIELDS} }} nextToken
            }}
          }}
        """
        while True:
            response = self._client.execute(query, {
                "taskId": task_id, "limit": self._page_size, "nextToken": token,
            })
            items, next_token = _page_connection(
                response, field="listTaskStageByTaskId", resource="task stage",
            )
            for stage in items:
                if stage.get("taskId") != task_id:
                    raise OptimizerDispatchBackendError("task stage belongs to a different Task")
            yield {"items": items, "next_token": next_token}
            if next_token is None:
                return
            if next_token in seen_tokens:
                raise OptimizerDispatchBackendError("task stage scan pagination token cycle")
            seen_tokens.add(next_token)
            token = next_token

    def reconcile_task_stages(self, task_id: str, stages: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
        expected = self._expected_stages(stages)
        observed = self._all_task_stages(task_id)
        observed_by_key = self._validate_stage_set(task_id, observed, expected)
        for key, stage in expected.items():
            if key not in observed_by_key:
                try:
                    created = self._create_task_stage(task_id, stage)
                except Exception as exc:
                    # The mutation may have committed before its response was
                    # lost. Exhaustive readback is the only safe recovery; an
                    # absent stage remains unknown and is never created twice.
                    after_uncertain_create = self._all_task_stages(task_id)
                    adopted = self._validate_stage_set(
                        task_id, after_uncertain_create, expected,
                    )
                    if key not in adopted:
                        raise OptimizerDispatchBackendError(
                            "TaskStage create outcome is unknown"
                        ) from exc
                    observed_by_key.update(adopted)
                    continue
                if (created.get("name"), created.get("order")) != key:
                    raise OptimizerDispatchBackendError("created TaskStage identity mismatch")
        reread = self._all_task_stages(task_id)
        self._validate_stage_set(task_id, reread, expected, require_complete=True)
        return reread

    @staticmethod
    def _expected_stages(stages: Sequence[Mapping[str, Any]]) -> dict[tuple[str, int], dict[str, Any]]:
        expected: dict[tuple[str, int], dict[str, Any]] = {}
        for stage in stages:
            if not isinstance(stage, Mapping):
                raise OptimizerDispatchBackendError("expected TaskStage is malformed")
            name, order, status = stage.get("name"), stage.get("order"), stage.get("status")
            if not isinstance(name, str) or not name or not isinstance(order, int) or not isinstance(status, str):
                raise OptimizerDispatchBackendError("expected TaskStage fields are malformed")
            key = (name, order)
            if key in expected:
                raise OptimizerDispatchBackendError("expected TaskStages are ambiguous")
            expected[key] = {"name": name, "order": order, "status": status}
        return expected

    def _all_task_stages(self, task_id: str) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for page in self._stage_pages(task_id):
            result.extend(page["items"])
        return result

    @staticmethod
    def _validate_stage_set(
        task_id: str,
        observed: Sequence[Mapping[str, Any]],
        expected: Mapping[tuple[str, int], Mapping[str, Any]],
        *,
        require_complete: bool = False,
    ) -> dict[tuple[str, int], dict[str, Any]]:
        result: dict[tuple[str, int], dict[str, Any]] = {}
        for stage in observed:
            if stage.get("taskId") != task_id:
                raise OptimizerDispatchBackendError("TaskStage physical Task identity mismatch")
            key = (stage.get("name"), stage.get("order"))
            if key not in expected:
                raise OptimizerDispatchBackendError("unexpected TaskStage exists")
            if key in result:
                raise OptimizerDispatchBackendError("TaskStages are ambiguous")
            if stage.get("status") != expected[key].get("status"):
                raise OptimizerDispatchBackendError("TaskStage configuration mismatch")
            result[key] = dict(stage)
        if require_complete and set(result) != set(expected):
            raise OptimizerDispatchBackendError("TaskStage readback is incomplete")
        return result

    def _create_task_stage(self, task_id: str, stage: Mapping[str, Any]) -> dict[str, Any]:
        input_data = {"taskId": task_id, **dict(stage)}
        response = self._client.execute(f"""
          mutation CreateTaskStage($input: CreateTaskStageInput!) {{
            createTaskStage(input: $input) {{ {_TASK_STAGE_FIELDS} }}
          }}
        """, {"input": input_data})
        if not isinstance(response, Mapping) or "createTaskStage" not in response:
            raise OptimizerDispatchBackendError("created TaskStage response is malformed")
        return _normalise_record(response["createTaskStage"], resource="created TaskStage")

    def release_held_task(self, task_id: str) -> dict[str, Any]:
        task = self.get_task(task_id)
        if task is None:
            raise OptimizerDispatchBackendError("held Task no longer exists")
        if task.get("dispatchStatus") != "HELD":
            raise OptimizerDispatchBackendError("Task is not HELD and cannot be released")
        task_metadata = _metadata(task.get("metadata"), resource="Task")
        procedure_id = task_metadata.get("procedure_id")
        if (
            not isinstance(procedure_id, str)
            or not procedure_id
            or task_metadata.get("dispatch_policy") != "held_once"
            or task.get("type") != "Procedure"
            or task.get("status") != "PENDING"
            or task.get("target") != f"procedure/{procedure_id}"
            or task.get("command") != f"procedure run {procedure_id}"
        ):
            raise OptimizerDispatchBackendError("held Task dispatch identity is malformed")
        input_data = {
            "id": task_id,
            "accountId": task.get("accountId"),
            "type": task.get("type"),
            "status": task.get("status"),
            "target": task.get("target"),
            "command": task.get("command"),
            "dispatchStatus": "PENDING",
            "scorecardId": task.get("scorecardId"),
            "scoreId": task.get("scoreId"),
            "metadata": _json_metadata(task_metadata, resource="Task"),
        }
        if any(not isinstance(input_data[key], str) or not input_data[key] for key in (
            "accountId", "type", "status", "target", "command", "scorecardId", "scoreId",
        )):
            raise OptimizerDispatchBackendError("held Task physical identity is malformed")
        response = self._client.execute(f"""
          mutation UpdateTask($input: UpdateTaskInput!) {{
            updateTask(input: $input) {{ {_TASK_FIELDS} }}
          }}
        """, {"input": input_data})
        if not isinstance(response, Mapping) or "updateTask" not in response:
            raise OptimizerDispatchBackendError("Task release response is malformed")
        updated = _normalise_record(response["updateTask"], resource="released Task")
        if updated.get("id") != task_id or updated.get("dispatchStatus") != "PENDING":
            raise OptimizerDispatchBackendError("Task release did not transition HELD to PENDING")
        return updated
