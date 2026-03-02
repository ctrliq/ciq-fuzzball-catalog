#!/bin/sh
# Used to set up example from https://github.com/lammpstutorials/lammpstutorials-inputs
set -e

run_dir="${1}"
mkdir -p "${run_dir}" && cd "${run_dir}"

commit="dd3dce70b883af02df293ce52491beabd8e01928"
url="https://raw.githubusercontent.com/lammpstutorials/lammpstutorials-inputs/${commit}"

for f in input.lammps cnt_molecular.data parm.lammps ; do
    wget -q -O "$f" "${url}/level1/breaking-a-carbon-nanotube/unbreakable-bonds/${f}"
done

# need to make one mod for the older lammps
sed -i 's/^delete_atoms/#delete_atoms/;s/^reset_atoms/#reset_atoms/' input.lammps
