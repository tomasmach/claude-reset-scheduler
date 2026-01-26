# Interactive Installation Script Design

## Overview

Create an `install.sh` script that guides users through configuration via interactive prompts, then installs the Claude Reset Scheduler as a system-wide systemd service.

## Requirements

- System-wide installation to `/opt/claude-reset-scheduler`
- Must run with sudo (check enforced)
- Interactive configuration wizard with validation
- Respects existing configurations with user choice
- Uses UV for dependency management
- Installs as systemd service/timer

## Configuration Model Changes

**Remove `work_end_time`**: This field serves no purpose since 5-hour ping intervals are about token resets, not work hours. Pings can extend beyond "work hours" without issue.

**Updated Config Structure**:
```yaml
work_start_time: "09:00"      # First ping of the day
active_days: [0, 1, 2, 3, 4]  # Days to run pings
log_level: "INFO"             # Always INFO, not configurable
log_file: "/var/log/claude-reset-scheduler/scheduler.log"
ping_message: "ping"
ping_timeout: 30
```

**Ping Calculation**: Always use 5-hour intervals from `work_start_time` regardless of number of pings requested. User sets first ping time + number of pings, script calculates: first_ping, first_ping+5h, first_ping+10h, etc.

## Overall Flow

```
1. Check if running as root → exit if not
2. Check for existing config at /etc/claude-reset-scheduler/config.yaml
   - If exists: prompt "(U)se existing, (R)econfigure, (A)bort?"
   - U: skip to installation using existing config
   - R: continue to wizard
   - A: exit cleanly
3. Run interactive configuration wizard
4. Generate config.yaml with validated inputs
5. Install system components
6. Enable and start systemd timer
7. Show status and next steps
```

## Interactive Configuration Wizard

### Prompts

**1. Active Days**
```
Which days should pings run? [0,1,2,3,4] (0=Mon, 1=Tue, ... 6=Sun, e.g., 0,1,2,3,4 or 5,6):
```
- Parse comma-separated list
- Validate: each number 0-6, no duplicates
- Re-prompt on error: "Invalid format. Must be comma-separated numbers 0-6."

**2. First Ping Time**
```
First ping time [09:00] (e.g., 08:00, 10:30, 14:00):
```
- Validate: HH:MM format, hours 00-23, minutes 00-59
- Re-prompt on error: "Invalid time format. Use HH:MM (e.g., 09:00)."

**3. Number of Pings**
```
Number of pings per day [3] (e.g., 2, 3, 4):
```
- Validate: integer 1-5 (reasonable range)
- Re-prompt on error: "Invalid number. Must be 1-5."

**4. Confirmation**
```
Configuration Summary:
- Active days: Monday, Tuesday, Wednesday, Thursday, Friday
- First ping: 09:00
- Pings per day: 3
- Ping times: 09:00, 14:00, 19:00

Continue with installation? (y/n):
```
- If n: exit cleanly
- If y: proceed to installation

### Validation Strategy

All prompts loop until valid input is received. Each prompt shows:
- Default value in brackets
- Examples of valid input
- Clear error messages on invalid input

## System Installation Steps

### 1. Create System User
```bash
useradd --system --no-create-home --shell /usr/sbin/nologin claude-reset-scheduler
```
Group created automatically with same name.

### 2. Install to /opt
```bash
mkdir -p /opt/claude-reset-scheduler
# Copy project files (exclude .git, .venv, __pycache__)
chown -R root:root /opt/claude-reset-scheduler
```

### 3. Create Virtual Environment
```bash
# Check if UV installed, if not: curl -LsSf https://astral.sh/uv/install.sh | sh
cd /opt/claude-reset-scheduler
uv venv
uv pip install pydantic pyyaml pytest
```

### 4. Create Config
```bash
mkdir -p /etc/claude-reset-scheduler
# Generate config.yaml from wizard inputs
chown root:claude-reset-scheduler /etc/claude-reset-scheduler/config.yaml
chmod 640 /etc/claude-reset-scheduler/config.yaml
```

### 5. Create Runtime Directories
```bash
mkdir -p /var/log/claude-reset-scheduler
mkdir -p /var/lib/claude-reset-scheduler
chown claude-reset-scheduler:claude-reset-scheduler /var/log/claude-reset-scheduler
chown claude-reset-scheduler:claude-reset-scheduler /var/lib/claude-reset-scheduler
chmod 755 /var/log/claude-reset-scheduler
chmod 755 /var/lib/claude-reset-scheduler
```

### 6. Install Systemd Files
```bash
cp systemd/*.{service,timer} /etc/systemd/system/
# Update service file:
# - ExecStart=/opt/claude-reset-scheduler/.venv/bin/python3 -m claude_reset_scheduler run
# - Environment=CLAUDE_RESET_SCHEDULER_CONFIG=/etc/claude-reset-scheduler/config.yaml
systemctl daemon-reload
```

## Service Activation

### Enable and Start
```bash
systemctl enable claude-reset-scheduler.timer
systemctl start claude-reset-scheduler.timer
systemctl is-active claude-reset-scheduler.timer  # Verify
```

### Success Output
```
✓ Installation complete!

Configuration:
- Active days: Monday, Tuesday, Wednesday, Thursday, Friday
- Ping times: 09:00, 14:00, 19:00
- Config: /etc/claude-reset-scheduler/config.yaml
- Logs: /var/log/claude-reset-scheduler/scheduler.log

Service status:
- Timer: active (runs every 15 minutes)
- Next run: <timestamp from systemctl>

Useful commands:
- Check timer status:  systemctl status claude-reset-scheduler.timer
- View logs:           journalctl -u claude-reset-scheduler.service -f
- Stop scheduler:      systemctl stop claude-reset-scheduler.timer
- Restart scheduler:   systemctl restart claude-reset-scheduler.timer
- Reconfigure:         sudo ./install.sh
```

## Error Handling

- Trap EXIT to cleanup partial installations on failure
- Clear error messages for each failure point
- Suggest rollback steps if installation fails partway through
- Check prerequisites: sudo, UV availability, systemctl

## Code Structure

```bash
#!/bin/bash
set -e

# Functions:
check_sudo()              # Verify running as root
check_existing_config()   # Handle existing config (U/R/A)
interactive_config()      # Run configuration wizard
validate_days()           # Validate day numbers
validate_time()           # Validate HH:MM format
validate_pings()          # Validate ping count
calculate_ping_times()    # Generate ping schedule
generate_config()         # Create config.yaml
install_system()          # Install all system components
activate_service()        # Enable and start systemd
show_success()            # Display completion message
cleanup_on_error()        # Rollback on failure

# Main execution flow
trap cleanup_on_error EXIT
main()
```

## Implementation Notes

- Use bash built-ins for portability (no external dependencies besides UV)
- Colored output for better UX (green for success, red for errors, yellow for warnings)
- All paths use absolute references, no assumptions about working directory
- Config generation uses YAML-safe formatting (proper quoting, indentation)
- Service file generation uses template substitution for paths
