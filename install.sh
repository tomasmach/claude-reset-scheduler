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
trap 'cleanup_on_error' ERR

cleanup_on_error() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        echo -e "${RED}Installation failed!${NC}"
        echo "Check logs above for details"
    fi
    exit $exit_code
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
