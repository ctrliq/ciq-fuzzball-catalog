#! /bin/sh
# used to set up example from https://github.com/lammpstutorials/lammpstutorials-inputs
# This job runs the md part of the second lennard jones liquid example
set -ex

run="${1}"
mkdir -p "${run}" && cd "${run}" || exit 1

commit="4e249a6f7a0f8f8057bf72c07d39841a297e69a6"
url="https://raw.githubusercontent.com/lammpstutorials/lammpstutorials-inputs/${commit}"

wget -q -O "input.lammps" "${url}/level1/lennard-jones-fluid/improved-input/input.md.lammps"
wget -q -O "minimized_coordinate.data" "${url}/level1/lennard-jones-fluid/improved-input/minimized_coordinate.data"
