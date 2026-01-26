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
SERVICE_NAME="claude-reset-scheduler"

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

check_sudo() {
    if [ "$EUID" -ne 0 ]; then
        error "This script must be run with sudo"
        echo "Usage: sudo ./uninstall.sh"
        exit 1
    fi
    success "Running as root"
}

confirm_uninstall() {
    info ""
    warning "This will remove Claude Reset Scheduler and all its files."
    warning "Configuration and logs will be permanently deleted."
    info ""

    while true; do
        read -p "Are you sure you want to uninstall? (yes/no): " choice
        case "$choice" in
            yes|YES)
                return 0
                ;;
            no|NO)
                info "Uninstall cancelled"
                exit 0
                ;;
            *)
                error "Please answer 'yes' or 'no'"
                ;;
        esac
    done
}

stop_service() {
    info ""
    info "=== Stopping Service ==="

    if systemctl is-active --quiet "${SERVICE_NAME}.timer"; then
        info "Stopping systemd timer..."
        systemctl stop "${SERVICE_NAME}.timer"
        success "Timer stopped"
    else
        info "Timer already stopped"
    fi

    if systemctl is-enabled --quiet "${SERVICE_NAME}.timer" 2>/dev/null; then
        info "Disabling systemd timer..."
        systemctl disable "${SERVICE_NAME}.timer"
        success "Timer disabled"
    else
        info "Timer already disabled"
    fi
}

remove_systemd_files() {
    info ""
    info "=== Removing Systemd Files ==="

    if [ -f "/etc/systemd/system/${SERVICE_NAME}.service" ]; then
        rm -f "/etc/systemd/system/${SERVICE_NAME}.service"
        success "Removed service file"
    fi

    if [ -f "/etc/systemd/system/${SERVICE_NAME}.timer" ]; then
        rm -f "/etc/systemd/system/${SERVICE_NAME}.timer"
        success "Removed timer file"
    fi

    systemctl daemon-reload
    success "Reloaded systemd daemon"
}

remove_directories() {
    info ""
    info "=== Removing Directories ==="

    if [ -d "$INSTALL_DIR" ]; then
        rm -rf "$INSTALL_DIR"
        success "Removed installation directory: $INSTALL_DIR"
    fi

    if [ -d "$CONFIG_DIR" ]; then
        rm -rf "$CONFIG_DIR"
        success "Removed configuration directory: $CONFIG_DIR"
    fi

    if [ -d "$LOG_DIR" ]; then
        rm -rf "$LOG_DIR"
        success "Removed log directory: $LOG_DIR"
    fi

    if [ -d "$STATE_DIR" ]; then
        rm -rf "$STATE_DIR"
        success "Removed state directory: $STATE_DIR"
    fi
}

remove_user() {
    info ""
    info "=== Removing System User ==="

    if id "$SERVICE_USER" &>/dev/null; then
        userdel "$SERVICE_USER"
        success "Removed system user: $SERVICE_USER"
    else
        info "System user already removed"
    fi
}

show_completion() {
    info ""
    echo -e "${GREEN}✓ Uninstall complete!${NC}"
    info ""
    info "Claude Reset Scheduler has been completely removed from your system."
    info ""
}

main() {
    check_sudo
    confirm_uninstall
    stop_service
    remove_systemd_files
    remove_directories
    remove_user
    show_completion
}

main
