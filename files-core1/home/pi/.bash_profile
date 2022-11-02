#!/usr/bin/env bash
if [[ -d '/opt/mycroft/bin' ]]; then
    export PATH="/opt/mycroft/bin:${PATH}"
fi

source "${HOME}/.bashrc"
