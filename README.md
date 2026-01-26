# Claude Reset Scheduler

## What & Why

Claude Code has a 5-hour rolling token limit. This scheduler automatically sends strategic pings to align the token reset window with your workday, ensuring you have full capacity during active development hours.

## Installation

### System-Wide (Recommended)

For production use, install as a system service:

**Prerequisites:** rsync (`sudo apt install rsync` on Ubuntu/Debian)

```bash
git clone https://github.com/tomasmach/claude-reset-scheduler.git
cd claude-reset-scheduler
sudo ./install.sh
```

The installer will guide you through configuration and set up systemd service automatically.

**Post-Installation:**
- Check status: `systemctl status claude-reset-scheduler.timer`
- View logs: `journalctl -u claude-reset-scheduler.service -f`
- Reconfigure: `sudo ./install.sh`
- Uninstall: `sudo ./uninstall.sh`

### Manual Installation

For development or testing, you can install locally using UV (recommended) or pip. If using UV:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv venv
source .venv/bin/activate
uv pip install pydantic pyyaml pytest
```

For manual installation without UV, set up a Python virtual environment and install dependencies yourself.

## Warning

**⚠️ Gray Area:** This tool operates in a gray area of Claude Code's terms of service. While it sends legitimate API calls, the intent is to optimize token reset timing rather than normal usage. Use at your own risk:

- This may violate Anthropic's terms of service
- Be prepared for potential account restrictions
- The authors are not responsible for any consequences

## License

MIT License - see [LICENSE](LICENSE) for details.
