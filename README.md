# Claude Reset Scheduler

Optimize your Claude Code token usage by scheduling strategic pings that align 5-hour token limit resets with your workday. Ensures fresh capacity is available during peak development hours.

## What is this?

Claude Code has a 5-hour rolling token limit. This scheduler automatically sends strategic pings to the Claude Code CLI to reset your token window, ensuring you always have full capacity when you start your workday.

By scheduling pings throughout your workday, the 5-hour reset window aligns with your active development hours, preventing mid-day token exhaustion.

## System-Wide Installation (Recommended)

For production use, install as a system service:

### Prerequisites

- Ubuntu/Debian: `sudo apt install rsync`
- Fedora/RHEL: `sudo dnf install rsync`
- Arch: `sudo pacman -S rsync`

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/claude-reset-scheduler.git
cd claude-reset-scheduler

# Run interactive installer
sudo ./install.sh
```

The installer will:
1. Guide you through configuration (days, times, frequency)
2. Create a dedicated system user
3. Install to `/opt/claude-reset-scheduler`
4. Set up systemd service and timer
5. Start the scheduler automatically

### Post-Installation

Check status:
```bash
systemctl status claude-reset-scheduler.timer
```

View logs:
```bash
journalctl -u claude-reset-scheduler.service -f
```

Reconfigure:
```bash
sudo ./install.sh
```

Uninstall:
```bash
sudo ./uninstall.sh
```

## Manual Installation

For development or testing, you can install locally:

### Using UV (Recommended)

```bash
# Install UV if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create and activate virtual environment
uv venv
source .venv/bin/activate

# Install dependencies
uv pip install pydantic pyyaml pytest
```

### Using Pip

```bash
# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install pydantic pyyaml pytest
```

## Configuration

### System Installation

Configuration is created automatically by `install.sh` at `/etc/claude-reset-scheduler/config.yaml`.

To reconfigure, run: `sudo ./install.sh`

### Manual Installation

Create a `config.yaml` file at `~/.config/claude-reset-scheduler/config.yaml`:

```yaml
work_start_time: "09:00"
active_days: [0, 1, 2, 3, 4]
log_level: "INFO"
log_file: "~/.local/share/claude-reset-scheduler/scheduler.log"
ping_message: "ping"
ping_timeout: 30
```

### Configuration Options

| Option | Required | Default | Description |
|--------|----------|---------|-------------|
| `work_start_time` | No | `09:00` | Time when your workday begins (HH:MM format) |
| `active_days` | No | `[0, 1, 2, 3, 4]` | Days to run (0=Monday, 6=Sunday) |
| `log_level` | No | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| `log_file` | No | `~/.local/share/claude-reset-scheduler/scheduler.log` | Path to log file |
| `ping_message` | No | `ping` | Message to send in ping |
| `ping_timeout` | No | `30` | Timeout for ping in seconds |

### Day Numbers

| Number | Day |
|--------|-----|
| 0 | Monday |
| 1 | Tuesday |
| 2 | Wednesday |
| 3 | Thursday |
| 4 | Friday |
| 5 | Saturday |
| 6 | Sunday |

### Example Configurations

**Standard 9-5 workday (Monday-Friday):**
```yaml
work_start_time: "09:00"
active_days: [0, 1, 2, 3, 4]
log_level: "INFO"
```

**Weekend warrior (Saturday-Sunday):**
```yaml
work_start_time: "10:00"
active_days: [5, 6]
log_level: "INFO"
```

**Every day:**
```yaml
work_start_time: "09:00"
active_days: [0, 1, 2, 3, 4, 5, 6]
log_level: "INFO"
```

**Late shift (Tuesday-Thursday):**
```yaml
work_start_time: "14:00"
active_days: [1, 2, 3]
log_level: "DEBUG"
```

## Usage

### Check Schedule

```bash
python -m claude_reset_scheduler schedule
```

Output:
```
Schedule based on config:
  Work start time: 09:00
  Active days: 0, 1, 2, 3, 4

Ping times:
  1. 09:00
  2. 14:00

Upcoming days:
  2026-01-27 (Monday): ACTIVE
  2026-01-28 (Tuesday): ACTIVE
  2026-01-29 (Wednesday): ACTIVE
  2026-01-30 (Thursday): ACTIVE
  2026-01-31 (Friday): ACTIVE
  2026-02-01 (Saturday): inactive
  2026-02-02 (Sunday): inactive
```

### Test Mode (Dry Run)

```bash
python -m claude_reset_scheduler test
```

Output:
```
Running in test mode (dry-run)
Work start time: 09:00
Active days: 0, 1, 2, 3, 4
Scheduled ping times: 09:00, 14:00
Current time: 14:30
  09:00: already sent
  14:00: already sent
```

### Run Scheduler

```bash
python -m claude_reset_scheduler run
```

This will send pings if it's the scheduled time and no ping has been sent yet today.

### Custom Config File

```bash
python -m claude_reset_scheduler --config /path/to/custom-config.yaml schedule
```

## Systemd Setup

### Generate Systemd Files

```bash
python -m claude_reset_scheduler install
```

This generates `claude-reset-scheduler.service` and `claude-reset-scheduler.timer` files in the current directory.

### Install and Enable Service

```bash
# Copy systemd files
sudo cp claude-reset-scheduler.service /etc/systemd/system/
sudo cp claude-reset-scheduler.timer /etc/systemd/system/

# Reload systemd daemon
sudo systemctl daemon-reload

# Enable timer to start on boot
sudo systemctl enable claude-reset-scheduler.timer

# Start timer immediately
sudo systemctl start claude-reset-scheduler.timer

# Check timer status
sudo systemctl status claude-reset-scheduler.timer

# View service logs
sudo journalctl -u claude-reset-scheduler.service -f
```

### How It Works

The systemd timer runs every 15 minutes. Each time it runs, the scheduler checks:

1. If today is an active day
2. If it's time to send a ping (within 15 minutes of scheduled time)
3. If a ping has already been sent today
4. If rate limiting is needed (no pings within the last hour)

If all conditions are met, it sends a ping to the Claude Code CLI.

## Testing

Run the test suite:

```bash
pytest tests/
```

Run with coverage:

```bash
pytest --cov=src/claude_reset_scheduler tests/
```

## FAQ

**Q: Why do I need this scheduler?**
A: Claude Code's 5-hour rolling token limit can reset at inconvenient times. By strategically timing pings throughout your workday, you ensure the reset window aligns with your active development hours.

**Q: How often are pings sent?**
A: The scheduler sends pings every 5 hours starting from your work start time, continuing throughout your workday. For example, with a 9am start: 09:00, 14:00, 19:00 (if still within work hours).

**Q: Will this violate Claude's terms of service?**
A: This tool is a gray area. It sends legitimate API calls but specifically to optimize token reset timing. Use responsibly and at your own risk.

**Q: Can I change the ping interval?**
A: The 5-hour interval aligns with Claude Code's token reset window. You can modify the interval in the `calculate_ping_times` function in `src/scheduler.py`, but 5 hours is optimal for token limit management.

**Q: What happens if the ping fails?**
A: The scheduler will retry up to 3 times with exponential backoff (5s, 10s, 20s). If all retries fail, it logs an error and waits for the next scheduled check.

**Q: How does rate limiting work?**
A: The scheduler won't send more than one ping per hour, even if multiple scheduled times fall within that window.

**Q: Can I run this on multiple machines?**
A: Each machine maintains its own token limit. You'll need a separate scheduler instance per machine.

**Q: Does this work with Claude Code CLI or only the web interface?**
A: This is designed for the Claude Code CLI. Ensure `claude-code` command is available in your PATH.

**Q: Where are pings tracked?**
A: Pings are tracked in `~/.local/state/claude-reset-scheduler/last_pings.json`.

## Disclaimer

**⚠️ Gray Area Warning:** This tool operates in a gray area of Claude Code's terms of service. While it sends legitimate API calls, the intent is to optimize token reset timing rather than normal usage. Use responsibly:

- This may violate Anthropic's terms of service
- Use at your own risk
- Consider the ethical implications
- Don't abuse or overload the API
- Be prepared for potential account restrictions

The authors are not responsible for any consequences arising from the use of this tool.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please ensure all tests pass before submitting a pull request:

```bash
pytest tests/
```

## Development

To set up for development:

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run linting
ruff check src/

# Run type checking
mypy src/
```
