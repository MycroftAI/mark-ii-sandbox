#!/usr/bin/env bash
set -euo pipefail

sed -i 's/CW/NORMAL/g' mycroft-gui-mark-2/lookandfeel/contents/plasmoidsetupscripts/org.kde.mycroft.mark2.js

mkdir -p mycroft-gui-mark-2/builddir
cd mycroft-gui-mark-2/builddir

cmake ../ -DCMAKE_INSTALL_PREFIX=/usr/local \
    -DCMAKE_BUILD_TYPE=Release -DKDE_INSTALL_LIBDIR=lib \
    -DKDE_INSTALL_USE_QT_SYS_PATHS=on

make -j8
make install
