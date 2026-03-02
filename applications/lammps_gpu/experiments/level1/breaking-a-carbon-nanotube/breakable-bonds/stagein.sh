#!/bin/sh
# used to set up example from https://github.com/lammpstutorials/lammpstutorials-inputs
set -e

run_dir="${1}"
mkdir -p "${run_dir}" && cd "${run_dir}"

commit="4e249a6f7a0f8f8057bf72c07d39841a297e69a6"
url="https://raw.githubusercontent.com/lammpstutorials/lammpstutorials-inputs/${commit}"

for f in input.lammps CH.airebo cnt_atom.data ; do
    wget -q -O "$f" "${url}/level1/breaking-a-carbon-nanotube/breakable-bonds/${f}"
done

# small modifications to the input file.
sed -i 's/^delete_atoms/#delete_atoms/;s/^reset_atoms/#reset_atoms/' input.lammps
