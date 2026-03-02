#!/bin/sh
# used to set up example from https://github.com/lammpstutorials/lammpstutorials-inputs
set -e

run_dir="${1}"
mkdir -p "${run_dir}" && cd "${run_dir}"

commit="4e249a6f7a0f8f8057bf72c07d39841a297e69a6"
url="https://raw.githubusercontent.com/lammpstutorials/lammpstutorials-inputs/${commit}"

wget -q -O "input.lammps" "${url}/level1/lennard-jones-fluid/improved-input/input.md.lammps"
wget -q -O "minimized_coordinate.data" "${url}/level1/lennard-jones-fluid/improved-input/minimized_coordinate.data"
