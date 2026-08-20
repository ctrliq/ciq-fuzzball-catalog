# Copyright 2026 CIQ, Inc. All rights reserved.
---
id: "ciq/ml_and_ai/vllm_mistral_small_4_119b_2603"
name: "vLLM Mistral-Small-4-119B-2603"
category: "ML_AND_AI"
tags:
- LLM
- inference
- vllm
- autoscaling
- multimodal
- Mistral AI
---

Serves
[`mistralai/Mistral-Small-4-119B-2603`](https://recipes.vllm.ai/mistralai/Mistral-Small-4-119B-2603)
from an autoscaled pool of vLLM ([vLLM docs](https://docs.vllm.ai/en/stable))
replicas behind a single OpenAI-compatible base URL. Deployment parameters come
from the [vLLM recipe for
Mistral-Small-4-119B](https://recipes.vllm.ai/mistralai/Mistral-Small-4-119B-2603):
every vLLM flag, environment variable, container image, GPU count and parallel
layout below is what that recipe validated for the selected hardware.

Mistral Small 4 (119B MoE, 6.5B active) — multimodal hybrid instruct +
reasoning model with native FP8 weights and 256K context

## Model

- **Checkpoint**: `mistralai/Mistral-Small-4-119B-2603`
- **Architecture**: moe, 119B parameters
- **Active parameters**: 6.5B
- **Context length**: 262144 tokens
- **Minimum vLLM version**: 0.20.0
- **Recipe difficulty**: intermediate

## Supported hardware

| Hardware | Node | GPUs per replica | Recipe status |
| --- | --- | --- | --- |
| `b200` | 8x B200, 1440 GB | 2 | untested upstream |
| `b300` | 8x B300, 2144 GB | 2 | untested upstream |
| `gb200` | 4x GB200 NVL4, 768 GB | 2 | untested upstream |
| `gb300` | 4x GB300 NVL4, 1152 GB | 2 | untested upstream |
| `h100` | 8x H100, 640 GB | 2 | untested upstream |
| `h200` | 8x H200, 1128 GB | 2 | untested upstream |
| `mi300x` | 8x MI300X, 1536 GB | 2 | untested upstream |
| `mi325x` | 8x MI325X, 2048 GB | 2 | untested upstream |
| `mi355x` | 8x MI355X, 2304 GB | 2 | untested upstream |

A replica requests exactly the GPUs its parallel size shards across, so one GPU
is requested where the weights fit one GPU. Hardware the recipe marks
`unsupported`, hardware that cannot hold the weights on one node, and profiles
with no Fuzzball device key (TPU, CPU, Intel XPU) are not offered.

## Variants

| Variant | Precision | Minimum VRAM | Checkpoint |
| --- | --- | --- | --- |
| `default` | fp8 | 143 GB | `mistralai/Mistral-Small-4-119B-2603` |
| `nvfp4` | nvfp4 | 72 GB | `mistralai/Mistral-Small-4-119B-2603-NVFP4` |

## Features

-  **`EnableToolCalling`** (default on): Mistral tool-call parser with
  automatic tool choice — emits [TOOL_CALLS] / [ARGS] from the chat template
-  **`EnableReasoning`** (default on): Mistral reasoning parser extracts
  [THINK]...[/THINK] into message.reasoning_content (emitted when
  reasoning_effort='high')
-  **`EnableSpecDecoding`** (default off): EAGLE speculative decoding via the
  mistralai/Mistral-Small-4-119B-2603-eagle 2-layer draft head

## Usage

```sh
fuzzball workflow catalog start vllm_mistral_small_4_119b_2603
fuzzball workflow catalog start vllm_mistral_small_4_119b_2603 --values Hardware=mi355x,Variant=nvfp4
fuzzball workflow catalog start vllm_mistral_small_4_119b_2603 --values ModelVolume=volume://user/models,MaxReplicas=4
```

Clients address the model as `mistralai/Mistral-Small-4-119B-2603` regardless
of the variant served, because the service pins `--served-model-name`. Gated
checkpoints need `HuggingFaceHubToken`. Non-public endpoints need a bearer
token from `fuzzball workflow endpoints generate-token`.

## Default configuration

`Hardware=h200`, `Strategy=single_node_tp`, `Variant=default` requests 2 GPU(s)
per replica and renders:

```sh
vllm serve mistralai/Mistral-Small-4-119B-2603 \
  --max-model-len 262144 \
  --tensor-parallel-size 2 \
  --enable-auto-tool-choice \
  --tool-call-parser mistral \
  --reasoning-parser mistral \
  --served-model-name mistralai/Mistral-Small-4-119B-2603
```

Image: `docker://vllm/vllm-openai:v0.20.0`

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
  -  `uv pip install -U "mistral_common>=1.11.0"`
  -  `uv pip install -U transformers`
-  Deployment parameters track the recipe at
  https://recipes.vllm.ai/mistralai/Mistral-Small-4-119B-2603. Regenerate this
  application with `scripts/gen_models.py` after the recipe changes.
