# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This repository defines applications for use with Fuzzball (see the [Fuzzball
documentation](https://ui.stable.fuzzball.ciq.dev/docs/)). Applications are
defined in the `applications` directory. Each application is housed in a subdirectory
of `applications`. The required files for each application are as follows:

- `metadata.md`: Contains structured information in the front matter and are
  otherwise a free form description of the application.
- `template.yaml`: Fuzzball workflow files as described in
  https://ui.stable.fuzzball.ciq.dev/docs/appendices/workflow-syntax/ and contain
  golang template strings augmented with functions from the
  [slim-sprig](https://github.com/go-task/slim-sprig) library.
- `values.yaml`: Describe values used to template the `template.yaml` files.

These files must be located at the top level of the directory. Other (arbitrary,
optional) files may be included as well.

Running the following command with a `template.yaml` and a `values.yaml` file
should yield a valid workflow template.

```sh
fuzzball application render-template <INPUT_FILE> <VALUES_FILE>


## Style guide
- Application templates should follow a style consistent with the existing
  templates listed below and the [style guide](StyleGuide.md).
  - bwa_alignment
  - specfrm3d
  - blast
  - gromacs_gpu
  - openfoam_motorbike


## Branches
See the [README.md](README.md) file for details on how branches are structured.
