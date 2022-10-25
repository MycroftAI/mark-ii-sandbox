#!/usr/bin/env bash
#
# Installs Nono Sans font family.
# Assumes files have already been copied in from Dockerfile.
#

set -euo pipefail

chmod 644 /usr/share/fonts/truetype/noto-sans/*
fc-cache -f -v

# Enable custom font configurations
ln -s /etc/fonts/conf.avail/52-noto-sans.conf /etc/fonts/conf.d/52-noto-sans.conf
ln -s /etc/fonts/conf.avail/12-mark-ii-defaults.conf /etc/fonts/conf.d/12-mark-ii-defaults.conf
