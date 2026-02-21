#!/bin/bash
# One-shot backfill retry — scheduled after 429 cooldown
# Triggered by system crontab

export PATH="$HOME/.nvm/versions/node/v22.22.0/bin:/opt/homebrew/Cellar/libpq/18.2/bin:$PATH"
cd "$HOME/Constructive/lib-count/packages/stats-db" || exit 1

# Load pgpm env
eval "$(pgpm env)"

LOG="$HOME/Constructive/lib-count/backfill-retry-$(date +%Y%m%d-%H%M).log"
echo "[$(date)] Starting backfill retry..." | tee "$LOG"

pnpm npm:fetch:downloads -- --backfill --concurrent 1 --delay 1500 >> "$LOG" 2>&1
EXIT=$?

if [ $EXIT -eq 0 ]; then
  echo "[$(date)] Backfill succeeded. Running reports..." | tee -a "$LOG"
  pnpm npm:report >> "$LOG" 2>&1
  pnpm npm:badges >> "$LOG" 2>&1
  pnpm npm:readme >> "$LOG" 2>&1

  cd "$HOME/Constructive/lib-count"
  git add -A
  git commit -m "chore: backfill suspicious zero-download days $(date +%Y-%m-%d)" >> "$LOG" 2>&1
  BOT_TOKEN=$(gh auth token --hostname github.com --user pyramation-bot)
  GH_TOKEN=$BOT_TOKEN git push origin main >> "$LOG" 2>&1
  echo "[$(date)] Done. Pushed to fork." | tee -a "$LOG"
else
  echo "[$(date)] Backfill FAILED (exit $EXIT) — check log: $LOG" | tee -a "$LOG"
fi
