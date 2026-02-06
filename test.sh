#!/bin/bash
# Testovací skript pro Claude Reset Scheduler
# Spusť na Raspberry Pi pro ověření že vše funguje

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASS=0
FAIL=0

test_pass() {
    echo -e "${GREEN}✓${NC} $1"
    ((PASS++))
}

test_fail() {
    echo -e "${RED}✗${NC} $1"
    ((FAIL++))
}

test_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

echo "=============================================="
echo "Claude Reset Scheduler - Test Suite"
echo "=============================================="
echo ""

# 1. Test bash syntaxe
echo "1. Kontrola syntaxe skriptů..."
if bash -n scripts/claude-reset.sh 2>/dev/null; then
    test_pass "claude-reset.sh má validní syntaxi"
else
    test_fail "claude-reset.sh má chybu v syntaxi"
fi

if bash -n install.sh 2>/dev/null; then
    test_pass "install.sh má validní syntaxi"
else
    test_fail "install.sh má chybu v syntaxi"
fi

# 2. Test přítomnosti claude
echo ""
echo "2. Kontrola Claude Code CLI..."
if command -v claude &> /dev/null; then
    test_pass "Claude Code CLI je nainstalován"
    CLAUDE_VERSION=$(claude --version 2>/dev/null || echo "neznámá")
    echo "   Verze: $CLAUDE_VERSION"
else
    test_fail "Claude Code CLI není nainstalován"
    echo "   Návod: curl -fsSL https://claude.ai/install.sh | sh"
fi

# 3. Test API klíče
echo ""
echo "3. Kontrola API klíče..."
if [[ -n "$ANTHROPIC_API_KEY" || -n "$CLAUDE_CODE_API_KEY" ]]; then
    test_pass "API klíč je nastaven v proměnných"
else
    test_warn "API klíč není v proměnných prostředí"
    if [[ -f "$HOME/.config/claude-reset-scheduler/env" ]]; then
        test_pass "API klíč může být v ~/.config/claude-reset-scheduler/env"
    else
        test_warn "Vytvoř soubor: ~/.config/claude-reset-scheduler/env"
    fi
fi

# 4. Test systemd
echo ""
echo "4. Kontrola systemd..."
if command -v systemctl &> /dev/null; then
    test_pass "systemctl je dostupný"
    
    if systemctl list-timers claude-reset.timer &>/dev/null; then
        test_pass "claude-reset.timer je aktivní"
        echo ""
        echo "   Příští spuštění:"
        systemctl list-timers claude-reset.timer --no-pager 2>/dev/null | tail -2
    else
        test_warn "claude-reset.timer není nainstalován"
        echo "   Spusť: sudo ./install.sh -u $(whoami)"
    fi
else
    test_fail "systemctl není dostupný (není systemd?)"
fi

# 5. Test adresářů
echo ""
echo "5. Kontrola adresářů..."
if [[ -d "$HOME/.local/share/claude-reset-scheduler" ]]; then
    test_pass "Log adresář existuje"
else
    test_warn "Log adresář neexistuje (vytvoří se při prvním běhu)"
fi

# 6. Simulace volání (dry-run)
echo ""
echo "6. Simulace volání claude -p..."
if command -v claude &> /dev/null; then
    echo "   Testuji: claude -p 'test' --max-turns 1 --allowedTools ''"
    if timeout 30 claude -p "Test message from claude-reset-scheduler test suite" \
        --max-turns 1 \
        --allowedTools "" \
        --output-format text 2>/dev/null | head -5; then
        test_pass "Claude odpověděl na testovací zprávu"
    else
        test_warn "Claude neodpověděl (může být offline nebo chyba API klíče)"
    fi
else
    test_warn "Přeskočeno - Claude není nainstalován"
fi

# 7. Test log souboru
echo ""
echo "7. Kontrola logů..."
if [[ -f "$HOME/.local/share/claude-reset-scheduler/reset.log" ]]; then
    test_pass "Log soubor existuje"
    echo ""
    echo "   Poslední záznamy:"
    tail -3 "$HOME/.local/share/claude-reset-scheduler/reset.log" 2>/dev/null | sed 's/^/   /'
else
    test_warn "Zatím žádné logy (timer se zatím nespustil)"
fi

# Souhrn
echo ""
echo "=============================================="
echo "VÝSLEDEK: $PASS OK, $FAIL chyb"
echo "=============================================="

if [[ $FAIL -eq 0 ]]; then
    echo -e "${GREEN}Vše vypadá dobře!${NC}"
    exit 0
else
    echo -e "${RED}Některé testy selhaly.${NC}"
    exit 1
fi
