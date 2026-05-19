"""
Wrapper boto3 pour MinIO/S3 — upload multipart presigné des orthophotos.

Architecture :

    Browser ── presigned PUT chunks ─▶ MinIO  (gros volumes, jamais Django)
       │
       └── POST /init  +  POST /complete ─▶ Django  (control plane)
                                              │
                                              ▼
                                          Celery télécharge depuis MinIO
                                          pour le pipeline GDAL.

Le **endpoint interne** (`S3_ENDPOINT_URL`, ex. http://minio:9000) sert à
Django/Celery pour les appels de plan de contrôle (initiate, complete,
download), tandis que le **endpoint externe** (`S3_ENDPOINT_URL_EXTERNAL`,
ex. https://s3.example.com) est embarqué dans les URLs signées renvoyées
au navigateur pour les PUT directs.
"""

from __future__ import annotations

import logging
from typing import List

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from django.conf import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------


def _s3_client(*, external: bool = False):
    """
    Construit un client boto3 S3 pour MinIO.

    - `external=False` (défaut) : utilisé par Django / Celery côté serveur,
      pour parler à MinIO via le réseau Docker (http://minio:9000).
    - `external=True` : utilisé uniquement pour générer des presigned URLs
      destinées au navigateur — `endpoint_url` doit être l'URL publique
      (https://s3.example.com) sinon Chrome refuse la requête (origin
      différente, ou TLS manquant).
    """
    endpoint = settings.S3_ENDPOINT_URL_EXTERNAL if external else settings.S3_ENDPOINT_URL
    if not endpoint:
        raise RuntimeError("S3_ENDPOINT_URL n'est pas configuré.")
    if not settings.S3_ACCESS_KEY or not settings.S3_SECRET_KEY:
        raise RuntimeError("S3_ACCESS_KEY/S3_SECRET_KEY manquants.")

    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name=settings.S3_REGION,
        # signature_version=s3v4 obligatoire pour MinIO ; addressing_style=path
        # car MinIO ne sait pas faire le virtual-host par défaut.
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            retries={"max_attempts": 3, "mode": "standard"},
        ),
    )


# ---------------------------------------------------------------------
# Bootstrap / CORS
# ---------------------------------------------------------------------


def ensure_bucket_and_cors() -> None:
    """
    Crée le bucket s'il manque + applique la CORS policy nécessaire
    pour que le navigateur puisse faire des PUT depuis le front et
    lire le header `ETag` retourné.
    """
    cli = _s3_client()
    bucket = settings.S3_BUCKET
    try:
        cli.head_bucket(Bucket=bucket)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in {"404", "NoSuchBucket", "NotFound"}:
            cli.create_bucket(Bucket=bucket)
            logger.info("Bucket S3 créé : %s", bucket)
        else:
            raise

    cors = {
        "CORSRules": [
            {
                "AllowedHeaders": ["*"],
                "AllowedMethods": ["PUT", "GET", "POST", "HEAD"],
                # Origines qui peuvent uploader directement.
                "AllowedOrigins": _allowed_origins_for_cors(),
                # ETag est nécessaire côté client pour CompleteMultipartUpload.
                "ExposeHeaders": ["ETag", "x-amz-version-id"],
                "MaxAgeSeconds": 3000,
            }
        ]
    }
    try:
        cli.put_bucket_cors(Bucket=bucket, CORSConfiguration=cors)
        logger.info("CORS appliquée sur %s : %s", bucket, cors["CORSRules"][0]["AllowedOrigins"])
    except ClientError as exc:
        logger.warning("CORS non appliquée : %s", exc)


def _allowed_origins_for_cors() -> List[str]:
    """
    Retourne la liste des origines acceptées pour la CORS du bucket.
    Combine ALLOWED_HOSTS + CSRF_TRUSTED_ORIGINS, en https/http si pertinent.
    """
    origins = set()
    for host in getattr(settings, "ALLOWED_HOSTS", []):
        if host and host not in {"*"}:
            origins.add(f"https://{host}")
            origins.add(f"http://{host}")
    for url in getattr(settings, "CSRF_TRUSTED_ORIGINS", []):
        if url:
            origins.add(url)
    if not origins:
        origins.add("*")
    return sorted(origins)


# ---------------------------------------------------------------------
# Multipart upload
# ---------------------------------------------------------------------


def initiate_multipart_upload(key: str, content_type: str = "application/octet-stream") -> str:
    """Démarre un multipart upload S3 et renvoie l'`UploadId`."""
    cli = _s3_client()
    resp = cli.create_multipart_upload(
        Bucket=settings.S3_BUCKET,
        Key=key,
        ContentType=content_type,
    )
    return resp["UploadId"]


def presign_part_url(key: str, upload_id: str, part_number: int) -> str:
    """
    URL signée pour `PUT` un chunk donné. À donner au navigateur, qui PUT
    directement vers MinIO sans repasser par Django.
    """
    cli = _s3_client(external=True)
    return cli.generate_presigned_url(
        ClientMethod="upload_part",
        Params={
            "Bucket": settings.S3_BUCKET,
            "Key": key,
            "UploadId": upload_id,
            "PartNumber": part_number,
        },
        ExpiresIn=settings.S3_PRESIGNED_EXPIRY,
        HttpMethod="PUT",
    )


def complete_multipart_upload(key: str, upload_id: str, parts: List[dict]) -> dict:
    """
    Termine un multipart upload. `parts` est la liste retournée par le
    navigateur : [{PartNumber: 1, ETag: "..."}, ...].
    """
    cli = _s3_client()
    # On trie par PartNumber au cas où le client envoie en désordre.
    sorted_parts = sorted(parts, key=lambda p: int(p["PartNumber"]))
    return cli.complete_multipart_upload(
        Bucket=settings.S3_BUCKET,
        Key=key,
        UploadId=upload_id,
        MultipartUpload={"Parts": [
            {"PartNumber": int(p["PartNumber"]), "ETag": p["ETag"]} for p in sorted_parts
        ]},
    )


def abort_multipart_upload(key: str, upload_id: str) -> None:
    """Annule un multipart upload (libère les parts déjà uploadées)."""
    cli = _s3_client()
    try:
        cli.abort_multipart_upload(Bucket=settings.S3_BUCKET, Key=key, UploadId=upload_id)
    except ClientError as exc:
        logger.warning("Abort multipart %s/%s échoué : %s", key, upload_id, exc)


# ---------------------------------------------------------------------
# Lecture (pour le pipeline Celery)
# ---------------------------------------------------------------------


def download_to_path(key: str, dest_path: str) -> None:
    """Télécharge l'objet S3 dans le filesystem local."""
    cli = _s3_client()
    cli.download_file(settings.S3_BUCKET, key, str(dest_path))


def head_object(key: str) -> dict:
    """Renvoie les métadonnées (taille, contentType…) sans télécharger."""
    cli = _s3_client()
    return cli.head_object(Bucket=settings.S3_BUCKET, Key=key)


def presigned_get_url(key: str, expires: int = 3600) -> str:
    """URL signée GET (pour télécharger directement depuis le navigateur)."""
    cli = _s3_client(external=True)
    return cli.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": settings.S3_BUCKET, "Key": key},
        ExpiresIn=expires,
    )
