#!/usr/bin/env bash
# Copyright 2022 Mycroft AI Inc.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
# -----------------------------------------------------------------------------
#
# Generates burnable image from Docker build artifacts and original Raspberry Pi
# OS boot partition.
#
# Before running this, you should run:
# - raspberry-pi-os/img2tar.py
# - make
#
# After running this, burn custom.img

set -ex

this_dir="$( cd "$( dirname "$0" )" && pwd )"

if [ -z "$1" ]; then
    image="${this_dir}/custom.img"
else
    image="$1"
fi

# custom_image_bytes=4096
custom_image_bytes=7144
pi_dir="${this_dir}/raspberry-pi-os"

function detach {
    # Detach loopback devices
    sudo losetup --all | grep "${image}" | \
        while read -r line; do
            echo "${line}" | awk -F: '{ print $1 }' | xargs -r sudo losetup --detach
        done
}

function fix_cmdline {
    sudo sed -i 's/console=tty1/loglevel=0 fastboot consoleblank=0 vt.global_cursor_default=0/' "$1"
}

detach

# Generate empty image and add parition table
dd if=/dev/zero of="${image}" bs=1M count="${custom_image_bytes}"
/sbin/sfdisk "${image}" < "${pi_dir}/partition_table.txt"

mount_dir='/mnt/pigpen'
sudo umount "${mount_dir}" || true
sudo mkdir -p "${mount_dir}"

# Mount with loopback
sudo losetup --find --partscan "${image}"
lo_dev="$(sudo losetup --all | grep "${image}" | awk -F: '{ print $1 }')"

# Copy boot partition
sudo mkfs.fat "${lo_dev}p1"
sudo mount "${lo_dev}p1" "${mount_dir}"
sudo tar xf "${pi_dir}/p1.tar" --no-same-owner -C "${mount_dir}"
sudo rsync -r "${this_dir}/boot/" "${mount_dir}/"
# fix_cmdline "${mount_dir}/cmdline.txt"
sudo umount "${mount_dir}"

# Copy user partition
sudo mkfs.ext4 "${lo_dev}p2"
sudo mount "${lo_dev}p2" "${mount_dir}"
sudo tar xf "${this_dir}/mycroft.tar" -C "${mount_dir}"
sudo umount "${mount_dir}"

detach
