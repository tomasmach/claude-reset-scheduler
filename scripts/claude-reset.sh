#!/bin/bash
# Claude Reset Scheduler - Script pro reset 5h limit window
# Tento skript pošle jednoduchou zprávu do Claude Code pro reset časovače

set -e

# Konfigurace
LOG_FILE="${HOME}/.local/share/claude-reset-scheduler/reset.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Vytvoření adresáře pro logy pokud neexistuje
mkdir -p "$(dirname "$LOG_FILE")"

# Funkce pro logování
log() {
    echo "[$TIMESTAMP] $1" | tee -a "$LOG_FILE"
}

# Kontrola zda je claude nainstalován
if ! command -v claude &> /dev/null; then
    log "ERROR: Claude Code CLI není nainstalován nebo není v PATH"
    exit 1
fi

# Kontrola zda je nastaven ANTHROPIC_API_KEY
if [[ -z "$ANTHROPIC_API_KEY" && -z "$CLAUDE_CODE_API_KEY" ]]; then
    # Zkusíme načíst z běžných lokací
    if [[ -f "$HOME/.config/claude-code/.env" ]]; then
        export $(grep -v '^#' "$HOME/.config/claude-code/.env" | xargs)
    elif [[ -f "$HOME/.env.claude" ]]; then
        export $(grep -v '^#' "$HOME/.env.claude" | xargs)
    fi
fi

log "INFO: Spouštím Claude Code reset..."

# Hlavní příkaz - pošle jednoduchou zprávu pro reset časovače
# Použijeme --max-turns 1 pro rychlé ukončení a --output-format text pro čitelný výstup
# --allowedTools "" zakáže všechny nástroje pro rychlejší a bezpečnější běh
if claude -p "Hi Claude! Just a quick ping to start my day. No action needed, thanks!" \
    --max-turns 1 \
    --output-format text \
    --allowedTools "" 2>&1 >> "$LOG_FILE"; then
    log "SUCCESS: Reset úspěšně dokončen"
else
    log "ERROR: Reset selhal s exit kodem $?"
    exit 1
fi
