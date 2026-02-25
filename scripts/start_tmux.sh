#!/bin/bash
# ClawDBot – tmux layout indítása (WSL-ben futtatandó)
#
# Használat:
#   wsl bash /mnt/e/openclaw_server_hosting/scripts/start_tmux.sh
#
# Layout:
#   ┌──────────────────────────┬──────────────────┐
#   │                          │  🐍 Python LLM   │
#   │   💬 ClawDBot Chat       │   (model log)    │
#   │                          ├──────────────────┤
#   │                          │  🦀 Rust API     │
#   │                          │   (server log)   │
#   └──────────────────────────┴──────────────────┘

PROJECT="/mnt/e/openclaw_server_hosting"
VENV="$PROJECT/python_llm/.venv/bin/activate"
SESSION="clawdbot"
MODELS_DIR="/mnt/w/openclaw_server_hosting/models"

# Ellenőrzések
if ! command -v tmux &>/dev/null; then
    echo "[HIBA] tmux nincs telepítve: sudo apt install tmux"
    exit 1
fi

if [ ! -f "$VENV" ]; then
    echo "[HIBA] Python venv nem létezik: $VENV"
    echo "Futtasd: bash $PROJECT/scripts/install_python_wsl.sh"
    exit 1
fi

# Meglévő session törlése
tmux kill-session -t "$SESSION" 2>/dev/null

# Új session – bal pane = Chat
tmux new-session -d -s "$SESSION" -x "$(tput cols)" -y "$(tput lines)"
tmux rename-window -t "$SESSION:0" "ClawDBot"

# Jobb oldali split (35% szélesség)
tmux split-window -t "$SESSION:0.0" -h -p 35

# Jobb felső: Python LLM szerver
tmux send-keys -t "$SESSION:0.1" \
    "export HF_HOME='$MODELS_DIR' HF_HUB_CACHE='$MODELS_DIR' HF_DATASETS_CACHE='$MODELS_DIR' HUGGINGFACE_HUB_CACHE='$MODELS_DIR' TRANSFORMERS_CACHE='$MODELS_DIR' && source '$VENV' && cd '$PROJECT/python_llm' && python model_server.py" Enter

# Jobb alsó: Rust API szerver
tmux split-window -t "$SESSION:0.1" -v -p 50
tmux send-keys -t "$SESSION:0.2" \
    "cd '$PROJECT/rust_server' && RUST_LOG=clawdbot_server=info,tower_http=warn cargo run --release" Enter

# Bal pane: Chat kliens (chat_cli.py maga vár a szerverre – nincs extra sleep)
tmux select-pane -t "$SESSION:0.0"
tmux send-keys -t "$SESSION:0.0" \
    "source '$VENV' && cd '$PROJECT/python_llm' && python chat_cli.py" Enter

# Pane feliratok
tmux set-option -t "$SESSION" pane-border-status top
tmux set-option -t "$SESSION" pane-border-format " #{pane_title} "
tmux set-option -t "$SESSION" pane-border-style "fg=colour240"
tmux set-option -t "$SESSION" pane-active-border-style "fg=colour39"

tmux select-pane -t "$SESSION:0.0" -T "💬 ClawDBot Chat"
tmux select-pane -t "$SESSION:0.1" -T "🐍 Python LLM"
tmux select-pane -t "$SESSION:0.2" -T "🦀 Rust API"

# Fókusz: Chat pane
tmux select-pane -t "$SESSION:0.0"

# Csatolódás
tmux attach-session -t "$SESSION"
