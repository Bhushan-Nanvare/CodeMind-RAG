"""
Edge-case tests that model differences between local in-memory Qdrant and Qdrant Cloud.

These tests do NOT call Qdrant Cloud. They validate that our client-side handling
is robust (e.g. point ID normalisation for cloud mode).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import MagicMock

import pytest


def _make_vdb(cloud_mode: bool):
    from services.vector_db import VectorDBClient

    vdb = VectorDBClient.__new__(VectorDBClient)
    vdb.client = MagicMock()
    vdb.collection_name = "x"
    vdb.dimension = 4
    vdb._available = True
    vdb._cloud_mode = cloud_mode
    return vdb


def test_cloud_mode_normalises_non_uuid_point_id():
    vdb = _make_vdb(cloud_mode=True)
    non_uuid = "a-auth-login"

    point_id = vdb._normalise_point_id(non_uuid)
    # Should become a stable UUID string.
    assert isinstance(point_id, str)
    assert point_id != non_uuid
    assert len(point_id) == 36


def test_cloud_mode_keeps_uuid_point_id():
    vdb = _make_vdb(cloud_mode=True)
    valid = "18ef7386-bda7-5ea8-9a5d-8aacac458ee4"
    assert vdb._normalise_point_id(valid) == valid


def test_non_cloud_mode_does_not_normalise():
    vdb = _make_vdb(cloud_mode=False)
    assert vdb._normalise_point_id("a-auth-login") == "a-auth-login"


def test_upsert_chunk_uses_normalised_id_in_cloud_mode():
    vdb = _make_vdb(cloud_mode=True)
    vdb.upsert_chunk("a-auth-login", [0.1, 0.2, 0.3, 0.4], {"repo_name": "r"})

    # Ensure qdrant_models.PointStruct got a UUID id (string with hyphens).
    args, kwargs = vdb.client.upsert.call_args
    points = kwargs["points"]
    assert len(points) == 1
    pid = str(points[0].id)
    assert pid != "a-auth-login"
    assert len(pid) == 36


def test_upsert_batch_normalises_ids_in_cloud_mode():
    vdb = _make_vdb(cloud_mode=True)
    batch = [
        ("a-auth-login", [0.1, 0.2, 0.3, 0.4], {"repo_name": "r"}),
        ("b-auth-middleware", [0.1, 0.2, 0.3, 0.4], {"repo_name": "r"}),
    ]
    vdb.upsert_chunks_batch(batch)
    args, kwargs = vdb.client.upsert.call_args
    points = kwargs["points"]
    assert len(points) == 2
    assert all(len(str(p.id)) == 36 for p in points)

