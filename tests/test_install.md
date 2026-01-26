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
