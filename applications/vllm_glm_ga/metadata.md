# Copyright 2026 CIQ, Inc. All rights reserved.
---
id: "ciq/ml_and_ai/vllm_glm_ga"
name: "vLLM GLM-GA"
category: "ML_AND_AI"
tags:
- LLM
- inference
- vllm
- autoscaling
- multimodal
- GLM (Z-AI)
---

Serves [`zai-org/GLM-GA`](https://recipes.vllm.ai/zai-org/GLM-GA) from an
autoscaled pool of vLLM ([vLLM docs](https://docs.vllm.ai/en/stable)) replicas
behind a single OpenAI-compatible base URL. Deployment parameters come from the
[vLLM recipe for GLM-GA](https://recipes.vllm.ai/zai-org/GLM-GA): every vLLM
flag, environment variable, container image, GPU count and parallel layout
below is what that recipe validated for the selected hardware.

GLM-GA dense vision-language model (~10B) — image and video understanding with
128K context and dedicated Glmga video processor (fps=2, up to 640 frames)

## Model

- **Checkpoint**: `zai-org/GLM-GA`
- **Architecture**: dense, 10B parameters
- **Context length**: 131072 tokens
- **Minimum vLLM version**: 0.21.0
- **Recipe difficulty**: beginner

## Supported hardware

| Hardware | Node | GPUs per replica | Recipe status |
| --- | --- | --- | --- |
| `b200` | 8x B200, 1440 GB | 1 | untested upstream |
| `b300` | 8x B300, 2144 GB | 1 | untested upstream |
| `gb200` | 4x GB200 NVL4, 768 GB | 1 | untested upstream |
| `gb300` | 4x GB300 NVL4, 1152 GB | 1 | untested upstream |
| `h100` | 8x H100, 640 GB | 1 | untested upstream |
| `h200` | 8x H200, 1128 GB | 1 | untested upstream |
| `mi300x` | 8x MI300X, 1536 GB | 1 | untested upstream |
| `mi325x` | 8x MI325X, 2048 GB | 1 | untested upstream |
| `mi355x` | 8x MI355X, 2304 GB | 1 | untested upstream |

A replica requests exactly the GPUs its parallel size shards across, so one GPU
is requested where the weights fit one GPU. Hardware the recipe marks
`unsupported`, hardware that cannot hold the weights on one node, and profiles
with no Fuzzball device key (TPU, CPU, Intel XPU) are not offered.

## Features

-  **`EnableTextOnly`** (default off): Skip loading the vision encoder for
  text-only workloads — frees VRAM for KV cache.

## Usage

```sh
fuzzball workflow catalog start vllm_glm_ga
fuzzball workflow catalog start vllm_glm_ga --values Hardware=mi355x
fuzzball workflow catalog start vllm_glm_ga --values ModelVolume=volume://user/models,MaxReplicas=4
```

Clients address the model as `zai-org/GLM-GA` regardless of the variant served,
because the service pins `--served-model-name`. Gated checkpoints need
`HuggingFaceHubToken`. Non-public endpoints need a bearer token from `fuzzball
workflow endpoints generate-token`.

## Default configuration

`Hardware=h200`, `Strategy=single_node_tp`, `Variant=default` requests 1 GPU(s)
per replica and renders:

```sh
vllm serve zai-org/GLM-GA \
  --trust-remote-code \
  --allowed-local-media-path / \
  --mm-processor-cache-type shm \
  --reasoning-parser glm45 \
  --tensor-parallel-size 1 \
  --served-model-name zai-org/GLM-GA
```

With environment:

```sh
VLLM_VIDEO_LOADER_BACKEND=glm4_6v
```

Image: `docker://vllm/vllm-openai:v0.21.0`

## Services

-  **vllm**: the replica pool. Every replica serves the same model on the same
  port and reports Prometheus metrics there. Replicas share one autoscaler DNS
  record that tracks only replicas past their readiness probe, so a client
  never sees a replica still loading weights.
-  **litellm**: the proxy, present when `EnableProxy` is true. It holds the
  endpoint, exposes `/v1` OpenAI-compatible routes, and is the workflow's
  cross-service scaling source. It declares no `depends-on`, because it must
  answer requests while the pool holds zero replicas.

## Notes and limitations

-  Only single-node serving strategies are offered. A Fuzzball service is one
  container on one node, so the recipe's multi-node strategies (`multi_node_*`,
  `pd_cluster`) are not generated.
-  Use a persistent `ModelVolume`. On the default ephemeral volume every
  replica added during scale-up re-downloads the weights, which dominates
  cold-start time.
-  `ReadinessFailureThreshold` is the weight download budget. Large checkpoints
  on a cold cache need it raised, not the initial delay.
-  The autoscaler has no drain setting. The `max(vllm:num_requests_running) ==
  bool 0` scale-down condition plus `ScaleDownCooldownSeconds` is the drain
  window; size it to cover the longest expected streaming generation.
-  The recipe lists extra install steps that apply to its pip install path; the
  container image used here already carries them:
  -  `uv pip install git+https://github.com/huggingface/transformers.git`
-  Deployment parameters track the recipe at
  https://recipes.vllm.ai/zai-org/GLM-GA. Regenerate this application with
  `scripts/gen_models.py` after the recipe changes.
