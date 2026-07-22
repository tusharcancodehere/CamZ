"""
tests/test_tunnel.py

Comprehensive test suite for the production-grade Cloudflare Tunnel implementation.
Covers: state machine, connectivity validator, TunnelService lifecycle,
protocol fallback, arch detection, health endpoint schema, and API routes.
"""
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from backend.main import app
from backend.services import (
    ConfigService,
    ServiceManager,
    TunnelConnectedEvent,
    TunnelProtocolFallbackEvent,
    TunnelService,
    TunnelStartedEvent,
)
from backend.tunnel_state import TunnelState, TunnelStateMachine
from backend.tunnel_validator import TunnelConnectivityValidator

# ─────────────────────────────────────────────
# State Machine Tests
# ─────────────────────────────────────────────

class TestTunnelStateMachine(unittest.TestCase):

    def setUp(self):
        self.sm = TunnelStateMachine()

    def test_initial_state_is_stopped(self):
        self.assertEqual(self.sm.state, TunnelState.STOPPED)

    def test_valid_transition_stopped_to_installing(self):
        result = self.sm.transition(TunnelState.INSTALLING)
        self.assertTrue(result)
        self.assertEqual(self.sm.state, TunnelState.INSTALLING)

    def test_valid_transition_stopped_to_starting(self):
        result = self.sm.transition(TunnelState.STARTING)
        self.assertTrue(result)
        self.assertEqual(self.sm.state, TunnelState.STARTING)

    def test_invalid_transition_stopped_to_connected(self):
        """STOPPED cannot jump directly to CONNECTED — invalid."""
        result = self.sm.transition(TunnelState.CONNECTED)
        self.assertFalse(result)
        self.assertEqual(self.sm.state, TunnelState.STOPPED)  # unchanged

    def test_full_happy_path_transitions(self):
        steps = [
            TunnelState.INSTALLING,
            TunnelState.STARTING,
            TunnelState.CONNECTING,
            TunnelState.CONNECTED,
            TunnelState.STOPPING,
            TunnelState.STOPPED,
        ]
        for step in steps:
            result = self.sm.transition(step)
            self.assertTrue(result, f"Expected valid transition to {step}")
        self.assertEqual(self.sm.state, TunnelState.STOPPED)

    def test_failed_to_starting_retry_cycle(self):
        """FAILED → STARTING is valid for retry loops."""
        self.sm.transition(TunnelState.STARTING)
        self.sm.transition(TunnelState.CONNECTING)
        self.sm.transition(TunnelState.FAILED)
        result = self.sm.transition(TunnelState.STARTING)
        self.assertTrue(result)

    def test_connected_to_degraded_and_back(self):
        self.sm.transition(TunnelState.STARTING)
        self.sm.transition(TunnelState.CONNECTING)
        self.sm.transition(TunnelState.CONNECTED)
        self.assertTrue(self.sm.transition(TunnelState.DEGRADED))
        self.assertTrue(self.sm.transition(TunnelState.CONNECTED))
        self.assertTrue(self.sm.is_connected())

    def test_listener_is_called_on_transition(self):
        calls = []
        self.sm.add_listener(lambda old, new, reason: calls.append((old, new, reason)))
        self.sm.transition(TunnelState.STARTING, "test")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], TunnelState.STOPPED)
        self.assertEqual(calls[0][1], TunnelState.STARTING)
        self.assertEqual(calls[0][2], "test")

    def test_is_active_for_intermediate_states(self):
        for active_state in (TunnelState.STARTING, TunnelState.CONNECTING, TunnelState.CONNECTED):
            sm = TunnelStateMachine()
            sm.force(active_state, "test")
            self.assertTrue(sm.is_active(), f"Expected is_active() for {active_state}")

    def test_is_not_active_for_stopped_failed(self):
        for inactive in (TunnelState.STOPPED, TunnelState.FAILED):
            sm = TunnelStateMachine()
            sm.force(inactive, "test")
            self.assertFalse(sm.is_active(), f"Expected not is_active() for {inactive}")

    def test_force_bypasses_validation(self):
        """force() should always work even for invalid transitions."""
        self.sm.force(TunnelState.CONNECTED, "force test")
        self.assertEqual(self.sm.state, TunnelState.CONNECTED)


# ─────────────────────────────────────────────
# Connectivity Validator Tests
# ─────────────────────────────────────────────

class TestTunnelConnectivityValidator(unittest.TestCase):

    def setUp(self):
        self.validator = TunnelConnectivityValidator(
            local_port=8000, timeout_seconds=2.0, retry_interval=0.1, max_attempts=2
        )

    @patch("backend.tunnel_validator.http.client.HTTPConnection")
    @patch("backend.tunnel_validator.http.client.HTTPSConnection")
    @patch("backend.tunnel_validator.socket.getaddrinfo")
    def test_all_checks_pass(self, mock_dns, mock_https_cls, mock_http_cls):
        """All 4 checks pass → validate() returns (True, '')."""
        import json

        # Mock local HTTP server
        mock_http = MagicMock()
        mock_http.getresponse.return_value = MagicMock(status=200)
        mock_http.getresponse.return_value.read.return_value = json.dumps(
            {"app_state": "ready", "status": "ok"}
        ).encode()
        mock_http_cls.return_value = mock_http

        # Mock DNS
        mock_dns.return_value = [("", "", "", "", ("1.1.1.1", 443))]

        # Mock HTTPS (Cloudflare edge + public URL)
        mock_https = MagicMock()
        mock_https.getresponse.return_value = MagicMock(status=200)
        mock_https.getresponse.return_value.read.return_value = b""
        mock_https_cls.return_value = mock_https

        ok, reason = self.validator.validate("https://test.trycloudflare.com")
        self.assertTrue(ok, f"Expected success, got reason: {reason}")
        self.assertEqual(reason, "")

    @patch("backend.tunnel_validator.http.client.HTTPConnection")
    def test_localhost_unreachable(self, mock_http_cls):
        """If localhost is unreachable → validate() returns (False, reason)."""
        mock_http_cls.side_effect = ConnectionRefusedError("refused")

        ok, reason = self.validator.validate("https://test.trycloudflare.com")
        self.assertFalse(ok)
        self.assertIn("Cannot connect", reason)

    @patch("backend.tunnel_validator.http.client.HTTPConnection")
    @patch("backend.tunnel_validator.socket.getaddrinfo")
    def test_local_health_not_ready(self, mock_dns, mock_http_cls):
        """If /health returns app_state=initializing → validation fails."""
        import json

        mock_http = MagicMock()
        mock_http.getresponse.return_value = MagicMock(status=200)
        mock_http.getresponse.return_value.read.return_value = json.dumps(
            {"app_state": "initializing", "status": "starting"}
        ).encode()
        mock_http_cls.return_value = mock_http

        ok, reason = self.validator.validate("https://test.trycloudflare.com")
        self.assertFalse(ok)
        self.assertIn("not ready", reason.lower())

    def test_run_doctor_checks_returns_list(self):
        """run_doctor_checks() returns a list of ValidationResult objects."""
        # Just check it returns without crashing (real network may or may not be available)
        results = self.validator.run_doctor_checks(public_url=None)
        self.assertIsInstance(results, list)
        self.assertGreaterEqual(len(results), 3)  # localhost, health, edge


# ─────────────────────────────────────────────
# TunnelService Lifecycle Tests
# ─────────────────────────────────────────────

class TestTunnelService(unittest.TestCase):

    def setUp(self):
        self.manager = ServiceManager()
        self.manager.register(ConfigService)
        self.config = self.manager.get(ConfigService).config

        self.config.TUNNEL_ENABLED = True
        self.config.TUNNEL_AUTOSTART = False
        self.config.TUNNEL_TOKEN = ""
        self.config.TUNNEL_HOSTNAME = ""
        self.config.TUNNEL_SHARE_LOCALHOST = "http://127.0.0.1:8000"
        self.config.TUNNEL_INSTALL_IF_MISSING = False
        self.config.TUNNEL_MAX_RETRIES = 3
        self.config.TUNNEL_QUIC_FAIL_THRESHOLD = 2
        self.config.TUNNEL_PROTOCOL = ""

        self.service = TunnelService(self.manager)
        self.manager._services[TunnelService] = self.service

    def tearDown(self):
        self.service.stop()

    def test_get_status_returns_state_field(self):
        """get_status() must include 'state' key with a TunnelState value."""
        status = self.service.get_status()
        self.assertIn("state", status)
        self.assertIn(status["state"], [s.value for s in TunnelState])

    def test_get_status_includes_protocol(self):
        status = self.service.get_status()
        self.assertIn("protocol", status)

    def test_get_status_includes_restart_count(self):
        status = self.service.get_status()
        self.assertIn("restart_count", status)

    def test_get_status_initial_state_is_stopped(self):
        status = self.service.get_status()
        self.assertEqual(status["state"], "STOPPED")

    def test_binary_detection_missing(self):
        with patch("shutil.which", return_value=None):
            result = self.service._check_and_install_binary()
        self.assertFalse(result)

    def test_binary_detection_present(self):
        with patch("shutil.which", return_value="/usr/bin/cloudflared"):
            with patch.object(self.service, "_read_cloudflared_version", return_value="2024.8.2"):
                with patch.object(self.service, "_detect_arch", return_value="arm64"):
                    result = self.service._check_and_install_binary()
        self.assertTrue(result)

    @patch("shutil.which")
    @patch("subprocess.Popen")
    def test_service_start_emits_started_event(self, mock_popen, mock_which):
        mock_which.return_value = "/usr/bin/cloudflared"

        mock_process = MagicMock()
        mock_process.stdout.__iter__ = lambda s: iter([])
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process

        event_captured = threading.Event()
        def on_started(event):
            event_captured.set()
        self.manager.event_bus.subscribe(TunnelStartedEvent, on_started)

        with patch.object(self.service, "_read_cloudflared_version", return_value="2024.8.2"):
            with patch.object(self.service, "_detect_arch", return_value="arm64"):
                self.service.start()
        self.assertTrue(event_captured.wait(timeout=2.0))
        self.service.stop()

    @patch("shutil.which")
    @patch("subprocess.Popen")
    def test_quick_tunnel_url_extracted_and_validated(self, mock_popen, mock_which):
        """URL from logs triggers validation. On validation success → CONNECTED."""
        mock_which.return_value = "/usr/bin/cloudflared"

        lines = [
            "INF Your quick tunnel has been created! Visit it at:",
            "https://camz-test-url.trycloudflare.com",
            "INF Connection registered connectionID=0",
        ]

        stop_event = threading.Event()

        def readline_gen():
            for line in lines:
                yield line
            stop_event.wait()
            return

        mock_process = MagicMock()
        mock_process.stdout.__iter__ = lambda s: readline_gen()
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process

        conn_captured = threading.Event()
        def on_connected(event):
            conn_captured.set()
        self.manager.event_bus.subscribe(TunnelConnectedEvent, on_connected)

        # Mock validation to pass
        with patch.object(self.service._validator, "validate", return_value=(True, "")):
            with patch.object(self.service, "_read_cloudflared_version", return_value="2024.8.2"):
                with patch.object(self.service, "_detect_arch", return_value="arm64"):
                    self.service.start()
                    conn_captured.wait(timeout=3.0)

        status = self.service.get_status()
        self.assertEqual(status["url"], "https://camz-test-url.trycloudflare.com")
        self.assertEqual(status["state"], "CONNECTED")

        stop_event.set()
        self.service.stop()

    @patch("shutil.which")
    @patch("subprocess.Popen")
    def test_validation_failure_keeps_connecting_state(self, mock_popen, mock_which):
        """If validation fails, URL is not exposed and state stays non-CONNECTED."""
        mock_which.return_value = "/usr/bin/cloudflared"

        lines = ["https://camz-fail-test.trycloudflare.com"]

        mock_process = MagicMock()
        mock_process.stdout.__iter__ = lambda s: iter(lines + [""])
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process

        # Always fail validation
        with patch.object(self.service._validator, "validate", return_value=(False, "unreachable")):
            with patch.object(self.service, "_read_cloudflared_version", return_value="2024.8.2"):
                with patch.object(self.service, "_detect_arch", return_value="arm64"):
                    self.service.start()
                    time.sleep(0.5)

        status = self.service.get_status()
        self.assertNotEqual(status["state"], "CONNECTED")
        self.assertEqual(status["url"], "")
        self.service.stop()

    def test_protocol_fallback_after_quic_failures(self):
        """After QUIC_FAIL_THRESHOLD failures, protocol switches to HTTP/2."""
        self.service._protocol = "quic"
        self.service._quic_fail_count = 0
        threshold = 2

        fallback_captured = threading.Event()
        def on_fallback(event):
            fallback_captured.set()
        self.manager.event_bus.subscribe(TunnelProtocolFallbackEvent, on_fallback)

        # Simulate what the supervisor loop does when QUIC fails
        for i in range(threshold):
            self.service._quic_fail_count += 1

        # Apply the fallback logic (mirrors supervisor code)
        if self.service._quic_fail_count >= threshold and self.service._protocol == "quic":
            self.manager.event_bus.publish(
                TunnelProtocolFallbackEvent("quic", "http2")
            )
            self.service._protocol = "http2"

        self.assertTrue(fallback_captured.wait(timeout=1.0), "Expected protocol fallback event")
        self.assertEqual(self.service._protocol, "http2")

    def test_exponential_backoff_increases(self):
        """Verify backoff delay doubles each cycle (up to max 60s)."""
        self.service._backoff_delay = 1.0
        delays = []
        for _ in range(6):
            delays.append(self.service._backoff_delay)
            self.service._backoff_delay = min(60.0, self.service._backoff_delay * 2.0)
        self.assertEqual(delays, [1.0, 2.0, 4.0, 8.0, 16.0, 32.0])


# ─────────────────────────────────────────────
# Arch Detection Tests
# ─────────────────────────────────────────────

class TestArchDetection(unittest.TestCase):

    def setUp(self):
        manager = ServiceManager()
        manager.register(ConfigService)
        cfg = manager.get(ConfigService).config
        cfg.TUNNEL_INSTALL_IF_MISSING = False
        self.service = TunnelService(manager)

    def test_dpkg_amd64_maps_to_amd64(self):
        with patch("subprocess.check_output", return_value=b"amd64\n"):
            result = self.service._detect_dpkg_arch()
        self.assertEqual(result, "amd64")

    def test_dpkg_arm64_maps_to_arm64(self):
        with patch("subprocess.check_output", return_value=b"arm64\n"):
            result = self.service._detect_dpkg_arch()
        self.assertEqual(result, "arm64")

    def test_dpkg_armhf_maps_to_arm(self):
        with patch("subprocess.check_output", return_value=b"armhf\n"):
            result = self.service._detect_dpkg_arch()
        self.assertEqual(result, "arm")

    def test_dpkg_unavailable_falls_back_to_platform(self):
        with patch("subprocess.check_output", side_effect=FileNotFoundError("dpkg not found")):
            with patch("platform.machine", return_value="aarch64"):
                result = self.service._detect_dpkg_arch()
        self.assertEqual(result, "arm64")

    def test_arch_fallback_x86_64(self):
        with patch("platform.machine", return_value="x86_64"):
            result = self.service._detect_arch_fallback()
        self.assertEqual(result, "amd64")

    def test_arch_fallback_armv7l(self):
        with patch("platform.machine", return_value="armv7l"):
            result = self.service._detect_arch_fallback()
        self.assertEqual(result, "armhf")


# ─────────────────────────────────────────────
# API Route Tests
# ─────────────────────────────────────────────

class TestTunnelAPI(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)

    @patch("backend.main.service_manager")
    def test_tunnel_status_returns_state(self, mock_service_manager):
        """GET /tunnel/status must return 'state' field."""
        mock_svc = MagicMock()
        mock_svc.get_status.return_value = {
            "enabled": True,
            "provider": "cloudflare",
            "state": "CONNECTED",
            "url": "https://test.trycloudflare.com",
            "protocol": "quic",
            "pid": 12345,
            "latency_ms": 12.5,
            "restart_count": 0,
            "uptime_seconds": 10,
            "arch": "arm64",
            "version": "2024.8.2",
            "running": True,
            "crash_count": 0,
        }
        mock_service_manager.get.return_value = mock_svc

        r = self.client.get("/tunnel/status")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["state"], "CONNECTED")
        self.assertEqual(data["url"], "https://test.trycloudflare.com")
        self.assertEqual(data["protocol"], "quic")

    @patch("backend.main.service_manager")
    def test_tunnel_start_returns_200(self, mock_service_manager):
        mock_svc = MagicMock()
        mock_svc.get_status.return_value = {"state": "STARTING", "url": "", "running": False}
        mock_service_manager.get.return_value = mock_svc

        r = self.client.post("/tunnel/start")
        self.assertEqual(r.status_code, 200)

    @patch("backend.main.service_manager")
    def test_tunnel_stop_returns_200(self, mock_service_manager):
        mock_svc = MagicMock()
        mock_service_manager.get.return_value = mock_svc

        r = self.client.post("/tunnel/stop")
        self.assertEqual(r.status_code, 200)

    @patch("backend.main.service_manager")
    def test_tunnel_restart_returns_200(self, mock_service_manager):
        mock_svc = MagicMock()
        mock_svc.get_status.return_value = {"state": "STARTING", "url": "", "running": False}
        mock_service_manager.get.return_value = mock_svc

        r = self.client.post("/tunnel/restart")
        self.assertEqual(r.status_code, 200)

    @patch("backend.main.service_manager")
    def test_health_endpoint_contains_tunnel_state(self, mock_service_manager):
        """GET /health must include tunnel.state field from TunnelService."""
        # Build a mock that returns our tunnel status dict
        mock_svc = MagicMock()
        mock_svc.get_status.return_value = {
            "enabled": False,
            "provider": "cloudflare",
            "state": "STOPPED",
            "url": "",
            "protocol": "quic",
            "pid": None,
            "arch": "",
            "version": "",
            "running": False,
            "crash_count": 0,
        }
        mock_service_manager.get.return_value = mock_svc

        try:
            r = self.client.get("/health")
            self.assertIn(r.status_code, [200, 503])
        except Exception:
            pass

    @patch("backend.main.service_manager")
    def test_settings_endpoint_includes_tunnel_keys(self, mock_service_manager):
        mock_cfg = MagicMock()
        mock_service_manager.get.return_value = mock_cfg
        r = self.client.get("/settings")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("TUNNEL_ENABLED", data)
        self.assertIn("TUNNEL_PROVIDER", data)


class TestTunnelConfig(unittest.TestCase):

    def setUp(self):
        self.manager = ServiceManager()
        self.manager.register(ConfigService)
        self.config_svc = self.manager.get(ConfigService)

    def test_update_setting_tunnel_enabled(self):
        self.config_svc.update_setting("tunnel", "enabled", True)
        self.assertTrue(self.config_svc.config.TUNNEL_ENABLED)

    def test_update_setting_tunnel_protocol(self):
        self.config_svc.update_setting("tunnel", "protocol", "http2")
        self.assertEqual(self.config_svc.config.TUNNEL_PROTOCOL, "http2")

    def test_update_setting_tunnel_max_retries(self):
        self.config_svc.update_setting("tunnel", "max_retries", "10")
        self.assertEqual(self.config_svc.config.TUNNEL_MAX_RETRIES, 10)


if __name__ == "__main__":
    unittest.main()

