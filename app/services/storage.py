from __future__ import annotations

import io
import uuid
from urllib.parse import urlparse

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

from app.config import get_settings


def _make_client():
    s = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=s.MINIO_ENDPOINT,
        aws_access_key_id=s.MINIO_ACCESS_KEY,
        aws_secret_access_key=s.MINIO_SECRET_KEY,
        config=Config(signature_version="s3v4"),
    )


def _ensure_bucket(client, bucket: str) -> None:
    try:
        client.head_bucket(Bucket=bucket)
    except ClientError:
        client.create_bucket(Bucket=bucket)


class StorageService:
    def __init__(self):
        self._settings = get_settings()
        self._bucket = self._settings.MINIO_BUCKET

    def _client(self):
        return _make_client()

    def upload_file(
        self,
        file_obj: io.IOBase,
        filename: str | None = None,
        content_type: str = "application/octet-stream",
    ) -> str:
        client = self._client()
        _ensure_bucket(client, self._bucket)
        key = filename or f"uploads/{uuid.uuid4()}"
        client.upload_fileobj(
            file_obj,
            self._bucket,
            key,
            ExtraArgs={"ContentType": content_type},
        )
        return f"s3://{self._bucket}/{key}"

    def download_file(self, uri: str) -> bytes:
        client = self._client()
        parsed = urlparse(uri)
        bucket = parsed.netloc
        key = parsed.path.lstrip("/")
        buf = io.BytesIO()
        client.download_fileobj(bucket, key, buf)
        return buf.getvalue()

    def get_presigned_url(self, uri: str, expires: int = 3600) -> str:
        client = self._client()
        parsed = urlparse(uri)
        bucket = parsed.netloc
        key = parsed.path.lstrip("/")
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires,
        )
