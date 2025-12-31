#! /bin/sh
set -ex

run="${1}"
dest="${2}"

mkdir -p "${dest}"
if [ -d  "${run}" ] ; then
    tar -czf "${dest}/${FB_WORKFLOW_ID}-${run}.tar.gz" "${run}"
    echo "saved results to ${dest}/${FB_WORKFLOW_ID}-${run}.tar.gz"
else
    echo "did not save results to persistent store"
fi
