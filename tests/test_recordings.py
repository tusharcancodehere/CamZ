"""
tests/test_recordings.py

Comprehensive test suite for Recording Management (Phase 9):
- Single recording deletion
- Bulk recording deletion with partial failure handling
- Delete all recordings
- Path traversal validation on bulk endpoints
- Thread-safe storage service operations
- Empty directory handling
"""

import json
import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from backend.main import app
from backend.services import ConfigService, ServiceManager, StorageService


class TestRecordingManagement(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = Path(tempfile.mkdtemp(prefix="camz_test_rec_"))
        self.client = TestClient(app)

        self.manager = ServiceManager()
        self.manager.register(ConfigService)
        self.storage = StorageService(self.manager)
        self.storage.directory = self.tmp_dir

    def tearDown(self):
        if self.tmp_dir.is_dir():
            shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _create_mock_recording(self, rec_id: str) -> Path:
        """Helper to create dummy session files (.json, .mp4, .jpg)."""
        session_dir = self.tmp_dir / "2026-07-22"
        session_dir.mkdir(parents=True, exist_ok=True)
        json_path = session_dir / f"{rec_id}.json"
        video_path = session_dir / f"{rec_id}.mp4"
        thumb_path = session_dir / f"{rec_id}.jpg"

        meta = {
            "id": rec_id,
            "start_time": "2026-07-22T10:00:00.000",
            "duration_seconds": 10.0,
            "file_size_bytes": 10240,
            "resolution": "1280x720",
        }
        with open(json_path, "w") as f:
            json.dump(meta, f)
        video_path.write_bytes(b"dummy video data " * 100)
        thumb_path.write_bytes(b"dummy thumb data " * 10)

        return json_path

    def test_delete_single_recording_success(self):
        rec_id = "session_single_001"
        self._create_mock_recording(rec_id)

        res = self.storage.delete_recording_by_id(rec_id)
        self.assertTrue(res)

        json_paths = list(self.tmp_dir.glob(f"**/{rec_id}.json"))
        self.assertEqual(len(json_paths), 0)

    def test_delete_single_recording_not_found(self):
        res = self.storage.delete_recording_by_id("non_existent_id")
        self.assertFalse(res)

    def test_delete_recordings_bulk_success(self):
        id1 = "session_bulk_001"
        id2 = "session_bulk_002"
        self._create_mock_recording(id1)
        self._create_mock_recording(id2)

        result = self.storage.delete_recordings_bulk([id1, id2])
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["deleted_count"], 2)
        self.assertEqual(result["failed_count"], 0)
        self.assertEqual(result["failed_ids"], [])

    def test_delete_recordings_bulk_partial_failure(self):
        id1 = "session_bulk_exist"
        id2 = "session_bulk_missing"
        self._create_mock_recording(id1)

        result = self.storage.delete_recordings_bulk([id1, id2])
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["deleted_count"], 1)
        self.assertEqual(result["failed_count"], 1)
        self.assertEqual(result["failed_ids"], [id2])

    def test_delete_all_recordings(self):
        for i in range(5):
            self._create_mock_recording(f"session_all_{i:03d}")

        result = self.storage.delete_all_recordings()
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["deleted_count"], 5)
        self.assertEqual(result["failed_count"], 0)
        self.assertGreater(result["freed_bytes"], 0)

        # Check directory is empty
        remaining = list(self.tmp_dir.glob("**/*.json"))
        self.assertEqual(len(remaining), 0)

    def test_delete_all_recordings_empty_directory(self):
        result = self.storage.delete_all_recordings()
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["deleted_count"], 0)
        self.assertEqual(result["failed_count"], 0)
        self.assertEqual(result["freed_bytes"], 0)

    def test_concurrent_deletion_requests(self):
        """Verify thread-safety when multiple threads request deletion simultaneously."""
        for i in range(10):
            self._create_mock_recording(f"session_conc_{i:03d}")

        threads = []
        errors = []

        def worker(rec_id):
            try:
                self.storage.delete_recording_by_id(rec_id)
            except Exception as e:
                errors.append(e)

        for i in range(10):
            t = threading.Thread(target=worker, args=(f"session_conc_{i:03d}",))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0)
        self.assertEqual(len(list(self.tmp_dir.glob("**/*.json"))), 0)


class TestRecordingAPIRoutes(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    @patch("backend.main.service_manager")
    def test_bulk_delete_api_success(self, mock_service_manager):
        mock_storage = MagicMock()
        mock_storage.delete_recordings_bulk.return_value = {
            "status": "completed",
            "deleted_count": 2,
            "failed_count": 0,
            "failed_ids": [],
        }
        mock_service_manager.get.return_value = mock_storage

        r = self.client.request("DELETE", "/recordings/bulk", json={"ids": ["rec_1", "rec_2"]})
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["deleted_count"], 2)

    @patch("backend.main.service_manager")
    def test_bulk_delete_api_path_traversal_blocked(self, mock_service_manager):
        r = self.client.request("DELETE", "/recordings/bulk", json={"ids": ["../etc/passwd"]})
        self.assertEqual(r.status_code, 400)

    @patch("backend.main.service_manager")
    def test_delete_all_api_success(self, mock_service_manager):
        mock_storage = MagicMock()
        mock_storage.delete_all_recordings.return_value = {
            "status": "completed",
            "deleted_count": 10,
            "failed_count": 0,
            "freed_bytes": 1048576,
        }
        mock_service_manager.get.return_value = mock_storage

        r = self.client.request("DELETE", "/recordings/all")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["deleted_count"], 10)


if __name__ == "__main__":
    unittest.main()
