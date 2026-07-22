"""
backend/tunnel_validator.py

Connectivity validator for Cloudflare Tunnel.

Performs 4 checks sequentially after a candidate URL is scraped:
  1. Localhost CAMZ server reachable
  2. Local /health reports READY state
  3. Cloudflare edge network reachable (DNS + HTTPS)
  4. Public tunnel URL responds

Only when all 4 pass is the tunnel considered CONNECTED and the URL exposed.
"""
from __future__ import annotations

import http.client
import logging
import socket
import time
from urllib.parse import urlparse

logger = logging.getLogger("camz.tunnel.validator")


class ValidationResult:
    """Result of a single connectivity check."""

    def __init__(self, ok: bool, check: str, detail: str = "") -> None:
        self.ok = ok
        self.check = check
        self.detail = detail

    def __bool__(self) -> bool:
        return self.ok

    def __repr__(self) -> str:
        status = "PASS" if self.ok else "FAIL"
        suffix = f": {self.detail}" if self.detail else ""
        return f"[{status}] {self.check}{suffix}"


class TunnelConnectivityValidator:
    """
    Validates that the CAMZ instance and the Cloudflare public URL
    are actually reachable before declaring the tunnel CONNECTED.
    """

    CLOUDFLARE_CHECK_HOST = "cloudflare.com"

    def __init__(
        self,
        local_port: int = 8000,
        timeout_seconds: float = 5.0,
        retry_interval: float = 2.0,
        max_attempts: int = 10,
    ) -> None:
        self._local_port = local_port
        self._timeout = timeout_seconds
        self._retry_interval = retry_interval
        self._max_attempts = max_attempts

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def validate(self, public_url: str) -> tuple[bool, str]:
        """
        Run all checks against the given public_url.
        Returns (success: bool, reason: str).
        The reason is empty on success, descriptive on failure.
        """
        checks = [
            self._check_localhost,
            self._check_local_health_ready,
            self._check_cloudflare_edge,
        ]

        for check_fn in checks:
            result = check_fn()
            logger.debug("Tunnel validator: %s", result)
            if not result:
                logger.warning("Tunnel validation failed — %s", result)
                return False, result.detail

        # Final check: public URL reachability (with retries, it may take a moment)
        result = self._check_public_url_with_retries(public_url)
        if not result:
            logger.warning("Tunnel validation failed — %s", result)
            return False, result.detail

        logger.info("Tunnel validation passed for %s", public_url)
        return True, ""

    # ------------------------------------------------------------------ #
    # Individual checks                                                    #
    # ------------------------------------------------------------------ #

    def _check_localhost(self) -> ValidationResult:
        """Check that the local CAMZ HTTP server responds."""
        try:
            conn = http.client.HTTPConnection("127.0.0.1", self._local_port, timeout=self._timeout)
            conn.request("GET", "/health")
            resp = conn.getresponse()
            resp.read()
            conn.close()
            if resp.status < 500:
                return ValidationResult(True, "localhost reachable", f"HTTP {resp.status}")
            return ValidationResult(
                False, "localhost reachable",
                f"HTTP {resp.status} — CAMZ health endpoint returned server error"
            )
        except Exception as exc:
            return ValidationResult(
                False, "localhost reachable",
                f"Cannot connect to 127.0.0.1:{self._local_port} — {exc}"
            )

    def _check_local_health_ready(self) -> ValidationResult:
        """Check that the local /health endpoint reports a ready state."""
        try:
            import json as _json
            conn = http.client.HTTPConnection("127.0.0.1", self._local_port, timeout=self._timeout)
            conn.request("GET", "/health")
            resp = conn.getresponse()
            body = resp.read().decode("utf-8", errors="replace")
            conn.close()

            data = _json.loads(body)
            # Accept either "ready" app_state or any 2xx without explicit "failed" status
            app_state = str(data.get("app_state", "")).lower()
            status = str(data.get("status", "")).lower()

            if app_state in ("ready",) or (status == "ok" and app_state not in ("failed", "error")):
                return ValidationResult(True, "local health READY", f"app_state={app_state}")

            return ValidationResult(
                False, "local health READY",
                f"app_state={app_state!r} is not ready — CAMZ may still be initializing"
            )
        except Exception as exc:
            return ValidationResult(
                False, "local health READY",
                f"Failed to parse /health response — {exc}"
            )

    def _check_cloudflare_edge(self) -> ValidationResult:
        """Check DNS resolution and HTTPS connectivity to the Cloudflare edge."""
        host = self.CLOUDFLARE_CHECK_HOST
        # 1. DNS
        try:
            socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
        except socket.gaierror as exc:
            return ValidationResult(
                False, "Cloudflare edge DNS",
                f"Cannot resolve {host} — {exc}. Check network/DNS."
            )

        # 2. HTTPS TCP connect
        try:
            conn = http.client.HTTPSConnection(host, 443, timeout=self._timeout)
            conn.request("HEAD", "/")
            resp = conn.getresponse()
            resp.read()
            conn.close()
            return ValidationResult(True, "Cloudflare edge HTTPS", f"HTTP {resp.status}")
        except Exception as exc:
            return ValidationResult(
                False, "Cloudflare edge HTTPS",
                f"Cannot reach {host}:443 — {exc}. Check firewall/outbound HTTPS."
            )

    def _check_public_url_with_retries(self, public_url: str) -> ValidationResult:
        """Poll the public tunnel URL until it responds or retries are exhausted."""
        parsed = urlparse(public_url)
        host = parsed.netloc
        # Prefer the /health endpoint — gives a meaningful response
        probe_path = "/health"

        last_error = "no attempts made"
        for attempt in range(1, self._max_attempts + 1):
            try:
                conn = http.client.HTTPSConnection(host, 443, timeout=self._timeout)
                conn.request("GET", probe_path, headers={"User-Agent": "CAMZ-TunnelValidator/1.0"})
                resp = conn.getresponse()
                resp.read()
                conn.close()
                if resp.status < 600:  # Any response (even 4xx) means the tunnel is routing
                    return ValidationResult(
                        True, "public URL reachable",
                        f"{public_url} → HTTP {resp.status} (attempt {attempt})"
                    )
            except Exception as exc:
                last_error = str(exc)
                logger.debug(
                    "Tunnel validator: public URL check attempt %d/%d failed: %s",
                    attempt, self._max_attempts, exc
                )

            if attempt < self._max_attempts:
                time.sleep(self._retry_interval)

        return ValidationResult(
            False, "public URL reachable",
            f"Tunnel URL {public_url} did not respond after {self._max_attempts} attempts "
            f"(last error: {last_error}). Possible Error 1033 — tunnel not yet registered."
        )

    # ------------------------------------------------------------------ #
    # Individual check runners (for camz tunnel doctor)                   #
    # ------------------------------------------------------------------ #

    def run_doctor_checks(self, public_url: str | None = None) -> list[ValidationResult]:
        """Run all checks and return individual results (for diagnostic output)."""
        results: list[ValidationResult] = [
            self._check_localhost(),
            self._check_local_health_ready(),
            self._check_cloudflare_edge(),
        ]
        if public_url:
            results.append(self._check_public_url_with_retries(public_url))
        return results
