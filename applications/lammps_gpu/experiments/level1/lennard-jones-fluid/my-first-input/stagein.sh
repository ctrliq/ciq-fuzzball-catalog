#!/bin/sh
# used to set up example from https://github.com/lammpstutorials/lammpstutorials-inputs
set -e

run_dir="${1}"
mkdir -p "${run_dir}" && cd "${run_dir}"

commit="dd3dce70b883af02df293ce52491beabd8e01928"
url="https://raw.githubusercontent.com/lammpstutorials/lammpstutorials-inputs/${commit}"
wget -q -O input.lammps "${url}/level1/lennard-jones-fluid/my-first-input/input.lammps"
