import sys
import importlib.util
from pathlib import Path


METRICS_DIR = Path(__file__).resolve().parent
INFRA_DIR = METRICS_DIR.parents[1]
sys.path.insert(0, str(METRICS_DIR))
sys.path.insert(0, str(INFRA_DIR))

from handler import determine_record_type


def load_module_from_path(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


metrics_config = load_module_from_path(
    "metrics_aggregation_config",
    INFRA_DIR / "stacks" / "metrics_aggregation_config.py",
)
amplify_discovery = load_module_from_path(
    "amplify_discovery",
    INFRA_DIR / "stacks" / "shared" / "amplify_discovery.py",
)

METRICS_STREAM_CONFIGS = metrics_config.METRICS_STREAM_CONFIGS
METRICS_TABLE_TYPES = metrics_config.METRICS_TABLE_TYPES
METRICS_TABLE_PATTERNS = amplify_discovery.METRICS_TABLE_PATTERNS


def test_procedure_streams_are_classified_as_procedures():
    arn = "arn:aws:dynamodb:us-west-2:123456789012:table/Procedure-abc123/stream/2026-04-27T00:00:00.000"

    assert determine_record_type(arn) == "procedures"


def test_metrics_stack_subscribes_to_procedure_table_stream():
    assert "procedure" in METRICS_TABLE_TYPES
    assert METRICS_STREAM_CONFIGS["procedure"] == {"batch_size": 1, "batch_window": 15}


def test_amplify_discovery_includes_procedure_table():
    assert METRICS_TABLE_PATTERNS["procedure"] == "Procedure"


def test_feedback_item_streams_are_classified_as_feedback_items():
    arn = "arn:aws:dynamodb:us-west-2:123456789012:table/FeedbackItem-abc123/stream/2026-04-29T00:00:00.000"

    assert determine_record_type(arn) == "feedbackItems"


def test_metrics_stack_subscribes_to_feedback_item_table_stream():
    assert "feedbackitem" in METRICS_TABLE_TYPES
    assert METRICS_STREAM_CONFIGS["feedbackitem"] == {"batch_size": 10, "batch_window": 15}


def test_amplify_discovery_includes_feedback_item_table():
    assert METRICS_TABLE_PATTERNS["feedbackitem"] == "FeedbackItem"
