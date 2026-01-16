#! /bin/sh
set -ex

run_dir="${1}"
dest="${2}"

run="$(basename $run_dir)"

mkdir -p "${dest}"
if [ -d  "${run_dir}" ] ; then
    tar -czf "${dest}/${FB_WORKFLOW_ID}-${run}.tar.gz" "${run_dir}"
    echo "saved results to ${dest}/${FB_WORKFLOW_ID}-${run}.tar.gz"
else
    echo "did not save results to persistent store"
fi
