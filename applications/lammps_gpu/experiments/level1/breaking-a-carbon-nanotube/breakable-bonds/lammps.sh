#!/bin/sh

run="${1}"

# GPU capability - this assumes that we are using the nvcr container
gpu_cap=$(nvidia-smi --query-gpu=compute_cap --format=csv,noheader | tr -d '.')
lammps_caps=( $(ls /usr/local/lammps | sed 's/^sm//') )
use_cap=""
for c in ${lammps_caps[@]} ; do
if [[ $c -gt $gpu_cap ]]; then
    break
fi
use_cap=${c}
done
printf "GPU capability:    sm%s\n" "${gpu_cap}"
printf "LAMMPS capability: sm%s\n" "${use_cap}"
prefix="/usr/local/lammps/sm${use_cap}"
PATH="${prefix}/bin"
LD_LIBRARY_PATH="${prefix}/lib:${LD_LIBRARY_PATH}"
LAMMPS_POTENTIALS=${prefix}/share/lammps/potentials"
MSI2LMP_LIBRARY=${prefix}/share/lammps/frc_files"

export PATH LD_LIBRARY_PATH LAMMPS_POTENTIALS MSI2LMP_LIBRARY

cd "${run}" || exit 100
[[ -e "${prefix}/bin/lmp" ]] || exit 101
lmp -k on g 1 -sf kk -pk kokkos cuda/aware \
    on neigh full comm device binsize 2.8 -var x 8 -var y 4 -var z 8 \
    -in input.lammps
