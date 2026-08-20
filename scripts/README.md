# scripts

## gen_models.py

Generates one Fuzzball application per vLLM model from a checkout of
[vllm-project/recipes](https://github.com/vllm-project/recipes).

```sh
uv run scripts/gen_models.py --recipes-dir ~/repos/recipes
uv run scripts/gen_models.py --recipes-dir ~/repos/recipes --model openai/gpt-oss-120b
uv run scripts/gen_models.py --recipes-dir ~/repos/recipes --dry-run
```

Output is `applications/vllm_<hf_repo>/{template.yaml,values.yaml,metadata.md}`.
Writes are idempotent: unchanged files are left alone and reported as current.
The script declares its own dependency (PyYAML) inline, so `uv run` needs no
virtualenv.

### What the generated applications are

Each application serves one model from an autoscaled vLLM service pool behind an
optional in-workflow LiteLLM proxy — the pattern in `applications/vllm`, with the
model's deployment parameters baked in.

The user picks:

- **Hardware** — a GPU node profile from the recipe's taxonomy. Selects the GPU
  vendor, how many GPUs a replica requests, the container image and the recipe's
  per-generation tuning.
- **Strategy** — a single-node parallelism strategy the recipe lists
  (`single_node_tp` / `single_node_tep` / `single_node_dep`).
- **Variant** — a checkpoint variant (precision) the recipe defines.
- **Features** — the recipe's own feature toggles (tool calling, reasoning,
  speculative decoding, …), defaulting to the recipe's `opt_in_features`.
- Scaling, storage, access, resource and image-override knobs.

Everything else — vLLM flags, environment, parallel size, image — comes from the
recipe for the chosen crossing. A crossing the recipe never validated fails at
render time with a message naming the knobs involved.

`MaxModelLen` and `ExtraVllmArgs` are appended last, so they override the
recipe's own flags for expert tuning.

### Flag resolution

The layering mirrors the recipes site's `src/lib/command-synthesis.js`:
`model.base_args`, variant args, strategy args plus the parallel-size flag,
`strategy_overrides`, then hardware overrides — where a per-strategy generation
override *replaces* the recipe baseline and the variant delta, while recipe and
variant blocks layer additively. Duplicate flags resolve last-wins. Feature args
emit last, as the template's user toggles.

A differential test against that upstream module agreed on all flags and
environment for 11,874 generated configurations.

### Deliberate limitations

- **Single-node strategies only.** A Fuzzball service is one container on one
  node, so `multi_node_*` and `pd_cluster` are skipped. Those need a different
  workflow shape (rank-aware multinode jobs), not a service pool.
- **`--omni` recipes are skipped** (25 of them: diffusion, TTS, video). They
  serve through `vllm serve --omni` with per-task presets.
- A hardware profile is offered only if the weights fit one of its nodes, its
  brand has a Fuzzball device key (so no TPU / CPU / Intel XPU), and the recipe
  does not mark it `unsupported`.
- Features with a **companion process** are dropped: the helper would have to run
  beside `vllm serve` in the same container.
- Single-select feature **modes** (for example MTP vs DSpark speculation) use the
  recipe's default mode for the variant; the mode is not a user knob.
- Recipe `dependencies` are documented in `metadata.md` but not installed: they
  target the pip install path, and the container image already carries them.
- AMD image defaults follow `applications/vllm`, because ROCm publishes no
  per-release tag matching `min_vllm_version`. Override with `VllmImageROCm`.

### After regenerating

Re-run `fuzzball application render-template` on any application you changed, and
check `git status` for applications the recipes repo no longer produces — the
script never deletes anything.
