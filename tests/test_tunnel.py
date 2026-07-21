import unittest
from unittest.mock import MagicMock, patch
import time
import threading
from fastapi.testclient import TestClient

from backend.config import config
from backend.services import (
    ServiceManager,
    ConfigService,
    TunnelService,
    TunnelStartedEvent,
    TunnelConnectedEvent,
    TunnelDisconnectedEvent,
    TunnelRestartedEvent,
)
from backend.main import app


class TestTunnelService(unittest.TestCase):

    def setUp(self):
        # Create a clean ServiceManager and mock dependencies
        self.manager = ServiceManager()
        self.manager.register(ConfigService)
        self.config = self.manager.get(ConfigService).config

        # Override config parameters for testing
        self.config.TUNNEL_ENABLED = True
        self.config.TUNNEL_AUTOSTART = False
        self.config.TUNNEL_TOKEN = ""
        self.config.TUNNEL_HOSTNAME = ""
        self.config.TUNNEL_SHARE_LOCALHOST = "http://127.0.0.1:8000"
        self.config.TUNNEL_INSTALL_IF_MISSING = False

        self.service = TunnelService(self.manager)
        self.manager._services[TunnelService] = self.service

    def tearDown(self):
        self.service.stop()

    @patch("shutil.which")
    def test_binary_detection_missing(self, mock_which):
        # Mock which to return None (missing cloudflared)
        mock_which.return_value = None
        self.assertFalse(self.service._check_and_install_binary())

    @patch("shutil.which")
    def test_binary_detection_present(self, mock_which):
        # Mock which to return a valid path
        mock_which.return_value = "/usr/bin/cloudflared"
        self.assertTrue(self.service._check_and_install_binary())

    @patch("shutil.which")
    @patch("subprocess.Popen")
    def test_service_start_stop(self, mock_popen, mock_which):
        mock_which.return_value = "/usr/bin/cloudflared"
        
        # Mock the process stdout readline to return empty and simulate process exit
        mock_process = MagicMock()
        mock_process.stdout.readline.return_value = ""
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process

        # Verify events are triggered
        event_captured = threading.Event()
        def on_started(event):
            event_captured.set()
        self.manager.event_bus.subscribe(TunnelStartedEvent, on_started)

        self.service.start()
        self.assertTrue(event_captured.wait(timeout=2.0))
        self.service.stop()
        self.assertFalse(self.service.is_active())

    @patch("shutil.which")
    @patch("subprocess.Popen")
    def test_quick_tunnel_url_parsing(self, mock_popen, mock_which):
        mock_which.return_value = "/usr/bin/cloudflared"
        
        # Simulate log output containing trycloudflare URL
        mock_process = MagicMock()
        lines = [
            "2026-07-21 INF Your quick tunnel has been created! Visit it at:",
            "2026-07-21 INF https://camz-test-url.trycloudflare.com",
            "2026-07-21 INF Connection registered connectionID=0",
        ]
        iterator = iter(lines)
        done_reading = threading.Event()
        def mock_readline():
            try:
                return next(iterator)
            except StopIteration:
                done_reading.wait()
                return ""
        
        mock_process.stdout.readline.side_effect = mock_readline
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process

        # Subcribe to connection confirmation
        conn_captured = threading.Event()
        def on_connected(event):
            conn_captured.set()
        self.manager.event_bus.subscribe(TunnelConnectedEvent, on_connected)

        self.service.start()
        # Wait for log lines processing thread
        conn_captured.wait(timeout=2.0)
        
        status = self.service.get_status()
        self.assertEqual(status["url"], "https://camz-test-url.trycloudflare.com")
        self.assertTrue(status["running"])
        
        done_reading.set()
        self.service.stop()

    @patch("shutil.which")
    @patch("subprocess.Popen")
    def test_exponential_backoff_recovery(self, mock_popen, mock_which):
        mock_which.return_value = "/usr/bin/cloudflared"
        
        # Process exits immediately with failure
        mock_process = MagicMock()
        mock_process.stdout.readline.return_value = ""
        mock_process.wait.return_value = 1
        mock_popen.return_value = mock_process

        # Fast forward wait in supervisor to avoid slow tests
        restarted_captured = threading.Event()
        def on_restarted(event):
            if event.attempt >= 2:
                restarted_captured.set()
        self.manager.event_bus.subscribe(TunnelRestartedEvent, on_restarted)

        # Mock the shutdown event wait to speed up the loop execution
        with patch.object(self.service._shutdown_event, 'wait', return_value=True):
            self.service.start()
            restarted_captured.wait(timeout=2.0)
            
        status = self.service.get_status()
        self.assertGreaterEqual(status["crash_count"], 2)
        self.service.stop()


class TestTunnelAPI(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    @patch("backend.main.service_manager")
    def test_tunnel_endpoints(self, mock_service_manager):
        # Mock TunnelService inside service manager
        mock_svc = MagicMock()
        mock_svc.get_status.return_value = {
            "enabled": True,
            "provider": "cloudflare",
            "running": True,
            "url": "https://test.trycloudflare.com",
            "uptime_seconds": 10,
            "latency_ms": 12.5,
            "crash_count": 0
        }
        mock_service_manager.get.return_value = mock_svc

        # 1. Test status route
        r = self.client.get("/tunnel/status")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["url"], "https://test.trycloudflare.com")

        # 2. Test restart route
        r = self.client.post("/tunnel/restart")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "restarted")

        # 3. Test start route
        r = self.client.post("/tunnel/start")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "started")

        # 4. Test stop route
        r = self.client.post("/tunnel/stop")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "stopped")
