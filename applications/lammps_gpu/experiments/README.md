

Scripts to set up example LAMMPS runs from example from
(https://github.com/lammpstutorials/lammpstutorials-inputs) in a standard format. Each experiment
directory contains a `stagein` script that creates the input files, a `lammps` script to run
LAMMPS on the inputs, and a (optional) `stageout` script to save the results to a persistent location.

Available examples:

- Level1
  - [Lennard Jones fluid - first example](level1/lennard-jones-fluid/my-first-input)
  - [Lennard Jones fluid - improved input](level1/lennard-jones-fluid/improved-input)
  - [Breaking a carbon nanotube - unbreakable bonds](level1/breaking-a-carbon-nanotube/unbreakable-bonds)
  - [Breaking a carbon nanotube - breakable bonds](level1/breaking-a-carbon-nanotube/breakable-bonds)
