#!/bin/sh
set -e

PACKAGE_ROOT=$(dirname $(realpath $0))

SRC_ROOT=$PACKAGE_ROOT/../../..
if [ $# -eq 1 ];
then
  VERSION="$1"
else
  VERSION="0.0.0"
fi

DEB_NAME=cxoneflow-scan-agent_${VERSION}_$(dpkg-architecture -q DEB_BUILD_ARCH).deb

echo Building $DEB_NAME

mkdir -p $PACKAGE_ROOT/deb-package/etc/cxoneflow-scan-agent
mkdir -p $PACKAGE_ROOT/deb-package/opt/cxoneflow-scan-agent

cp $PACKAGE_ROOT/control $PACKAGE_ROOT/deb-package/DEBIAN
echo "Version: $VERSION" >> $PACKAGE_ROOT/deb-package/DEBIAN/control

cp $PACKAGE_ROOT/../etc/cxoneflow-scan-agent/* $PACKAGE_ROOT/deb-package/etc/cxoneflow-scan-agent/
cp $PACKAGE_ROOT/../systemd/* $PACKAGE_ROOT/deb-package/opt/cxoneflow-scan-agent/

docker run -i --rm -w /src \
-v $SRC_ROOT:/src -v $PACKAGE_ROOT/deb-package/opt/cxoneflow-scan-agent:/dist/output \
python:3.12-bookworm sh -c \
" \
pip install -U pyinstaller && \
pip install -r requirements.txt && \
pyinstaller -F --copy-metadata aio-pika --copy-metadata jschema-to-python --specpath /dist/platform/spec --distpath /dist/output --workpath /dist/work cx_scan_agent.py \
"

dpkg-deb --build $PACKAGE_ROOT/deb-package
mv $PACKAGE_ROOT/deb-package.deb $PACKAGE_ROOT/$DEB_NAME

