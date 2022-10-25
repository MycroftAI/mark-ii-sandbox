#!/usr/bin/env bash
set -euo pipefail

# Store build info for Mark II Skill to show devs
mkdir -p /etc/mycroft
jq -n \
    --arg datetime "$(date +%F) $(date +%T)" \
    '{"build_date": $datetime}' \
    > /etc/mycroft/build-info.json
