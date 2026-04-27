import sys
from pathlib import Path


METRICS_DIR = Path(__file__).resolve().parent
INFRA_DIR = METRICS_DIR.parents[1]
sys.path.insert(0, str(METRICS_DIR))
sys.path.insert(0, str(INFRA_DIR))

from handler import determine_record_type
from stacks.metrics_aggregation_stack import METRICS_STREAM_CONFIGS, METRICS_TABLE_TYPES
from stacks.shared.amplify_discovery import METRICS_TABLE_PATTERNS


def test_procedure_streams_are_classified_as_procedures():
    arn = "arn:aws:dynamodb:us-west-2:123456789012:table/Procedure-abc123/stream/2026-04-27T00:00:00.000"

    assert determine_record_type(arn) == "procedures"


def test_metrics_stack_subscribes_to_procedure_table_stream():
    assert "procedure" in METRICS_TABLE_TYPES
    assert METRICS_STREAM_CONFIGS["procedure"] == {"batch_size": 1, "batch_window": 15}


def test_amplify_discovery_includes_procedure_table():
    assert METRICS_TABLE_PATTERNS["procedure"] == "Procedure"
