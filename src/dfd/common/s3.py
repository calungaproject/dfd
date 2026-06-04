"""S3 read/write utilities for conversation logs and artifacts."""

from __future__ import annotations

import gzip
import json
import logging

import boto3

logger = logging.getLogger(__name__)

_client = None


def init_s3(endpoint_url: str | None = None) -> None:
    """Initialize the module-level S3 client."""
    global _client
    kwargs: dict = {}
    if endpoint_url:
        kwargs["endpoint_url"] = endpoint_url
    _client = boto3.client("s3", **kwargs)


def _get_client():
    if _client is None:
        raise RuntimeError("S3 client not initialized — call init_s3() first")
    return _client


def read_file(bucket: str, s3_key: str) -> str | None:
    """Read a file from S3. Returns content as string, or None on error.

    Automatically decompresses .gz files.
    """
    try:
        response = _get_client().get_object(Bucket=bucket, Key=s3_key)
        raw = response["Body"].read()
        if s3_key.endswith(".gz"):
            raw = gzip.decompress(raw)
        text = raw.decode("utf-8", errors="replace")
        return text.replace("\x00", "")
    except Exception as e:
        logger.warning("Failed to read s3://%s/%s: %s", bucket, s3_key, e)
        return None


def write_json(bucket: str, s3_key: str, data: dict | list) -> bool:
    """Write a JSON object to S3. Returns True on success."""
    try:
        body = json.dumps(data, default=str, ensure_ascii=False).encode("utf-8")
        _get_client().put_object(
            Bucket=bucket, Key=s3_key, Body=body, ContentType="application/json"
        )
        return True
    except Exception as e:
        logger.error("Failed to write s3://%s/%s: %s", bucket, s3_key, e)
        return False


def read_json(bucket: str, s3_key: str) -> dict | list | None:
    """Read a JSON file from S3. Returns parsed object, or None on error."""
    text = read_file(bucket, s3_key)
    if text is None:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.warning("Invalid JSON in s3://%s/%s: %s", bucket, s3_key, e)
        return None
