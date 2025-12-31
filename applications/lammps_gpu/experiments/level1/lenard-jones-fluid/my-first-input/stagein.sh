#! /bin/sh
# used to set up example from https://github.com/lammpstutorials/lammpstutorials-inputs
set -ex

run="${1}"
mkdir -p "${run}" && cd "${run}"

commit="4e249a6f7a0f8f8057bf72c07d39841a297e69a6"
url="https://raw.githubusercontent.com/lammpstutorials/lammpstutorials-inputs/${commit}"
wget -q -O input.lammps "${url}/level1/lennard-jones-fluid/my-first-input/input.lammps"
