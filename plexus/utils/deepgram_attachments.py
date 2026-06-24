import json
import logging
import os
from typing import Any, Dict, List, Optional


def is_deepgram_attachment_key(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False

    filename = os.path.basename(value).lower()
    return "deepgram" in filename and filename.endswith(".json")


def deepgram_attachment_keys_from_metadata(metadata: Dict[str, Any]) -> List[str]:
    if not isinstance(metadata, dict):
        return []

    keys: List[str] = []

    def add_key(value: Any, *, require_deepgram_filename: bool = True) -> None:
        if not isinstance(value, str) or not value.strip():
            return

        key = value.strip()
        if require_deepgram_filename and not is_deepgram_attachment_key(key):
            return
        if key not in keys:
            keys.append(key)

    for pointer_key in (
        "deepgram_attachment_key",
        "deepgramAttachmentKey",
        "deepgram_s3_key",
        "deepgramS3Key",
    ):
        add_key(metadata.get(pointer_key), require_deepgram_filename=False)

    for pointer_key in ("attachment_key", "attachmentKey"):
        add_key(metadata.get(pointer_key))

    for collection_key in ("attachedFiles", "attached_files", "attachments"):
        value = metadata.get(collection_key)
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                add_key(value)
                continue

        if not isinstance(value, list):
            continue

        for item in value:
            if isinstance(item, str):
                add_key(item)
            elif isinstance(item, dict):
                for item_key in (
                    "key",
                    "path",
                    "s3_key",
                    "s3Key",
                    "attachment_key",
                    "attachmentKey",
                ):
                    add_key(item.get(item_key))

    return keys


def load_deepgram_from_attachment_metadata(
    metadata: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    attachment_keys = deepgram_attachment_keys_from_metadata(metadata)
    if not attachment_keys:
        return None

    from plexus.utils.score_result_s3_utils import download_score_result_trace_file

    for attachment_key in attachment_keys:
        try:
            deepgram_data, _ = download_score_result_trace_file(attachment_key)
            if deepgram_data:
                logging.debug("Loaded deepgram data from item attachment %s", attachment_key)
                return deepgram_data
        except Exception as e:
            logging.debug("Could not load deepgram data from %s: %s", attachment_key, e)

    return None
