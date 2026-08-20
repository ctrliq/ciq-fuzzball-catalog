# Copyright 2026 CIQ, Inc. All rights reserved.
---
id: "ciq/ml_and_ai/vllm_nvidia_nemotron_3_super_120b_a12b_bf16"
name: "vLLM NVIDIA-Nemotron-3-Super-120B-A12B-BF16"
category: "ML_AND_AI"
tags:
- LLM
- inference
- vllm
- autoscaling
- text
- NVIDIA
---

Serves
[`nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-BF16`](https://recipes.vllm.ai/nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-BF16)
from an autoscaled pool of vLLM ([vLLM docs](https://docs.vllm.ai/en/stable))
replicas behind a single OpenAI-compatible base URL. Deployment parameters come
from the [vLLM recipe for NVIDIA
Nemotron-3-Super-120B-A12B](https://recipes.vllm.ai/nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-BF16):
every vLLM flag, environment variable, container image, GPU count and parallel
layout below is what that recipe validated for the selected hardware.

NVIDIA Nemotron-3-Super Mamba-hybrid latent-MoE (~120B total / ~12B active)
with BF16, FP8, and NVFP4 variants

## Model

- **Checkpoint**: `nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-BF16`
- **Architecture**: moe, 120B parameters
- **Active parameters**: 12B
- **Context length**: 262144 tokens
- **Minimum vLLM version**: 0.17.1
- **Recipe difficulty**: advanced

## Supported hardware

| Hardware | Node | GPUs per replica | Recipe status |
| --- | --- | --- | --- |
| `b200` | 8x B200, 1440 GB | 1/8 | verified |
| `b300` | 8x B300, 2144 GB | 1/8 | untested upstream |
| `dgx_spark_gb10` | 1x DGX Spark (GB10), 128 GB | 1 | verified |
| `dgx_station_gb300` | 1x DGX Station (GB300), 252 GB | 1 | verified |
| `gb200` | 4x GB200 NVL4, 768 GB | 1/4 | untested upstream |
| `gb300` | 4x GB300 NVL4, 1152 GB | 1/4 | untested upstream |
| `h100` | 8x H100, 640 GB | 8 | verified |
| `h200` | 8x H200, 1128 GB | 8 | verified |
| `mi300x` | 8x MI300X, 1536 GB | 1/8 | untested upstream |
| `mi325x` | 8x MI325X, 2048 GB | 1/8 | untested upstream |
| `mi355x` | 8x MI355X, 2304 GB | 1/8 | untested upstream |
| `rtx_pro_6000` | 1x RTX Pro 6000, 96 GB | 1 | verified |

A replica requests exactly the GPUs its parallel size shards across, so one GPU
is requested where the weights fit one GPU. Hardware the recipe marks
`unsupported`, hardware that cannot hold the weights on one node, and profiles
with no Fuzzball device key (TPU, CPU, Intel XPU) are not offered.

## Variants

| Variant | Precision | Minimum VRAM | Checkpoint |
| --- | --- | --- | --- |
| `base_bf16` | bf16 | 298 GB | `nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-Base-BF16` |
| `default` | bf16 | 298 GB | `nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-BF16` |
| `fp8` | fp8 | 149 GB | `nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-FP8` |
| `nvfp4` | nvfp4 | 75 GB | `nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-NVFP4` |

## Features

-  **`EnableToolCalling`** (default on): Qwen3 XML tool-call parser with
  automatic tool choice
-  **`EnableReasoning`** (default on): Built-in nemotron_v3 reasoning parser
  (vLLM >= 0.17.1)
-  **`EnableSpecDecoding`** (default off): MTP speculative decoding for
  accelerated inference

## Usage

```sh
fuzzball workflow catalog start vllm_nvidia_nemotron_3_super_120b_a12b_bf16
fuzzball workflow catalog start vllm_nvidia_nemotron_3_super_120b_a12b_bf16 --values Hardware=rtx_pro_6000,Variant=nvfp4
fuzzball workflow catalog start vllm_nvidia_nemotron_3_super_120b_a12b_bf16 --values ModelVolume=volume://user/models,MaxReplicas=4
```

Clients address the model as `nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-BF16`
regardless of the variant served, because the service pins
`--served-model-name`. Gated checkpoints need `HuggingFaceHubToken`. Non-public
endpoints need a bearer token from `fuzzball workflow endpoints
generate-token`.

## Default configuration

`Hardware=h200`, `Strategy=single_node_tp`, `Variant=default` requests 8 GPU(s)
per replica and renders:

```sh
vllm serve nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-BF16 \
  --trust-remote-code \
  --kv-cache-dtype fp8 \
  --tensor-parallel-size 8 \
  --enable-auto-tool-choice \
  --tool-call-parser qwen3_xml \
  --reasoning-parser nemotron_v3 \
  --served-model-name nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-BF16
```

Image: `docker://vllm/vllm-openai:v0.17.1`

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
  https://recipes.vllm.ai/nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-BF16.
  Regenerate this application with `scripts/gen_models.py` after the recipe
  changes.
