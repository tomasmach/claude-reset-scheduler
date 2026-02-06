# Claude Reset Scheduler

Automatický scheduler pro Raspberry Pi, který každé ráno pošle jednoduchou zprávu přes Claude Code CLI pro reset 5h limit window.

## 💡 Proč to potřebuješ?

Claude má 5h limit window, který se počítá od momentu kdy začneš psát. Když vstáváš v 7:30 a začneš pracovat v 9:00, tento scheduler zařídí, aby se 5h timer resetoval už v 7:30. Tím získáš plných 5 hodin na práci ve flow, místo aby se ti timer resetoval uprostřed dne.

## 🚀 Instalace

### Požadavky

- Raspberry Pi (nebo jakýkoliv Linux s systemd)
- Nainstalovaný [Claude Code CLI](https://claude.ai/code)
- API klíč od Anthropic (`ANTHROPIC_API_KEY`)
- Root přístup pro instalaci systemd service

### 1. Nainstaluj Claude Code CLI

Pokud ještě nemáš Claude Code:

```bash
curl -fsSL https://claude.ai/install.sh | sh
```

### 2. Nastav API klíč

```bash
# Přidej do ~/.bashrc nebo ~/.zshrc
export ANTHROPIC_API_KEY="sk-ant-api03-xxxx"
```

### 3. Spusť instalační skript

```bash
# Naklonuj repozitář
git clone https://github.com/tomasmach/claude-reset-scheduler.git
cd claude-reset-scheduler

# Spusť instalaci (nahraď 'pi' svým uživatelem)
sudo ./install.sh -u pi -t 07:30
```

Parametry:
- `-u, --user USERNAME` - Uživatel pod kterým bude service běžet (**povinné**)
- `-t, --time HH:MM` - Čas kdy se má reset spouštět (default: 07:30)

## ⚙️ Konfigurace

### Změna času

```bash
# Edituj timer
sudo systemctl edit --full claude-reset.timer

# Změň řádek OnCalendar, například na 8:00:
# OnCalendar=*-*-* 08:00:00

# Reload a restart
sudo systemctl daemon-reload
sudo systemctl restart claude-reset.timer
```

### API klíč v souboru

Můžeš nastavit API klíč v souboru místo globální proměnné:

```bash
# Edituj soubor
nano ~/.config/claude-reset-scheduler/env

# Přidej:
ANTHROPIC_API_KEY=sk-ant-api03-xxxx
```

## 📋 Správa

### Kontrola statusu

```bash
# Status timeru
sudo systemctl status claude-reset.timer

# Příští spuštění
systemctl list-timers claude-reset.timer
```

### Manuální spuštění

```bash
# Spusť okamžitě
sudo systemctl start claude-reset@pi

# Zkontroluj logy
sudo journalctl -u claude-reset -f
```

### Logy

```bash
# Logy ze systemd
sudo journalctl -u claude-reset

# Logy ze skriptu
cat ~/.local/share/claude-reset-scheduler/reset.log
```

### Odinstalace

```bash
# Stop a disable timer
sudo systemctl stop claude-reset.timer
sudo systemctl disable claude-reset.timer

# Smaž soubory
sudo rm -f /etc/systemd/system/claude-reset.timer
sudo rm -f /etc/systemd/system/claude-reset@.service
sudo rm -rf /opt/claude-reset-scheduler

# Reload systemd
sudo systemctl daemon-reload
```

## 🔧 Alternativní řešení: Cron

Pokud preferuješ cron místo systemd timeru:

```bash
# Přidej crontab záznam
crontab -e

# Přidej tento řádek (spustí v 7:30 každý den)
30 7 * * * /usr/bin/claude -p "Good morning!" --max-turns 1 --allowedTools "" >> ~/.local/share/claude-reset.log 2>&1
```

## 🐛 Troubleshooting

### Claude není nalezen

```bash
# Ověř instalaci
which claude
claude --version

# Pokud není v PATH, přidej ho do ~/.bashrc:
export PATH="$HOME/.local/bin:$PATH"
```

### API klíč není nastaven

```bash
# Ověř proměnnou
echo $ANTHROPIC_API_KEY

# Nastav ji v ~/.bashrc a načti:
source ~/.bashrc
```

### Permission denied

```bash
# Uprav oprávnění ke skriptu
sudo chmod +x /opt/claude-reset-scheduler/scripts/claude-reset.sh
```

## 📁 Struktura projektu

```
claude-reset-scheduler/
├── scripts/
│   └── claude-reset.sh      # Hlavní bash skript
├── systemd/
│   ├── claude-reset.service # Template service soubor
│   └── claude-reset.timer   # Timer (7:30 každý den)
├── install.sh               # Instalační skript
└── README.md                # Tento soubor
```

## 📝 Licence

MIT License - viz LICENSE soubor.
