#!/usr/bin/env bash
set -ex

# Directory of *this* script
this_dir="$( cd "$( dirname "$0" )" && pwd )"

venv_dir="${this_dir}/.venv"
if [ ! -d "${venv_dir}" ]; then
    echo "Missing virtual environment in ${venv_dir}";
    echo 'Did you run install.sh?';
    exit 1;
fi

"${venv_dir}/bin/python3" "${this_dir}/dbus_server.py"
