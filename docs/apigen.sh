#!/bin/bash
# script to automatically generate the psyplot api documentation using
cd `dirname $0`
# sphinx-apidoc and sed
sphinx-apidoc -f -M -e  -T -o api ../empd_admin/
# replace chapter title in psyplot.rst
sed -i -e 1,1s/.*/'Python API Reference'/ api/empd_admin.rst
sed -i -e 2,2s/.*/'===================='/ api/empd_admin.rst
