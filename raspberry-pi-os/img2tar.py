#!/usr/bin/env python3
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

import argparse
import logging
import os
import re
import subprocess
import time
import typing
from pathlib import Path

LOG = logging.getLogger("img2tar")
PARTITIONS = ["p1", "p2"]

ENV = dict(os.environ)
ENV["PATH"] = ENV["PATH"] + ":/sbin"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-i", "--image", required=True, help="Path to Raspberry Pi OS .img file"
    )
    parser.add_argument(
        "--resize-factor",
        type=float,
        default=1.0,
        help="Multiplier for data partition size (default: 1.0)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG)
    LOG.debug(args)

    # -------------------------------------------------------------------------
    # Unpack source image
    # -------------------------------------------------------------------------

    src_img_path = Path(args.image)

    table_path = Path("partition_table.txt")
    extract_partition_table(src_img_path, table_path, resize_factor=args.resize_factor)

    src_device_path = mount_image(src_img_path)

    try:
        src_mountpoints = get_mountpoints(src_device_path)
        while len(src_mountpoints) != len(PARTITIONS):
            time.sleep(1)
            src_mountpoints = get_mountpoints(src_device_path)

        LOG.info(src_mountpoints)

        for partition in PARTITIONS:
            tar_path = Path(f"{partition}.tar")
            mount_path = src_mountpoints[partition]
            tar_partition(mount_path, tar_path)
    finally:
        unmount_image(src_device_path)


def tar_partition(mount_path: str, tar_path: Path, sudo: bool = True):
    tar_cmd = [
        "tar",
        "-cf",
        str(tar_path),
        "-C",
        str(mount_path),
        "--numeric-owner",
        ".",
    ]

    if sudo:
        tar_cmd.insert(0, "sudo")

    LOG.debug(tar_cmd)
    subprocess.check_call(tar_cmd)
    LOG.info("Extracted partition to %s", tar_path)


def extract_partition_table(
    img_path: Path, table_path: Path, resize_factor: float = 1.0
):
    def replace_sectors(match) -> str:
        current_sectors = int(match.group(1))
        new_sectors = int(current_sectors * resize_factor)
        rest_of_string = match.group(2)

        return f"{new_sectors}{rest_of_string}"

    with open(table_path, "w", encoding="ascii") as table_file:
        extract_cmd = ["sfdisk", "--dump", str(img_path)]
        LOG.debug(extract_cmd)
        output_str = subprocess.check_output(
            extract_cmd, universal_newlines=True, env=ENV
        )
        for line in output_str.splitlines():
            line = line.strip()

            if resize_factor != 1.0:
                line = re.sub(r" ([0-9]+)(, type=83)$", replace_sectors, line)

            print(line, file=table_file)

        LOG.info("Extracted partition table from %s to %s", img_path, table_path)


def mount_image(img_path: Path) -> str:
    mount_cmd = [
        "udisksctl",
        "loop-setup",
        "--file",
        str(img_path),
    ]
    LOG.debug(mount_cmd)

    result_str = subprocess.check_output(mount_cmd, universal_newlines=True)

    # Mapped file XXX.img as /dev/YYY.
    device_path = result_str.strip().split()[-1][:-1]
    LOG.info("Mounted %s at %s", img_path, device_path)

    return device_path


def get_mountpoints(device_path: str) -> typing.Dict[str, str]:
    mountpoints = {}

    for partition in PARTITIONS:
        info_cmd = ["udisksctl", "info", "--block-device", f"{device_path}{partition}"]
        LOG.debug(info_cmd)
        output_str = subprocess.check_output(info_cmd, universal_newlines=True)
        for line in output_str.splitlines():
            words = line.strip().split()
            # MountPoints:        /media/XXX/YYY
            if (len(words) == 2) and (words[0] == "MountPoints:"):
                mountpoints[partition] = words[1]

    return mountpoints


def unmount_image(device_path: str):
    for partition in PARTITIONS:
        unmount_cmd = [
            "udisksctl",
            "unmount",
            "--block-device",
            f"{device_path}{partition}",
        ]
        LOG.debug(unmount_cmd)
        subprocess.check_call(unmount_cmd)

    LOG.info("Unmounted %s", device_path)


if __name__ == "__main__":
    main()
