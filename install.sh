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

# Global state
USE_EXISTING_CONFIG=false

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
    local start_minutes=$((10#$hour * 60 + 10#$minute))

    local times=()
    local current_minutes=$start_minutes

    for ((i=0; i<num_pings; i++)); do
        local h=$(( (current_minutes / 60) % 24 ))
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
interactive_config() { :; }
generate_config() { :; }
install_system() { :; }
activate_service() { :; }
show_success() { :; }

main
