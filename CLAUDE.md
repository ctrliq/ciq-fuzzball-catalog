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

Instead of carrying its own `template.yaml`, an application may set
`template: <application>` in its metadata.md front matter to use another
application's template (e.g. the per-model vLLM presets reference `vllm`). An
application must have exactly one of the two, and the referenced application
must carry a real `template.yaml` (no chained references). Loading
template-referencing entries requires an orchestrator with the reference
resolver (fuzzball commit d23fad62c4); on older orchestrators such entries
abort the catalog sync, so see README.md's Contributing rules before porting
one to a release branch.

These files must be located at the top level of the directory. Other (arbitrary,
optional) files may be included as well.

## Validating a change

Rendering a `template.yaml` against its `values.yaml` should yield a valid
workflow definition:

```sh
fuzzball workflow catalog render --from-file template.yaml --values values.yaml > rendered.yaml
```

For a template-referencing entry (no local `template.yaml`), render the
referenced application's template against the entry's values instead:
`render --from-file ../vllm/template.yaml --values values.yaml`.

`--values` (`-v`) is **required** when `--from-file` is set. Without
`--from-file`, the positional argument is a catalog entry name or UUID and the
command renders an entry already stored on the cluster — not a local file.

**Rendering is not local.** Despite operating on local files, this command dials
the cluster and templates server-side, so it needs a reachable cluster and an
unexpired login. `fuzzball context show` confirms both. There is no offline
render path; a bare template syntax error and a lost auth token surface through
the same command.

Rendering only proves the template produced parseable output. Validate and score
the result as well:

```sh
fuzzball workflow validate rendered.yaml   # syntax and schema
fuzzball workflow score rendered.yaml      # schedulability and cost estimate
```

Worth checking by hand, since none of the three commands catch these:

- Every `.Foo` reference in `template.yaml` has a matching `name:` entry in
  `values.yaml`, and no declared value is left orphaned. Removing a parameter
  makes this easy to get wrong in both directions.
- Any `fail` guards in the template still fire, by rendering once with a
  deliberately bad value.
- `score` reflects a *federate* placement decision. The static node roster
  (`fuzzball node list`) can show no GPUs while a GPU workflow still scores as
  schedulable, because the federate provisions nodes on demand. Do not conclude
  from static node capacity that an application cannot be tested.

### Testing end to end

To test the rendered workflow directly:

```sh
fuzzball workflow start rendered.yaml --name <test-name> --watch
```

To test the packaging as the catalog actually serves it — which is the only path
that exercises `metadata.md` front matter and catalog ingestion — register a
branch as a source, reload it, then start the entry by name:

```sh
fuzzball workflow catalog source add <source-name> <repo-uri> <branch>
fuzzball workflow catalog source reload <source-name>
fuzzball workflow catalog start <template>
```

### Deprecated command paths

The catalog surface used to live under `fuzzball workflow-template`, and the
render command took two positionals (`render-template INPUT VALUES`). Both still
work as hidden, deprecated aliases that print a warning, so older scripts and
docs may show them. Write new instructions against `fuzzball workflow catalog`.

## Style guide

- Value names in `values.yaml` are **PascalCase** (`MinReplicas`,
  `HfTokenSecret`), referenced in `template.yaml` as direct fields
  (`.MinReplicas`, never `index . "min-replicas"`). Keep `metadata.md`
  usage examples (`--values Name=...`) in the same casing.
- Application templates should follow a style consistent with the existing
  templates listed below and the [style guide](StyleGuide.md).
  - bwa_alignment
  - specfem3d
  - blast
  - gromacs_gpu
  - openfoam_motorbike

## Branches

See the [README.md](README.md) file for details on how branches are structured.
