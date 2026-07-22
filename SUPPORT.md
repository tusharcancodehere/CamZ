# CAMZ Support Guide

If you run into issues or have questions regarding CAMZ setup, hardware configuration, or tunnel routing, please refer to the resources below.

---

## 🔍 Diagnostics & Health Verification

Always run diagnostics first to identify if your platform supports the required drivers, libraries, sockets, or network rules:

```bash
./camz doctor
```

To display general system information, camera backends, and active tunnel states:
```bash
./camz info
```

---

## 📖 Documentation Suite

Before opening an issue, check the comprehensive documentation in `docs/`:

- [Installation Guide](docs/INSTALL.md)
- [Configuration Reference](docs/CONFIGURATION.md)
- [CLI Reference](docs/CLI.md)
- [REST API Reference](docs/API.md)
- [Recording Management](docs/RECORDING_MANAGEMENT.md)
- [Cloudflare Tunnel Guide](docs/CLOUDFLARE_TUNNEL.md)
- [Developer Guide](docs/DEVELOPMENT.md)
- [Troubleshooting Guide](docs/TROUBLESHOOTING.md)

---

## 📝 Reading System Logs

Application logs are saved to `runtime/logs/camera.log`. You can inspect them directly:

```bash
# View live logs via CLI
./camz logs

# Tail log file directly
tail -n 100 runtime/logs/camera.log
```

---

## 💬 Community Support Channels

- **GitHub Issues**: Open a bug report or feature request.
- **GitHub Discussions**: Share setup guides, showcase Raspberry Pi installations, or request templates.
