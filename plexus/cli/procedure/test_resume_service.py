from plexus.cli.procedure.resume_service import resume_procedure


def test_resume_uses_local_task_tracked_execution_to_finalize_state(monkeypatch):
    calls = []

    class _Client:
        def execute(self, query, variables):
            if "query GetProcedure" in query:
                return {
                    "getProcedure": {
                        "id": "procedure-1",
                        "status": "WAITING_FOR_HUMAN",
                        "waitingOnMessageId": "pending-1",
                        "code": "name: validation",
                        "accountId": "account-1",
                    }
                }
            if "query FindResponse" in query:
                return {
                    "listChatMessageByParentMessageId": {
                        "items": [{"id": "response-1", "createdAt": "2026-07-28T00:00:00Z"}]
                    }
                }
            raise AssertionError(f"Unexpected GraphQL operation: {query}")

    class _DirectServiceMustNotRun:
        def __init__(self, _client):
            pass

        async def run_procedure(self, **_kwargs):
            raise AssertionError("resume must use the task-tracked local runner")

    async def _run_tracked(**kwargs):
        calls.append(kwargs)
        return {"success": True, "status": "COMPLETED", "message": "complete"}

    monkeypatch.setattr(
        "plexus.cli.procedure.service.ProcedureService",
        _DirectServiceMustNotRun,
    )
    monkeypatch.setattr(
        "plexus.cli.shared.experiment_runner.run_procedure_with_task_tracking",
        _run_tracked,
    )

    client = _Client()
    result = resume_procedure(client, "procedure-1")

    assert result == {
        "resumed": True,
        "status": "COMPLETED",
        "message": "Procedure resumed and executed successfully",
    }
    assert calls == [
        {
            "procedure_id": "procedure-1",
            "client": client,
            "account_id": "account-1",
        }
    ]
