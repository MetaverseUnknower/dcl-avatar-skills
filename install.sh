#!/usr/bin/env bash
# Install the skills for Claude Code, Codex and/or Grok Build.
#
#   bash install.sh [all|claude|codex|grok]... [--link] [--project <dir>]
#
# Targets (default: all):
#   claude  ~/.claude/skills            (project: <dir>/.claude/skills)
#   codex   ~/.agents/skills            (project: <dir>/.agents/skills)
#   grok    ~/.agents/skills            (project: <dir>/.grok/skills); Grok also reads Claude Code skills
# --link     symlink instead of copying, so `git pull` here updates every agent
# --project  install into a repository instead of your home directory
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
targets=() link=0 project=""
while [ $# -gt 0 ]; do
  case "$1" in
    all|claude|codex|grok) targets+=("$1") ;;
    --link) link=1 ;;
    --project) project="${2:?--project needs a directory}"; shift ;;
    -h|--help) sed -n '2,13p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
  shift
done
[ ${#targets[@]} -eq 0 ] && targets=(all)

dirs=()
for t in "${targets[@]}"; do
  if [ -n "$project" ]; then
    case "$t" in
      all) dirs+=("$project/.claude/skills" "$project/.agents/skills") ;;
      claude) dirs+=("$project/.claude/skills") ;;
      codex) dirs+=("$project/.agents/skills") ;;
      grok) dirs+=("$project/.grok/skills") ;;
    esac
  else
    case "$t" in
      all) dirs+=("$HOME/.claude/skills" "$HOME/.agents/skills") ;;
      claude) dirs+=("$HOME/.claude/skills") ;;
      codex|grok) dirs+=("$HOME/.agents/skills") ;;
    esac
  fi
done

seen=" "
for d in "${dirs[@]}"; do
  case "$seen" in *" $d "*) continue ;; esac
  seen="$seen$d "
  mkdir -p "$d"
  for skill in "$here"/skills/*/; do
    name="$(basename "$skill")"
    dest="$d/$name"
    if [ -e "$dest" ] || [ -L "$dest" ]; then
      if [ -L "$dest" ] || [ -f "$dest/SKILL.md" ]; then rm -rf "$dest"; else
        echo "skip $dest: exists and isn't a skill folder" >&2; continue; fi
    fi
    if [ "$link" = 1 ]; then ln -s "${skill%/}" "$dest"; else cp -R "${skill%/}" "$dest"; fi
    echo "installed $name -> $dest"
  done
done

python3 -c 'import numpy' 2>/dev/null || echo "note: the checker scripts need numpy (pip install numpy)"
