#!/usr/bin/env bash
set -ex

# Directory of *this* script
this_dir="$( cd "$( dirname "$0" )" && pwd )"

venv_dir="${this_dir}/.venv"

# Create virtual environment.
#
# NOTE: System site packages are enabled so the built-in Raspberry Pi packages
# can be used.
rm -rf "${venv_dir}"
python3 -m venv --system-site-packages "${venv_dir}"
"${venv_dir}/bin/pip3" install --upgrade pip
"${venv_dir}/bin/pip3" install --upgrade wheel setuptools
"${venv_dir}/bin/pip3" install -r "${this_dir}/requirements.txt"
