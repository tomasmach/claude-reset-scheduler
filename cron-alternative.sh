#!/bin/bash
# Alternativní jednoduché řešení pomocí cron místo systemd
# Tento skript nainstaluje crontab záznam

set -e

USER_NAME=$(whoami)
RESET_TIME="${1:-07:30}"

# Parsování času
HOUR=$(echo "$RESET_TIME" | cut -d: -f1)
MIN=$(echo "$RESET_TIME" | cut -d: -f2)

echo "Instaluji crontab pro uživatele $USER_NAME"
echo "Čas spuštění: $RESET_TIME"

# Vytvoření adresáře pro logy
mkdir -p "$HOME/.local/share/claude-reset-scheduler"

# Kontrola zda je claude nainstalován
if ! command -v claude &> /dev/null; then
    echo "ERROR: Claude Code CLI není nainstalován"
    echo "Nainstaluj pomocí: curl -fsSL https://claude.ai/install.sh | sh"
    exit 1
fi

# Vytvoření log souboru
LOG_FILE="$HOME/.local/share/claude-reset-scheduler/reset.log"

# Přidání do crontab
CRON_CMD="$MIN $HOUR * * * /usr/bin/claude -p \"Hi Claude! Morning ping.\" --max-turns 1 --allowedTools \"\" >> $LOG_FILE 2>&1"

# Záloha stávajícího crontabu
if crontab -l &>/dev/null; then
    crontab -l > /tmp/crontab.backup
    echo "Záloha crontabu vytvořena: /tmp/crontab.backup"
fi

# Přidání nového záznamu
(crontab -l 2>/dev/null; echo "# Claude Reset Scheduler - $(date)") | crontab -
(crontab -l 2>/dev/null; echo "$CRON_CMD") | crontab -

echo "Crontab nainstalován!"
echo ""
echo "Zobrazení crontabu:"
crontab -l
echo ""
echo "Logy budou v: $LOG_FILE"
echo ""
echo "Pro odinstalaci spusť: crontab -e a smaž řádky s 'claude'"
