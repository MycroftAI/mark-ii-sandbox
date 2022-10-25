#!/usr/bin/env bash
set -euo pipefail

mkdir -p lottie-qml/builddir
cd lottie-qml/builddir
cmake .. -DCMAKE_INSTALL_PREFIX=/usr/local -DCMAKE_BUILD_TYPE=Release \
    -DKDE_INSTALL_LIBDIR=lib -DKDE_INSTALL_USE_QT_SYS_PATHS=ON

make -j8
make install
