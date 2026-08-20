# Copyright 2026 CIQ, Inc. All rights reserved.
---
id: "ciq/ml_and_ai/vllm_macaron_v1_coding_venti"
name: "vLLM Macaron-V1-Coding-Venti"
category: "ML_AND_AI"
tags:
- LLM
- inference
- vllm
- autoscaling
- text
- MindLab Research
---

Serves
[`mindlab-research/Macaron-V1-Coding-Venti`](https://recipes.vllm.ai/mindlab-research/Macaron-V1-Coding-Venti)
from an autoscaled pool of vLLM ([vLLM docs](https://docs.vllm.ai/en/stable))
replicas behind a single OpenAI-compatible base URL. Deployment parameters come
from the [vLLM recipe for
Macaron-V1-Coding-Venti](https://recipes.vllm.ai/mindlab-research/Macaron-V1-Coding-Venti):
every vLLM flag, environment variable, container image, GPU count and parallel
layout below is what that recipe validated for the selected hardware.

Macaron-V1-Coding-Venti — MindLab's coding-specialist checkpoint: the
Macaron-V1-Venti L2 Coding LoRA merged into the GLM-5.2 BF16 base. Same MoE
architecture and launch as GLM-5.2 (~743B total, 39B active), no runtime
adapter.

## Model

- **Checkpoint**: `mindlab-research/Macaron-V1-Coding-Venti`
- **Architecture**: moe, 743B parameters
- **Active parameters**: 39B
- **Context length**: 1048576 tokens
- **Minimum vLLM version**: 0.25.0
- **Recipe difficulty**: advanced

## Supported hardware

| Hardware | Node | GPUs per replica | Recipe status |
| --- | --- | --- | --- |
| `b200` | 8x B200, 1440 GB | 8 | untested upstream |
| `b300` | 8x B300, 2144 GB | 8 | verified |
| `gb300` | 4x GB300 NVL4, 1152 GB | 4 | untested upstream |
| `h200` | 8x H200, 1128 GB | 8 | untested upstream |
| `mi300x` | 8x MI300X, 1536 GB | 8 | untested upstream |
| `mi325x` | 8x MI325X, 2048 GB | 8 | untested upstream |
| `mi355x` | 8x MI355X, 2304 GB | 8 | untested upstream |

A replica requests exactly the GPUs its parallel size shards across, so one GPU
is requested where the weights fit one GPU. Hardware the recipe marks
`unsupported`, hardware that cannot hold the weights on one node, and profiles
with no Fuzzball device key (TPU, CPU, Intel XPU) are not offered.

## Variants

| Variant | Precision | Minimum VRAM | Checkpoint |
| --- | --- | --- | --- |
| `default` | bf16 | 1786 GB | `mindlab-research/Macaron-V1-Coding-Venti` |
| `fp8` | fp8 | 893 GB | `mindlab-research/Macaron-V1-Coding-Venti` |

## Serving strategies

-  **`single_node_tep`** (Tensor + Expert Parallel): Single-node TEP. TP splits
  dense layers and EP splits expert layers across local GPUs. TP must be set to
  GPU count to avoid OOM from replicated dense layers. For MoE models only.
-  **`single_node_tp`** (Tensor Parallel): Single-node tensor parallel. Splits
  the model across all local GPUs. TP size is set to the GPU count at deploy
  time. The simplest multi-GPU strategy — works for all model architectures.

## Features

-  **`EnableToolCalling`** (default on): GLM-4.7 tool call parser with
  automatic tool choice
-  **`EnableReasoning`** (default on): GLM-4.5 reasoning parser — thinking mode
  enabled by default on requests
-  **`EnableSpecDecoding`** (default off): Multi-Token Prediction speculative
  decoding (up to 5 draft tokens)

## Usage

```sh
fuzzball workflow catalog start vllm_macaron_v1_coding_venti
fuzzball workflow catalog start vllm_macaron_v1_coding_venti --values Hardware=mi355x,Strategy=single_node_tp,Variant=fp8
fuzzball workflow catalog start vllm_macaron_v1_coding_venti --values ModelVolume=volume://user/models,MaxReplicas=4
```

Clients address the model as `mindlab-research/Macaron-V1-Coding-Venti`
regardless of the variant served, because the service pins
`--served-model-name`. Gated checkpoints need `HuggingFaceHubToken`. Non-public
endpoints need a bearer token from `fuzzball workflow endpoints
generate-token`.

## Default configuration

`Hardware=h200`, `Strategy=single_node_tp`, `Variant=fp8` requests 8 GPU(s) per
replica and renders:

```sh
vllm serve mindlab-research/Macaron-V1-Coding-Venti \
  --quantization fp8 \
  --tensor-parallel-size 8 \
  --kv-cache-dtype fp8 \
  --tool-call-parser glm47 \
  --enable-auto-tool-choice \
  --reasoning-parser glm45 \
  --served-model-name mindlab-research/Macaron-V1-Coding-Venti
```

Image: `docker://vllm/vllm-openai:v0.25.0`

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
-  Deployment parameters track the recipe at
  https://recipes.vllm.ai/mindlab-research/Macaron-V1-Coding-Venti. Regenerate
  this application with `scripts/gen_models.py` after the recipe changes.
