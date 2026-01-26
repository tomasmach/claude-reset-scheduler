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
CONFIG_ACTIVE_DAYS=""
CONFIG_FIRST_PING=""
CONFIG_NUM_PINGS=""

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
interactive_config() {
    # Skip if using existing config
    if [ "$USE_EXISTING_CONFIG" = true ]; then
        return 0
    fi

    info ""
    info "======================================"
    info "  Configuration Wizard"
    info "======================================"
    info ""
    info "This wizard will help you configure the ping schedule."
    info ""

    # Prompt for active days
    while true; do
        info "Which days should be active?"
        info "  0=Monday, 1=Tuesday, 2=Wednesday, 3=Thursday,"
        info "  4=Friday, 5=Saturday, 6=Sunday"
        info "  Example: 0,1,2,3,4 for weekdays"
        read -p "Active days: " days_input
        days_input="${days_input:-0,1,2,3,4}"

        if validate_days "$days_input"; then
            CONFIG_ACTIVE_DAYS="${days_input// /}"
            success "Days validated: $CONFIG_ACTIVE_DAYS"
            break
        else
            error "Invalid format. Enter comma-separated numbers 0-6 (no duplicates)"
        fi
    done

    info ""

    # Prompt for first ping time
    while true; do
        info "What time should the first ping occur? (24-hour format)"
        info "  Example: 09:00 for 9 AM"
        read -p "First ping time: " time_input
        time_input="${time_input:-09:00}"

        if validate_time "$time_input"; then
            CONFIG_FIRST_PING="$time_input"
            success "Time validated: $CONFIG_FIRST_PING"
            break
        else
            error "Invalid format. Enter time as HH:MM (00:00 to 23:59)"
        fi
    done

    info ""

    # Prompt for number of pings
    while true; do
        info "How many pings per day? (1-5)"
        info "  Pings occur every 5 hours starting from first ping time"
        read -p "Number of pings: " pings_input
        pings_input="${pings_input:-3}"

        if validate_pings "$pings_input"; then
            CONFIG_NUM_PINGS="$pings_input"
            success "Number validated: $CONFIG_NUM_PINGS"
            break
        else
            error "Invalid number. Enter a number between 1 and 5"
        fi
    done

    info ""
    info "======================================"
    info "  Configuration Summary"
    info "======================================"
    info ""

    # Show active days with names
    info "Active days:"
    IFS=',' read -ra day_array <<< "$CONFIG_ACTIVE_DAYS"
    for day in "${day_array[@]}"; do
        info "  - $(day_name "$day")"
    done

    info ""
    info "Ping schedule:"

    # Calculate and show ping times
    read -ra times <<< "$(calculate_ping_times_bash "$CONFIG_FIRST_PING" "$CONFIG_NUM_PINGS")"
    for time in "${times[@]}"; do
        info "  - $time"
    done

    info ""

    # Confirmation prompt
    while true; do
        read -p "$(echo -e "${YELLOW}Proceed with this configuration? (y/n)${NC} ")" confirm
        case "$confirm" in
            [Yy]* )
                success "Configuration confirmed"
                return 0
                ;;
            [Nn]* )
                error "Configuration rejected"
                info "Installation aborted by user"
                exit 0
                ;;
            * )
                error "Invalid choice. Please enter y or n."
                ;;
        esac
    done
}
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
install_system() { :; }
activate_service() { :; }
show_success() { :; }

main
