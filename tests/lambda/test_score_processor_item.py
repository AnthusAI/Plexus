import importlib.util
import asyncio
import sys
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest


def _load_handler_module():
    if "boto3" not in sys.modules:
        sys.modules["boto3"] = SimpleNamespace(client=lambda *_args, **_kwargs: Mock())
    if "botocore" not in sys.modules:
        botocore_module = types.ModuleType("botocore")
        exceptions_module = types.ModuleType("botocore.exceptions")
        exceptions_module.ClientError = Exception
        botocore_module.exceptions = exceptions_module
        sys.modules["botocore"] = botocore_module
        sys.modules["botocore.exceptions"] = exceptions_module

    client_module_name = "plexus.dashboard.api.client"
    if client_module_name not in sys.modules:
        client_module = types.ModuleType(client_module_name)
        client_module.PlexusDashboardClient = object
        sys.modules[client_module_name] = client_module

    def _ensure_model_module(module_name, class_name):
        if module_name in sys.modules:
            return
        module = types.ModuleType(module_name)
        model_cls = type(class_name, (), {"get_by_id": staticmethod(lambda *_a, **_k: None)})
        setattr(module, class_name, model_cls)
        sys.modules[module_name] = module

    _ensure_model_module("plexus.dashboard.api.models.scoring_job", "ScoringJob")
    _ensure_model_module("plexus.dashboard.api.models.account", "Account")
    _ensure_model_module("plexus.dashboard.api.models.scorecard", "Scorecard")
    _ensure_model_module("plexus.dashboard.api.models.score", "Score")
    _ensure_model_module("plexus.dashboard.api.models.item", "Item")

    handler_path = Path(__file__).resolve().parents[2] / "score-processor-lambda" / "handler.py"
    spec = importlib.util.spec_from_file_location("score_processor_lambda_handler", handler_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_lambda_process_job_passes_item_to_scoring_helper():
    handler = _load_handler_module()
    processor = handler.LambdaJobProcessor.__new__(handler.LambdaJobProcessor)
    processor.client = Mock()
    processor.account_id = "acct-1"
    processor.response_queue_url = "https://example.com/queue"
    processor.request_queue_url = "https://example.com/request-queue"
    processor.sqs_client = Mock()

    fake_item = SimpleNamespace(id="item-123", text="fallback")
    fake_result = SimpleNamespace(value="ok", metadata={})
    fake_outcome = SimpleNamespace(result=fake_result, dependency_unmet=False, score_results={"score-id": fake_result})
    fake_scorecard = SimpleNamespace(score_entire_text=AsyncMock())
    fake_scoring_job = Mock()
    score_helper = AsyncMock(return_value=fake_outcome)

    with patch.object(handler.ScoringJob, "get_by_id", return_value=fake_scoring_job):
        with patch.object(handler, "resolve_scorecard_id", return_value="scorecard-id"):
            with patch.object(handler, "resolve_score_id", return_value={"id": "score-id", "name": "Target Score"}):
                with patch.object(handler, "get_text_from_item", return_value="text"):
                    with patch.object(handler, "get_metadata_from_item", return_value={}):
                        with patch.object(handler, "get_external_id_from_item", return_value="ext-1"):
                            with patch.object(handler, "create_scorecard_instance_for_single_score", return_value=fake_scorecard):
                                with patch.object(handler, "create_score_result", AsyncMock(return_value="srid")) as create_score_result:
                                    with patch.object(handler, "score_single_target_with_dependencies", score_helper):
                                        with patch.object(handler, "Item", SimpleNamespace(get_by_id=Mock(return_value=fake_item)), create=True):
                                            asyncio.run(
                                                processor.process_job(
                                                    "job-1",
                                                    "item-123",
                                                    "scorecard-external",
                                                    "score-external",
                                                    receipt_handle=None,
                                                )
                                            )

    call_kwargs = score_helper.call_args.kwargs
    assert call_kwargs["item"] is fake_item
    assert call_kwargs["target_score_id"] == "score-id"
    assert call_kwargs["target_score_name"] == "Target Score"
    create_score_result.assert_called_once()
    processor.sqs_client.send_message.assert_called_once()


def test_lambda_process_job_dependency_unmet_marks_failed_without_retry():
    handler = _load_handler_module()
    processor = handler.LambdaJobProcessor.__new__(handler.LambdaJobProcessor)
    processor.client = Mock()
    processor.account_id = "acct-1"
    processor.response_queue_url = "https://example.com/queue"
    processor.request_queue_url = "https://example.com/request-queue"
    processor.sqs_client = Mock()

    fake_item = SimpleNamespace(id="item-123", text="fallback")
    fake_outcome = SimpleNamespace(result=None, dependency_unmet=True, score_results={"score-id": "SKIPPED"})
    fake_scoring_job = Mock()

    with patch.object(handler.ScoringJob, "get_by_id", return_value=fake_scoring_job):
        with patch.object(handler, "resolve_scorecard_id", return_value="scorecard-id"):
            with patch.object(handler, "resolve_score_id", return_value={"id": "score-id", "name": "Target Score"}):
                with patch.object(handler, "get_text_from_item", return_value="text"):
                    with patch.object(handler, "get_metadata_from_item", return_value={}):
                        with patch.object(handler, "get_external_id_from_item", return_value="ext-1"):
                            with patch.object(handler, "create_scorecard_instance_for_single_score", return_value=SimpleNamespace()):
                                with patch.object(handler, "score_single_target_with_dependencies", AsyncMock(return_value=fake_outcome)):
                                    with patch.object(handler, "create_score_result", AsyncMock()) as create_score_result:
                                        with patch.object(handler, "Item", SimpleNamespace(get_by_id=Mock(return_value=fake_item)), create=True):
                                            asyncio.run(
                                                processor.process_job(
                                                    "job-1",
                                                    "item-123",
                                                    "scorecard-external",
                                                    "score-external",
                                                    receipt_handle="receipt-1",
                                                )
                                            )

    create_score_result.assert_not_called()
    processor.sqs_client.send_message.assert_not_called()
    processor.sqs_client.delete_message.assert_called_once()
    failed_calls = [
        call for call in fake_scoring_job.update.call_args_list
        if call.kwargs.get("status") == "FAILED"
    ]
    assert failed_calls
    assert failed_calls[-1].kwargs.get("errorMessage") == handler.DEPENDENCY_UNMET_MESSAGE[:255]


def test_lambda_process_job_re_raises_on_non_dependency_failure():
    handler = _load_handler_module()
    processor = handler.LambdaJobProcessor.__new__(handler.LambdaJobProcessor)
    processor.client = Mock()
    processor.account_id = "acct-1"
    processor.response_queue_url = "https://example.com/queue"
    processor.request_queue_url = "https://example.com/request-queue"
    processor.sqs_client = Mock()

    fake_item = SimpleNamespace(id="item-123", text="fallback")
    fake_scoring_job = Mock()

    with patch.object(handler.ScoringJob, "get_by_id", return_value=fake_scoring_job):
        with patch.object(handler, "resolve_scorecard_id", return_value="scorecard-id"):
            with patch.object(handler, "resolve_score_id", return_value={"id": "score-id", "name": "Target Score"}):
                with patch.object(handler, "get_text_from_item", return_value="text"):
                    with patch.object(handler, "get_metadata_from_item", return_value={}):
                        with patch.object(handler, "get_external_id_from_item", return_value="ext-1"):
                            with patch.object(handler, "create_scorecard_instance_for_single_score", return_value=SimpleNamespace()):
                                with patch.object(handler, "score_single_target_with_dependencies", AsyncMock(side_effect=RuntimeError("boom"))):
                                    with patch.object(handler, "Item", SimpleNamespace(get_by_id=Mock(return_value=fake_item)), create=True):
                                        with pytest.raises(RuntimeError, match="boom"):
                                            asyncio.run(
                                                processor.process_job(
                                                    "job-1",
                                                    "item-123",
                                                    "scorecard-external",
                                                    "score-external",
                                                    receipt_handle=None,
                                                )
                                            )
