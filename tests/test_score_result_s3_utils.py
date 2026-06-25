import json

import pytest
from botocore.exceptions import ClientError

from plexus.utils import score_result_s3_utils


def _not_found_error():
    return ClientError(
        {"Error": {"Code": "404", "Message": "Not Found"}},
        "HeadObject",
    )


def test_download_trace_items_path_falls_back_to_score_result_bucket(monkeypatch, tmp_path):
    calls = []
    local_path = tmp_path / "deepgram.json"

    class FakeS3Client:
        def download_file(self, *, Bucket, Key, Filename):
            calls.append((Bucket, Key))
            if Bucket == "datasource-bucket":
                raise _not_found_error()

            assert Bucket == "score-result-bucket"
            with open(Filename, "w") as f:
                json.dump({"results": {"channels": []}}, f)

    monkeypatch.setenv("DATASOURCES_BUCKET", "datasource-bucket")
    monkeypatch.setenv(
        "AMPLIFY_STORAGE_SCORERESULTATTACHMENTS_BUCKET_NAME",
        "score-result-bucket",
    )
    monkeypatch.setattr(score_result_s3_utils.boto3, "client", lambda service: FakeS3Client())

    content, returned_path = score_result_s3_utils.download_score_result_trace_file(
        "items/123/deepgram.json",
        str(local_path),
    )

    assert content == {"results": {"channels": []}}
    assert returned_path == str(local_path)
    assert calls == [
        ("datasource-bucket", "items/123/deepgram.json"),
        ("score-result-bucket", "items/123/deepgram.json"),
    ]


def test_download_trace_non_items_path_uses_score_result_bucket_only(monkeypatch, tmp_path):
    calls = []
    local_path = tmp_path / "trace.json"

    class FakeS3Client:
        def download_file(self, *, Bucket, Key, Filename):
            calls.append((Bucket, Key))
            with open(Filename, "w") as f:
                json.dump({"trace": []}, f)

    monkeypatch.setenv("DATASOURCES_BUCKET", "datasource-bucket")
    monkeypatch.setenv(
        "AMPLIFY_STORAGE_SCORERESULTATTACHMENTS_BUCKET_NAME",
        "score-result-bucket",
    )
    monkeypatch.setattr(score_result_s3_utils.boto3, "client", lambda service: FakeS3Client())

    content, returned_path = score_result_s3_utils.download_score_result_trace_file(
        "scoreresults/result-id/trace.json",
        str(local_path),
    )

    assert content == {"trace": []}
    assert returned_path == str(local_path)
    assert calls == [("score-result-bucket", "scoreresults/result-id/trace.json")]


def test_download_trace_items_path_does_not_fallback_on_non_not_found_error(
    monkeypatch,
    tmp_path,
):
    calls = []
    local_path = tmp_path / "deepgram.json"
    access_denied = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}},
        "HeadObject",
    )

    class FakeS3Client:
        def download_file(self, *, Bucket, Key, Filename):
            calls.append((Bucket, Key))
            raise access_denied

    monkeypatch.setenv("DATASOURCES_BUCKET", "datasource-bucket")
    monkeypatch.setenv(
        "AMPLIFY_STORAGE_SCORERESULTATTACHMENTS_BUCKET_NAME",
        "score-result-bucket",
    )
    monkeypatch.setattr(score_result_s3_utils.boto3, "client", lambda service: FakeS3Client())

    with pytest.raises(ClientError):
        score_result_s3_utils.download_score_result_trace_file(
            "items/123/deepgram.json",
            str(local_path),
        )

    assert calls == [("datasource-bucket", "items/123/deepgram.json")]
