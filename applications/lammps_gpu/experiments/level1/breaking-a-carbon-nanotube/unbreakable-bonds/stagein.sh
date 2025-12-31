#! /bin/sh
# Used to set up example from https://github.com/lammpstutorials/lammpstutorials-inputs
# This job runs the md part of the second lennard jones liquid example
set -ex

run="${1}"
mkdir -p "${run}" && cd "${run}" || exit 1

commit="4e249a6f7a0f8f8057bf72c07d39841a297e69a6"
url="https://raw.githubusercontent.com/lammpstutorials/lammpstutorials-inputs/${commit}"

for f in input.lammps cnt_molecular.data parm.lammps ; do
    wget -q -O "$f" "${url}/level1/breaking-a-carbon-nanotube/unbreakable-bonds/${f}"
done

# need to make one mod for the older lammps
sed -i 's/^delete_atoms/#delete_atoms/;s/^reset_atoms/#reset_atoms/' input.lammps
