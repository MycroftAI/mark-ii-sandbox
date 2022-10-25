#!/usr/bin/env bash
set -euo pipefail

mkdir -p mycroft-gui/builddir
cd mycroft-gui/builddir

cmake ../ -DCMAKE_INSTALL_PREFIX=/usr/local \
    -DCMAKE_BUILD_TYPE=Release -DKDE_INSTALL_LIBDIR=lib \
    -DKDE_INSTALL_USE_QT_SYS_PATHS=on

make -j8
make install
