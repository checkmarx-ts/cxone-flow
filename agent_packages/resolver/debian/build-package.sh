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

mkdir -p $PACKAGE_ROOT/deb-package/etc/cxoneflow-resolver-agent
mkdir -p $PACKAGE_ROOT/deb-package/opt/cxoneflow-resolver-agent

cp $PACKAGE_ROOT/control $PACKAGE_ROOT/deb-package/DEBIAN
echo "Version: $VERSION" >> $PACKAGE_ROOT/deb-package/DEBIAN/control

cp $PACKAGE_ROOT/../etc/cxoneflow-resolver-agent/* $PACKAGE_ROOT/deb-package/etc/cxoneflow-resolver-agent/
cp $PACKAGE_ROOT/../systemd/* $PACKAGE_ROOT/deb-package/opt/cxoneflow-resolver-agent/

docker run -it --rm -w /src \
-v $SRC_ROOT:/src -v $PACKAGE_ROOT/deb-package/opt/cxoneflow-resolver-agent:/dist/output \
python:3.12-bookworm sh -c \
" \
pip install -U pyinstaller && \
pip install -r requirements.txt && \
pyinstaller -F --copy-metadata aio-pika --specpath /dist/platform/spec --distpath /dist/output --workpath /dist/work resolver_agent.py \
"

dpkg-deb --build $PACKAGE_ROOT/deb-package
mv $PACKAGE_ROOT/deb-package.deb $PACKAGE_ROOT/cxoneflow-resolver-agent_${VERSION}_$(dpkg-architecture -q DEB_BUILD_ARCH).deb

