#!/bin/bash
# Instalační skript pro Claude Reset Scheduler na Raspberry Pi

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="/opt/claude-reset-scheduler"
USER_NAME=""

# Barvy pro výstup
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Funkce pro zobrazení nápovědy
show_help() {
    cat << EOF
Použití: sudo ./install.sh [MOŽNOSTI]

Možnosti:
    -u, --user USERNAME     Uživatel pod kterým bude service běžet (povinné)
    -t, --time HH:MM        Čas kdy se má reset spouštět (default: 07:30)
    -h, --help              Zobrazit tuto nápovědu

Příklad:
    sudo ./install.sh -u pi -t 07:30
EOF
}

# Parsování argumentů
while [[ $# -gt 0 ]]; do
    case $1 in
        -u|--user)
            USER_NAME="$2"
            shift 2
            ;;
        -t|--time)
            RESET_TIME="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            print_error "Neznámá možnost: $1"
            show_help
            exit 1
            ;;
    esac
done

# Kontrola root oprávnění
if [[ $EUID -ne 0 ]]; then
   print_error "Tento skript musí běžet jako root (použij sudo)"
   exit 1
fi

# Kontrola uživatele
if [[ -z "$USER_NAME" ]]; then
    print_error "Musíš zadat uživatele pomocí -u nebo --user"
    show_help
    exit 1
fi

if ! id "$USER_NAME" &>/dev/null; then
    print_error "Uživatel '$USER_NAME' neexistuje"
    exit 1
fi

# Default čas
RESET_TIME="${RESET_TIME:-07:30}"

# Validace času
if ! [[ "$RESET_TIME" =~ ^[0-9]{2}:[0-9]{2}$ ]]; then
    print_error "Neplatný formát času. Použij HH:MM (např. 07:30)"
    exit 1
fi

print_info "Začínám instalaci Claude Reset Scheduler..."
print_info "Uživatel: $USER_NAME"
print_info "Čas resetu: $RESET_TIME"

# Kontrola zda je nainstalován claude
if ! sudo -u "$USER_NAME" bash -c 'command -v claude' &> /dev/null; then
    print_warn "Claude Code CLI není nainstalován pro uživatele $USER_NAME"
    echo ""
    echo "Návod k instalaci Claude Code:"
    echo "  curl -fsSL https://claude.ai/install.sh | sh"
    echo ""
    read -p "Chceš pokračovat v instalaci scheduleru? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Vytvoření instalačního adresáře
print_info "Vytvářím instalační adresáře..."
mkdir -p "$INSTALL_DIR/scripts"
mkdir -p "$INSTALL_DIR/systemd"

# Kopírování souborů
print_info "Kopíruji soubory..."
cp "$SCRIPT_DIR/scripts/claude-reset.sh" "$INSTALL_DIR/scripts/"
chmod +x "$INSTALL_DIR/scripts/claude-reset.sh"

# Vytvoření timer souboru s upraveným časem
print_info "Konfiguruji časovač na $RESET_TIME..."
cat > "$INSTALL_DIR/systemd/claude-reset.timer" << EOF
[Unit]
Description=Claude Code Reset Timer - Spouští reset každý den v $RESET_TIME
Documentation=https://github.com/tomasmach/claude-reset-scheduler

[Timer]
# Spustit každý den v $RESET_TIME
OnCalendar=*-*-* $RESET_TIME:00

# Přesnost timeru (spustí se do 1 minuty od naplánovaného času)
AccuracySec=1min

# Spustit při bootu pokud jsme čas zmeškali
Persistent=true

[Install]
WantedBy=timers.target
EOF

# Vytvoření service souboru s uživatelem
print_info "Konfiguruji service pro uživatele $USER_NAME..."
cat > "$INSTALL_DIR/systemd/claude-reset@.service" << EOF
[Unit]
Description=Claude Code Reset - Reset 5h limit window
Documentation=https://github.com/tomasmach/claude-reset-scheduler
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User=%i
Environment="HOME=/home/%i"
Environment="PATH=/usr/local/bin:/usr/bin:/bin:/home/%i/.local/bin"
EnvironmentFile=-/home/%i/.config/claude-reset-scheduler/env
ExecStart=$INSTALL_DIR/scripts/claude-reset.sh
StandardOutput=journal
StandardError=journal
SyslogIdentifier=claude-reset
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/home/%i/.local/share/claude-reset-scheduler
TimeoutSec=120
EOF

# Kopírování systemd souborů
print_info "Instaluji systemd service a timer..."
cp "$INSTALL_DIR/systemd/claude-reset@.service" /etc/systemd/system/
cp "$INSTALL_DIR/systemd/claude-reset.timer" /etc/systemd/system/

# Vytvoření adresáře pro konfiguraci a logy
print_info "Vytvářím adresáře pro konfiguraci a logy..."
sudo -u "$USER_NAME" mkdir -p "/home/$USER_NAME/.config/claude-reset-scheduler"
sudo -u "$USER_NAME" mkdir -p "/home/$USER_NAME/.local/share/claude-reset-scheduler"

# Vytvoření template pro environment variables
if [[ ! -f "/home/$USER_NAME/.config/claude-reset-scheduler/env" ]]; then
    cat > "/home/$USER_NAME/.config/claude-reset-scheduler/env" << EOF
# Environment variables pro Claude Reset Scheduler
# Sem dej svůj API klíč pokud není nastaven globálně

# ANTHROPIC_API_KEY=sk-ant-xxxx
EOF
    sudo -u "$USER_NAME" chmod 600 "/home/$USER_NAME/.config/claude-reset-scheduler/env"
    print_info "Vytvořen soubor s environment variables: /home/$USER_NAME/.config/claude-reset-scheduler/env"
fi

# Reload systemd a enable timer
print_info "Aktivuji systemd timer..."
systemctl daemon-reload
systemctl enable claude-reset.timer
systemctl start claude-reset.timer

print_info "Instalace dokončena!"
echo ""
echo "==============================================="
echo "Status timeru:"
systemctl status claude-reset.timer --no-pager

echo ""
echo "==============================================="
echo "Další příkazy:"
echo "  Kontrola statusu:  sudo systemctl status claude-reset.timer"
echo "  Logy:              sudo journalctl -u claude-reset -f"
echo "  Manuální spuštění: sudo systemctl start claude-reset@$USER_NAME"
echo "  Editace času:      sudo systemctl edit --full claude-reset.timer"
echo ""
echo "DŮLEŽITÉ:"
echo "1. Ujisti se že máš nainstalovaný Claude Code: curl -fsSL https://claude.ai/install.sh | sh"
echo "2. Ověř že máš nastavený API klíč v ~/.config/claude-reset-scheduler/env nebo globálně"
echo "3. Testuj manuálně: sudo systemctl start claude-reset@$USER_NAME"
