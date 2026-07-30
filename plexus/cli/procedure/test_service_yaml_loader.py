import pytest
from unittest.mock import Mock, patch

from plexus.cli.procedure.service import ProcedureService
from plexus.cli.procedure.tactus_adapters.storage import ProcedureArtifactStorageError


def test_get_procedure_yaml_loads_verified_code_artifact_when_metadata_is_dict():
    client = Mock()
    service = ProcedureService(client)

    procedure = Mock()
    procedure.code = None
    procedure.metadata = {
        "code_s3_key": "procedures/proc-1/code.tac",
        "code_artifact": {
            "_s3_key": "procedures/proc-1/code.tac",
            "sha256": "a" * 64,
            "size_bytes": 57,
            "content_type": "text/plain",
        },
    }
    procedure.parentProcedureId = None
    procedure.templateId = None
    procedure.accountId = "acc-1"

    with patch(
        "plexus.cli.procedure.service.Procedure.get_by_id",
        return_value=procedure,
    ), patch(
        "plexus.cli.procedure.tactus_adapters.storage.download_procedure_attachment",
        return_value=b"class: Tactus\nname: Test\nversion: 1.0.0\ncode: |\n  return {}",
    ) as download_mock:
        yaml_text = service.get_procedure_yaml("proc-1")

    assert yaml_text is not None
    assert "class: Tactus" in yaml_text
    download_mock.assert_called_once_with(
        client,
        "proc-1",
        "code.tac",
        procedure.metadata["code_artifact"],
        content_type="text/plain",
    )


def test_get_procedure_yaml_rejects_legacy_code_pointer_without_integrity_metadata():
    client = Mock()
    service = ProcedureService(client)
    procedure = Mock(code=None, metadata={"code_s3_key": "procedures/proc-1/code.tac"})
    procedure.parentProcedureId = None
    procedure.templateId = None
    procedure.accountId = "acc-1"

    with patch("plexus.cli.procedure.service.Procedure.get_by_id", return_value=procedure), pytest.raises(
        ProcedureArtifactStorageError,
        match="integrity",
    ):
        service.get_procedure_yaml("proc-1")
