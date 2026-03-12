# Copyright 2025 CIQ, Inc. All rights reserved.
---
id: "lammps_gpu_application"
name: "LAMMPS (GPU)"
category: "MOLECULAR_DYNAMICS"
featured: true
tags:
- MD
- Sandia
- GPU
keyart: keyart.jpg
---
The LAMMPS GPU application provides a Fuzzball workflow to execute
[LAMMPS](https://www.lammps.org/) molecular dynamics simulations on one or more
nodes with GPU acceleration using Kokkos.

## Workflow structure

The workflow is driven by two user-provided shell scripts fetched from a URL
at runtime:

| Script      | Required | Purpose                                                   |
|-------------|----------|-----------------------------------------------------------|
| **stagein** | yes      | Downloads/generates input files into a run directory      |
| **lammps**  | yes      | Configures the LAMMPS environment and runs the simulation |

Scripts can be hosted via HTTPS or S3 (set `ExperimentUrl` accordingly).
A set of ready-made example scripts are included in the `experiments/`
subdirectory covering Lennard-Jones fluid and carbon nanotube simulations from
the [LAMMPS tutorials](https://github.com/lammpstutorials/lammpstutorials-inputs).

## Result storage

Results can be saved to S3, a persistent Fuzzball volume, or both:

- **S3**: Set `S3Bucket` and `S3Secret`. A tar archive is uploaded via Fuzzball
  volume egress to `s3://<S3Bucket>/<OutputPath>/<RunName>-<timestamp>.tar.gz`.
- **Persistent volume**: Set `DataVolume`. The tar archive is copied to
  `<OutputPath>/<RunName>-<timestamp>.tar.gz` on the volume.

The workflow ID is embedded in the archive as `FB_WORKFLOW_ID` for traceability.

## Container

The default container is the [NVIDIA NGC LAMMPS
image](https://catalog.ngc.nvidia.com/orgs/nvidia/containers/lammps)
which ships LAMMPS built with Kokkos for multiple GPU compute capabilities
under `/usr/local/lammps/sm<cap>`. The `lammps.sh` scripts auto-detect the
GPU capability at runtime and select the matching build.

## Resources

- **GPUs**: NVIDIA (default) or AMD. The GPU vendor, model, and count are
  configurable.
- **MPI**: Multi-node runs are supported via OpenMPI (default) or MPICH.
- **Timeout**: The LAMMPS job has a configurable runtime limit (default 30m).
