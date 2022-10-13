#!/usr/bin/env bash

# Directory of *this* script
this_dir="$( cd "$( dirname "$0" )" && pwd )"

vf_dir="${this_dir}/vocalfusion-rpi-setup-5.2.0"

# -----------------------------------------------------------------------------

echo 'Installing required packages'
sudo apt-get update
sudo apt-get install --yes build-essential raspberrypi-kernel-headers python3-smbus

echo 'Building kernel module'
cd "${vf_dir}" && ./setup.sh

echo 'Building support tools'
cd "${vf_dir}/resources/clk_dac_setup" && make
