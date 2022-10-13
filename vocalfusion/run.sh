#!/usr/bin/env bash

this_dir='/usr/local/mycroft/mark-2'

# Load kernel module (don't fail if it's already loaded)
sudo insmod "${this_dir}/i2s_master_loader.ko" || true

# Force ALSA to configure
arecord -d 1 > /dev/null 2>&1

# Set up clocks
sudo "${this_dir}/setup_mclk"
sudo "${this_dir}/setup_bclk"

python3 "${this_dir}/setup_microphone.py" "${this_dir}/app_xvf3510_int_spi_boot_v4_2_0.bin"
python3 "${this_dir}/setup_speakers.py"
