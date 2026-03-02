#!/bin/sh
# used to set up example from https://github.com/lammpstutorials/lammpstutorials-inputs
set -e

run_dir="${1}"
mkdir -p "${run_dir}" && cd "${run_dir}"

commit="dd3dce70b883af02df293ce52491beabd8e01928"
url="https://raw.githubusercontent.com/lammpstutorials/lammpstutorials-inputs/${commit}"

for f in input.lammps CH.airebo cnt_atom.data ; do
    wget -q -O "$f" "${url}/level1/breaking-a-carbon-nanotube/breakable-bonds/${f}"
done

# small modifications to the input file.
sed -i 's/^delete_atoms/#delete_atoms/;s/^reset_atoms/#reset_atoms/' input.lammps
