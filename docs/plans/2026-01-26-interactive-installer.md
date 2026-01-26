# Interactive Installer Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create an interactive `install.sh` script that guides users through configuration and installs Claude Reset Scheduler as a system-wide systemd service.

**Architecture:** Bash script with modular functions for validation, configuration wizard, and system installation. Uses UV for Python dependency management, creates dedicated system user, and installs to /opt with proper permissions.

**Tech Stack:** Bash, systemd, UV (Python package manager), YAML

---

## Task 1: Remove work_end_time from Config

**Files:**
- Modify: `src/config.py:52`
- Modify: `src/scheduler.py:21-38`

**Step 1: Remove work_end_time from Config model**

In `src/config.py`, remove the `work_end_time` field and its validator:

```python
class Config(BaseModel):
    work_start_time: str = Field(default="09:00")
    # DELETE: work_end_time: str = Field(default="17:00")
    active_days: list[int] = Field(default=[0, 1, 2, 3, 4])
    # ... rest unchanged
```

Remove the `validate_work_times_order` validator entirely (lines 78-88).

**Step 2: Update calculate_ping_times to use number of pings**

In `src/scheduler.py`, replace the `calculate_ping_times` function:

```python
def calculate_ping_times(config: Config, num_pings: int = 3) -> list[str]:
    """Calculate ping times based on start time and number of pings.

    Args:
        config: Configuration containing work_start_time
        num_pings: Number of pings per day (default 3)

    Returns:
        List of time strings in HH:MM format, spaced 5 hours apart
    """
    start_hour, start_minute = map(int, config.work_start_time.split(":"))
    start_time_minutes = start_hour * 60 + start_minute

    ping_interval_minutes = 5 * 60  # 5 hours

    times = []
    current_time_minutes = start_time_minutes
    for _ in range(num_pings):
        hour = current_time_minutes // 60
        minute = current_time_minutes % 60
        times.append(f"{hour:02d}:{minute:02d}")
        current_time_minutes += ping_interval_minutes

    return times
```

**Step 3: Run existing tests**

Run: `pytest tests/ -v`
Expected: Some tests may fail due to API change (num_pings parameter)

**Step 4: Commit config changes**

```bash
git add src/config.py src/scheduler.py
git commit -m "refactor: remove work_end_time and update ping calculation"
```

---

## Task 2: Create install.sh Script Structure

**Files:**
- Create: `install.sh`

**Step 1: Write initial script structure**

Create `install.sh`:

```bash
#!/bin/bash
set -e
set -o pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
INSTALL_DIR="/opt/claude-reset-scheduler"
CONFIG_DIR="/etc/claude-reset-scheduler"
LOG_DIR="/var/log/claude-reset-scheduler"
STATE_DIR="/var/lib/claude-reset-scheduler"
SERVICE_USER="claude-reset-scheduler"

# Trap for cleanup on error
trap 'cleanup_on_error' EXIT

cleanup_on_error() {
    if [ $? -ne 0 ]; then
        echo -e "${RED}Installation failed!${NC}"
        echo "Check logs above for details"
    fi
}

error() {
    echo -e "${RED}ERROR: $1${NC}" >&2
}

success() {
    echo -e "${GREEN}✓ $1${NC}"
}

warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

info() {
    echo "$1"
}

main() {
    check_sudo
    check_existing_config
    interactive_config
    generate_config
    install_system
    activate_service
    show_success
}

# Placeholder functions (will be implemented in next tasks)
check_sudo() { :; }
check_existing_config() { :; }
interactive_config() { :; }
generate_config() { :; }
install_system() { :; }
activate_service() { :; }
show_success() { :; }

main
```

**Step 2: Make script executable**

Run: `chmod +x install.sh`

**Step 3: Test script runs**

Run: `./install.sh`
Expected: Should exit immediately (placeholder functions do nothing)

**Step 4: Commit script structure**

```bash
git add install.sh
git commit -m "feat: add install.sh script structure"
```

---

## Task 3: Implement Validation Functions

**Files:**
- Modify: `install.sh`

**Step 1: Add validation functions**

Add before the `main()` function:

```bash
validate_days() {
    local input="$1"

    # Remove spaces
    input="${input// /}"

    # Check format: comma-separated numbers
    if ! [[ "$input" =~ ^[0-6](,[0-6])*$ ]]; then
        return 1
    fi

    # Check for duplicates
    IFS=',' read -ra days <<< "$input"
    local seen=()
    for day in "${days[@]}"; do
        if [[ " ${seen[@]} " =~ " ${day} " ]]; then
            return 1
        fi
        seen+=("$day")
    done

    return 0
}

validate_time() {
    local input="$1"

    # Check format HH:MM
    if ! [[ "$input" =~ ^[0-9]{2}:[0-9]{2}$ ]]; then
        return 1
    fi

    local hour="${input%%:*}"
    local minute="${input##*:}"

    # Validate ranges
    if [ "$hour" -lt 0 ] || [ "$hour" -gt 23 ]; then
        return 1
    fi

    if [ "$minute" -lt 0 ] || [ "$minute" -gt 59 ]; then
        return 1
    fi

    return 0
}

validate_pings() {
    local input="$1"

    # Check if integer
    if ! [[ "$input" =~ ^[0-9]+$ ]]; then
        return 1
    fi

    # Check range 1-5
    if [ "$input" -lt 1 ] || [ "$input" -gt 5 ]; then
        return 1
    fi

    return 0
}

calculate_ping_times_bash() {
    local start_time="$1"
    local num_pings="$2"

    local hour="${start_time%%:*}"
    local minute="${start_time##*:}"
    local start_minutes=$((hour * 60 + minute))

    local times=()
    local current_minutes=$start_minutes

    for ((i=0; i<num_pings; i++)); do
        local h=$((current_minutes / 60))
        local m=$((current_minutes % 60))
        times+=("$(printf "%02d:%02d" $h $m)")
        current_minutes=$((current_minutes + 300))  # 5 hours = 300 minutes
    done

    echo "${times[@]}"
}

day_name() {
    case "$1" in
        0) echo "Monday" ;;
        1) echo "Tuesday" ;;
        2) echo "Wednesday" ;;
        3) echo "Thursday" ;;
        4) echo "Friday" ;;
        5) echo "Saturday" ;;
        6) echo "Sunday" ;;
    esac
}
```

**Step 2: Test validation functions**

Run: `bash -c 'source install.sh; validate_days "0,1,2,3,4" && echo "valid" || echo "invalid"'`
Expected: "valid"

Run: `bash -c 'source install.sh; validate_time "09:00" && echo "valid" || echo "invalid"'`
Expected: "valid"

Run: `bash -c 'source install.sh; validate_pings "3" && echo "valid" || echo "invalid"'`
Expected: "valid"

**Step 3: Commit validation functions**

```bash
git add install.sh
git commit -m "feat: add input validation functions"
```

---

## Task 4: Implement check_sudo and check_existing_config

**Files:**
- Modify: `install.sh`

**Step 1: Implement check_sudo function**

Replace the `check_sudo` placeholder:

```bash
check_sudo() {
    if [ "$EUID" -ne 0 ]; then
        error "This script must be run with sudo"
        echo "Usage: sudo ./install.sh"
        exit 1
    fi
    success "Running as root"
}
```

**Step 2: Implement check_existing_config function**

Replace the `check_existing_config` placeholder:

```bash
check_existing_config() {
    local config_file="$CONFIG_DIR/config.yaml"

    if [ ! -f "$config_file" ]; then
        USE_EXISTING_CONFIG=false
        return 0
    fi

    info ""
    info "Existing configuration found at $config_file"

    while true; do
        read -p "$(echo -e "${YELLOW}(U)se existing, (R)econfigure, or (A)bort?${NC} ")" choice
        case "$choice" in
            [Uu]* )
                USE_EXISTING_CONFIG=true
                success "Using existing configuration"
                return 0
                ;;
            [Rr]* )
                USE_EXISTING_CONFIG=false
                warning "Will reconfigure"
                return 0
                ;;
            [Aa]* )
                info "Installation aborted by user"
                exit 0
                ;;
            * )
                error "Invalid choice. Please enter U, R, or A."
                ;;
        esac
    done
}
```

**Step 3: Add global variable at top of script**

Add after the configuration section:

```bash
# Global state
USE_EXISTING_CONFIG=false
```

**Step 4: Test sudo check**

Run: `./install.sh`
Expected: "ERROR: This script must be run with sudo"

Run: `sudo ./install.sh`
Expected: Should proceed past sudo check

**Step 5: Commit check functions**

```bash
git add install.sh
git commit -m "feat: implement sudo and existing config checks"
```

---

## Task 5: Implement Interactive Configuration Wizard

**Files:**
- Modify: `install.sh`

**Step 1: Add global variables for config values**

Add after `USE_EXISTING_CONFIG=false`:

```bash
CONFIG_ACTIVE_DAYS=""
CONFIG_FIRST_PING=""
CONFIG_NUM_PINGS=""
```

**Step 2: Implement interactive_config function**

Replace the `interactive_config` placeholder:

```bash
interactive_config() {
    if [ "$USE_EXISTING_CONFIG" = true ]; then
        return 0
    fi

    info ""
    info "=== Configuration Wizard ==="
    info ""

    # Prompt for active days
    while true; do
        read -p "Which days should pings run? [0,1,2,3,4] (0=Mon, 1=Tue, ... 6=Sun, e.g., 0,1,2,3,4 or 5,6): " input
        input="${input:-0,1,2,3,4}"

        if validate_days "$input"; then
            CONFIG_ACTIVE_DAYS="$input"
            break
        else
            error "Invalid format. Must be comma-separated numbers 0-6."
        fi
    done

    # Prompt for first ping time
    while true; do
        read -p "First ping time [09:00] (e.g., 08:00, 10:30, 14:00): " input
        input="${input:-09:00}"

        if validate_time "$input"; then
            CONFIG_FIRST_PING="$input"
            break
        else
            error "Invalid time format. Use HH:MM (e.g., 09:00)."
        fi
    done

    # Prompt for number of pings
    while true; do
        read -p "Number of pings per day [3] (e.g., 2, 3, 4): " input
        input="${input:-3}"

        if validate_pings "$input"; then
            CONFIG_NUM_PINGS="$input"
            break
        else
            error "Invalid number. Must be 1-5."
        fi
    done

    # Show summary and confirm
    info ""
    info "=== Configuration Summary ==="

    # Convert days to names
    IFS=',' read -ra days <<< "$CONFIG_ACTIVE_DAYS"
    local day_names=()
    for day in "${days[@]}"; do
        day_names+=("$(day_name "$day")")
    done
    info "- Active days: ${day_names[*]}"

    info "- First ping: $CONFIG_FIRST_PING"
    info "- Pings per day: $CONFIG_NUM_PINGS"

    # Calculate and show ping times
    local ping_times=($(calculate_ping_times_bash "$CONFIG_FIRST_PING" "$CONFIG_NUM_PINGS"))
    info "- Ping times: ${ping_times[*]}"

    info ""

    while true; do
        read -p "Continue with installation? (y/n): " choice
        case "$choice" in
            [Yy]* )
                success "Configuration confirmed"
                return 0
                ;;
            [Nn]* )
                info "Installation aborted by user"
                exit 0
                ;;
            * )
                error "Please answer y or n."
                ;;
        esac
    done
}
```

**Step 3: Test interactive wizard**

Run: `sudo ./install.sh`
Expected: Should prompt for configuration (may error on later steps)

**Step 4: Commit wizard implementation**

```bash
git add install.sh
git commit -m "feat: implement interactive configuration wizard"
```

---

## Task 6: Implement Configuration File Generation

**Files:**
- Modify: `install.sh`

**Step 1: Implement generate_config function**

Replace the `generate_config` placeholder:

```bash
generate_config() {
    if [ "$USE_EXISTING_CONFIG" = true ]; then
        info "Using existing configuration"
        return 0
    fi

    local config_file="$CONFIG_DIR/config.yaml"

    info "Generating configuration file..."

    # Create config directory
    mkdir -p "$CONFIG_DIR"

    # Convert days array to YAML format
    local days_yaml="["
    IFS=',' read -ra days <<< "$CONFIG_ACTIVE_DAYS"
    for i in "${!days[@]}"; do
        if [ $i -gt 0 ]; then
            days_yaml+=", "
        fi
        days_yaml+="${days[$i]}"
    done
    days_yaml+="]"

    # Generate config.yaml
    cat > "$config_file" << EOF
work_start_time: "$CONFIG_FIRST_PING"
active_days: $days_yaml
log_level: "INFO"
log_file: "$LOG_DIR/scheduler.log"
ping_message: "ping"
ping_timeout: 30
EOF

    # Set permissions
    chown root:$SERVICE_USER "$config_file" 2>/dev/null || true
    chmod 640 "$config_file"

    success "Configuration file created at $config_file"
}
```

**Step 2: Test config generation (dry run)**

Create a test version that writes to /tmp:

Run: `sudo bash -c 'CONFIG_DIR=/tmp/test-config CONFIG_ACTIVE_DAYS="0,1,2" CONFIG_FIRST_PING="10:00" CONFIG_NUM_PINGS="2" SERVICE_USER=root; source install.sh; generate_config'`
Expected: Creates `/tmp/test-config/config.yaml`

Run: `cat /tmp/test-config/config.yaml`
Expected: Valid YAML with correct values

**Step 3: Commit config generation**

```bash
git add install.sh
git commit -m "feat: implement configuration file generation"
```

---

## Task 7: Implement System Installation

**Files:**
- Modify: `install.sh`

**Step 1: Implement install_system function**

Replace the `install_system` placeholder:

```bash
install_system() {
    info ""
    info "=== Installing System Components ==="

    # Create system user
    if ! id "$SERVICE_USER" &>/dev/null; then
        info "Creating system user $SERVICE_USER..."
        useradd --system --no-create-home --shell /usr/sbin/nologin "$SERVICE_USER"
        success "System user created"
    else
        success "System user already exists"
    fi

    # Install to /opt
    info "Installing to $INSTALL_DIR..."
    mkdir -p "$INSTALL_DIR"

    # Get the directory where install.sh is located
    local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

    # Copy project files (exclude .git, .venv, __pycache__)
    rsync -av --exclude='.git' --exclude='.venv' --exclude='__pycache__' \
        --exclude='*.pyc' --exclude='.pytest_cache' \
        "$script_dir/" "$INSTALL_DIR/"

    chown -R root:root "$INSTALL_DIR"
    success "Project files installed"

    # Check and install UV
    if ! command -v uv &> /dev/null; then
        info "Installing UV package manager..."
        curl -LsSf https://astral.sh/uv/install.sh | sh
        export PATH="$HOME/.local/bin:$PATH"
        success "UV installed"
    else
        success "UV already installed"
    fi

    # Create virtual environment
    info "Creating virtual environment..."
    cd "$INSTALL_DIR"
    uv venv
    uv pip install pydantic pyyaml pytest
    success "Virtual environment created"

    # Create runtime directories
    info "Creating runtime directories..."
    mkdir -p "$LOG_DIR"
    mkdir -p "$STATE_DIR"
    chown "$SERVICE_USER:$SERVICE_USER" "$LOG_DIR"
    chown "$SERVICE_USER:$SERVICE_USER" "$STATE_DIR"
    chmod 755 "$LOG_DIR"
    chmod 755 "$STATE_DIR"
    success "Runtime directories created"

    # Install systemd files
    info "Installing systemd service files..."
    local python_path="$INSTALL_DIR/.venv/bin/python3"

    # Update service file with correct paths
    sed -e "s|ExecStart=.*|ExecStart=$python_path -m claude_reset_scheduler run|" \
        -e "s|WorkingDirectory=.*|WorkingDirectory=$INSTALL_DIR|" \
        -e "s|Environment=PATH=.*|Environment=PATH=$INSTALL_DIR/.venv/bin:/usr/bin:/bin|" \
        -e "s|Environment=CLAUDE_RESET_SCHEDULER_CONFIG=.*|Environment=CLAUDE_RESET_SCHEDULER_CONFIG=$CONFIG_DIR/config.yaml|" \
        "$INSTALL_DIR/systemd/claude-reset-scheduler.service" > /etc/systemd/system/claude-reset-scheduler.service

    cp "$INSTALL_DIR/systemd/claude-reset-scheduler.timer" /etc/systemd/system/

    systemctl daemon-reload
    success "Systemd files installed"
}
```

**Step 2: Check for rsync dependency**

Add prerequisite check in `check_sudo` function:

```bash
check_sudo() {
    if [ "$EUID" -ne 0 ]; then
        error "This script must be run with sudo"
        echo "Usage: sudo ./install.sh"
        exit 1
    fi

    # Check for rsync
    if ! command -v rsync &> /dev/null; then
        error "rsync is required but not installed"
        echo "Install it with: sudo apt install rsync  # or equivalent for your OS"
        exit 1
    fi

    success "Running as root"
}
```

**Step 3: Commit system installation**

```bash
git add install.sh
git commit -m "feat: implement system installation"
```

---

## Task 8: Implement Service Activation and Success Message

**Files:**
- Modify: `install.sh`

**Step 1: Implement activate_service function**

Replace the `activate_service` placeholder:

```bash
activate_service() {
    info ""
    info "=== Activating Service ==="

    # Enable timer to start on boot
    info "Enabling systemd timer..."
    systemctl enable claude-reset-scheduler.timer
    success "Timer enabled"

    # Start timer immediately
    info "Starting systemd timer..."
    systemctl start claude-reset-scheduler.timer
    success "Timer started"

    # Verify timer is active
    if systemctl is-active --quiet claude-reset-scheduler.timer; then
        success "Timer is active"
    else
        error "Timer failed to start"
        echo "Check status with: systemctl status claude-reset-scheduler.timer"
        exit 1
    fi
}
```

**Step 2: Implement show_success function**

Replace the `show_success` placeholder:

```bash
show_success() {
    local config_file="$CONFIG_DIR/config.yaml"

    # Read config values for display
    local active_days log_file
    if [ -f "$config_file" ]; then
        active_days=$(grep "active_days:" "$config_file" | cut -d':' -f2 | tr -d ' []')
        log_file=$(grep "log_file:" "$config_file" | cut -d':' -f2 | tr -d ' "')
    fi

    # Convert days to names
    local day_names=()
    IFS=',' read -ra days <<< "$active_days"
    for day in "${days[@]}"; do
        day_names+=("$(day_name "$day")")
    done

    # Calculate ping times for display
    local ping_times
    if [ "$USE_EXISTING_CONFIG" = false ]; then
        ping_times=($(calculate_ping_times_bash "$CONFIG_FIRST_PING" "$CONFIG_NUM_PINGS"))
    fi

    # Get next run time
    local next_run=$(systemctl list-timers --no-pager | grep claude-reset-scheduler | awk '{print $1, $2, $3}')

    info ""
    echo -e "${GREEN}✓ Installation complete!${NC}"
    info ""
    info "Configuration:"
    info "- Active days: ${day_names[*]}"
    if [ ${#ping_times[@]} -gt 0 ]; then
        info "- Ping times: ${ping_times[*]}"
    fi
    info "- Config: $config_file"
    info "- Logs: $log_file"
    info ""
    info "Service status:"
    info "- Timer: active (runs every 15 minutes)"
    if [ -n "$next_run" ]; then
        info "- Next run: $next_run"
    fi
    info ""
    info "Useful commands:"
    info "- Check timer status:  systemctl status claude-reset-scheduler.timer"
    info "- View logs:           journalctl -u claude-reset-scheduler.service -f"
    info "- Stop scheduler:      systemctl stop claude-reset-scheduler.timer"
    info "- Restart scheduler:   systemctl restart claude-reset-scheduler.timer"
    info "- Reconfigure:         sudo ./install.sh"
    info ""
}
```

**Step 3: Update cleanup trap to only run on error**

Replace the `cleanup_on_error` and trap:

```bash
# Track if main completed successfully
INSTALL_COMPLETE=false

trap 'cleanup_on_error' EXIT

cleanup_on_error() {
    if [ "$INSTALL_COMPLETE" = false ] && [ $? -ne 0 ]; then
        echo -e "${RED}Installation failed!${NC}"
        echo "Check logs above for details"
    fi
}
```

And add to end of `main()`:

```bash
main() {
    check_sudo
    check_existing_config
    interactive_config
    generate_config
    install_system
    activate_service
    show_success
    INSTALL_COMPLETE=true
}
```

**Step 4: Commit service activation**

```bash
git add install.sh
git commit -m "feat: implement service activation and success message"
```

---

## Task 9: Update Systemd Service Template

**Files:**
- Modify: `systemd/claude-reset-scheduler.service`

**Step 1: Update service file to be a template**

Replace content of `systemd/claude-reset-scheduler.service`:

```ini
[Unit]
Description=Claude Reset Scheduler
After=network.target

[Service]
Type=oneshot
ExecStart=/opt/claude-reset-scheduler/.venv/bin/python3 -m claude_reset_scheduler run
User=claude-reset-scheduler
Group=claude-reset-scheduler
WorkingDirectory=/opt/claude-reset-scheduler
Environment=PATH=/opt/claude-reset-scheduler/.venv/bin:/usr/bin:/bin
Environment=CLAUDE_RESET_SCHEDULER_CONFIG=/etc/claude-reset-scheduler/config.yaml
StandardOutput=journal
StandardError=journal
```

**Step 2: Verify timer file is correct**

Check `systemd/claude-reset-scheduler.timer`:

```ini
[Unit]
Description=Claude Reset Scheduler Timer

[Timer]
OnCalendar=*:0/15
Persistent=true
AccuracySec=1s

[Install]
WantedBy=timers.target
```

**Step 3: Commit systemd template**

```bash
git add systemd/claude-reset-scheduler.service
git commit -m "feat: update systemd service template for install.sh"
```

---

## Task 10: Update README with Installation Instructions

**Files:**
- Modify: `README.md`

**Step 1: Add System-Wide Installation section**

Add after the "Installation" section:

```markdown
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

## Manual Installation

For development or testing, you can install locally:
```

Then keep the existing "Using UV" and "Using Pip" sections under "Manual Installation".

**Step 2: Update Configuration section**

Update the configuration section to mention both methods:

```markdown
## Configuration

### System Installation

Configuration is created automatically by `install.sh` at `/etc/claude-reset-scheduler/config.yaml`.

To reconfigure, run: `sudo ./install.sh`

### Manual Installation

Create a `config.yaml` file at `~/.config/claude-reset-scheduler/config.yaml`:
```

**Step 3: Commit README updates**

```bash
git add README.md
git commit -m "docs: add system-wide installation instructions"
```

---

## Task 11: Create Test Plan for install.sh

**Files:**
- Create: `tests/test_install.md`

**Step 1: Write manual test plan**

Create `tests/test_install.md`:

```markdown
# install.sh Test Plan

## Prerequisites Test

```bash
# Test without sudo
./install.sh
# Expected: Error message about needing sudo

# Test without rsync (if possible)
# Expected: Error message about missing rsync
```

## Configuration Wizard Tests

```bash
# Test with defaults
sudo ./install.sh
# At each prompt, press Enter
# Expected: Uses defaults (0,1,2,3,4, 09:00, 3 pings)

# Test with custom values
sudo ./install.sh
# Days: 5,6
# Time: 10:30
# Pings: 4
# Expected: Shows Saturday, Sunday, 10:30, 14:30, 18:30, 22:30

# Test validation errors
sudo ./install.sh
# Days: 7  (invalid)
# Expected: Error, re-prompt
# Days: 0,0  (duplicates)
# Expected: Error, re-prompt
# Time: 25:00  (invalid)
# Expected: Error, re-prompt
# Pings: 10  (out of range)
# Expected: Error, re-prompt
```

## Existing Config Tests

```bash
# Install once
sudo ./install.sh
# Complete installation

# Run again
sudo ./install.sh
# Choose (U)se existing
# Expected: Skips wizard, uses existing config

# Run again
sudo ./install.sh
# Choose (R)econfigure
# Expected: Runs wizard, overwrites config

# Run again
sudo ./install.sh
# Choose (A)bort
# Expected: Exits cleanly
```

## Installation Verification

```bash
# After successful installation:

# Check files exist
ls -la /opt/claude-reset-scheduler
ls -la /etc/claude-reset-scheduler/config.yaml
ls -la /etc/systemd/system/claude-reset-scheduler.*

# Check user exists
id claude-reset-scheduler

# Check permissions
ls -l /etc/claude-reset-scheduler/config.yaml
# Expected: -rw-r----- root claude-reset-scheduler

# Check service status
systemctl status claude-reset-scheduler.timer
systemctl list-timers | grep claude-reset-scheduler

# Check logs
journalctl -u claude-reset-scheduler.service --since "1 hour ago"
```

## Cleanup for Testing

```bash
# Uninstall (for re-testing)
sudo systemctl stop claude-reset-scheduler.timer
sudo systemctl disable claude-reset-scheduler.timer
sudo rm /etc/systemd/system/claude-reset-scheduler.*
sudo systemctl daemon-reload
sudo rm -rf /opt/claude-reset-scheduler
sudo rm -rf /etc/claude-reset-scheduler
sudo rm -rf /var/log/claude-reset-scheduler
sudo rm -rf /var/lib/claude-reset-scheduler
sudo userdel claude-reset-scheduler
```
```

**Step 2: Commit test plan**

```bash
git add tests/test_install.md
git commit -m "docs: add install.sh test plan"
```

---

## Task 12: Final Testing and Documentation

**Step 1: Run full installation test**

Follow `tests/test_install.md` test plan:
1. Test prerequisites
2. Test wizard with defaults
3. Test wizard with custom values
4. Test validation errors
5. Verify installation

**Step 2: Test reconfiguration**

Run: `sudo ./install.sh`
Choose (R)econfigure, use different values
Expected: Updates config, reinstalls

**Step 3: Verify scheduler works**

Wait for next timer trigger (up to 15 minutes) or run manually:
```bash
sudo systemctl start claude-reset-scheduler.service
journalctl -u claude-reset-scheduler.service -n 50
```

**Step 4: Create final commit**

```bash
git add -A
git commit -m "chore: final testing and verification"
```

---

## Completion Checklist

- [ ] Task 1: Remove work_end_time from Config
- [ ] Task 2: Create install.sh script structure
- [ ] Task 3: Implement validation functions
- [ ] Task 4: Implement check_sudo and check_existing_config
- [ ] Task 5: Implement interactive configuration wizard
- [ ] Task 6: Implement configuration file generation
- [ ] Task 7: Implement system installation
- [ ] Task 8: Implement service activation and success message
- [ ] Task 9: Update systemd service template
- [ ] Task 10: Update README with installation instructions
- [ ] Task 11: Create test plan
- [ ] Task 12: Final testing and documentation

## Post-Implementation

After all tasks complete:
1. Test on clean system (VM recommended)
2. Update CHANGELOG.md
3. Tag release: `git tag v1.0.0`
4. Push to main branch
5. Create GitHub release with install.sh instructions
