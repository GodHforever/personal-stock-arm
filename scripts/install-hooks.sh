#!/bin/bash
# 安装Git hooks到.git/hooks/
# 用法: bash scripts/install-hooks.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
HOOKS_SRC="$SCRIPT_DIR/hooks"
HOOKS_DST="$ROOT/.git/hooks"

echo "安装Git hooks..."

for hook in "$HOOKS_SRC"/*; do
    hook_name=$(basename "$hook")
    cp "$hook" "$HOOKS_DST/$hook_name"
    chmod +x "$HOOKS_DST/$hook_name"
    echo "  已安装: $hook_name"
done

echo "Git hooks安装完成。"
