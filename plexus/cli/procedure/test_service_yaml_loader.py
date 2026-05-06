from unittest.mock import Mock, patch

from plexus.cli.procedure.service import ProcedureService


def test_get_procedure_yaml_loads_s3_code_when_metadata_is_dict():
    client = Mock()
    service = ProcedureService(client)

    procedure = Mock()
    procedure.code = None
    procedure.metadata = {"code_s3_key": "procedures/proc-1/code.tac"}
    procedure.parentProcedureId = None
    procedure.templateId = None
    procedure.accountId = "acc-1"

    with patch(
        "plexus.cli.procedure.service.Procedure.get_by_id",
        return_value=procedure,
    ), patch(
        "plexus.reports.s3_utils.download_procedure_code",
        return_value="class: Tactus\nname: Test\nversion: 1.0.0\ncode: |\n  return {}",
    ) as download_mock:
        yaml_text = service.get_procedure_yaml("proc-1")

    assert yaml_text is not None
    assert "class: Tactus" in yaml_text
    download_mock.assert_called_once_with("proc-1", ["procedures/proc-1/code.tac"])
