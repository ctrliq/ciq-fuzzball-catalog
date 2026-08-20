# Copyright 2026 CIQ, Inc. All rights reserved.
---
id: "ciq/ml_and_ai/vllm_nemotron_3_nano_omni_30b_a3b_reasoning_bf16"
name: "vLLM Nemotron-3-Nano-Omni-30B-A3B-Reasoning-BF16"
category: "ML_AND_AI"
tags:
- LLM
- inference
- vllm
- autoscaling
- multimodal
- text
- NVIDIA
---

Serves
[`nvidia/Nemotron-3-Nano-Omni-30B-A3B-Reasoning-BF16`](https://recipes.vllm.ai/nvidia/Nemotron-3-Nano-Omni-30B-A3B-Reasoning-BF16)
from an autoscaled pool of vLLM ([vLLM docs](https://docs.vllm.ai/en/stable))
replicas behind a single OpenAI-compatible base URL. Deployment parameters come
from the [vLLM recipe for
Nemotron-3-Nano-Omni-30B-A3B-Reasoning](https://recipes.vllm.ai/nvidia/Nemotron-3-Nano-Omni-30B-A3B-Reasoning-BF16):
every vLLM flag, environment variable, container image, GPU count and parallel
layout below is what that recipe validated for the selected hardware.

Mamba2-Transformer hybrid MoE omnimodal model (31B total / 3B active) with
unified video, audio, image, and text understanding; reasoning + tool calling;
BF16, FP8, and NVFP4 variants

## Model

- **Checkpoint**: `nvidia/Nemotron-3-Nano-Omni-30B-A3B-Reasoning-BF16`
- **Architecture**: moe, 31B parameters
- **Active parameters**: 3B
- **Context length**: 262144 tokens
- **Minimum vLLM version**: 0.20.0
- **Recipe difficulty**: advanced

## Supported hardware

| Hardware | Node | GPUs per replica | Recipe status |
| --- | --- | --- | --- |
| `b200` | 8x B200, 1440 GB | 1 | verified |
| `b300` | 8x B300, 2144 GB | 1 | untested upstream |
| `gb200` | 4x GB200 NVL4, 768 GB | 1 | untested upstream |
| `gb300` | 4x GB300 NVL4, 1152 GB | 1 | untested upstream |
| `h100` | 8x H100, 640 GB | 1 | verified |
| `h200` | 8x H200, 1128 GB | 1 | verified |
| `mi300x` | 8x MI300X, 1536 GB | 1 | untested upstream |
| `mi325x` | 8x MI325X, 2048 GB | 1 | untested upstream |
| `mi355x` | 8x MI355X, 2304 GB | 1 | untested upstream |

A replica requests exactly the GPUs its parallel size shards across, so one GPU
is requested where the weights fit one GPU. Hardware the recipe marks
`unsupported`, hardware that cannot hold the weights on one node, and profiles
with no Fuzzball device key (TPU, CPU, Intel XPU) are not offered.

## Variants

| Variant | Precision | Minimum VRAM | Checkpoint |
| --- | --- | --- | --- |
| `default` | bf16 | 75 GB | `nvidia/Nemotron-3-Nano-Omni-30B-A3B-Reasoning-BF16` |
| `fp8` | fp8 | 38 GB | `nvidia/Nemotron-3-Nano-Omni-30B-A3B-Reasoning-FP8` |
| `nvfp4` | nvfp4 | 28 GB | `nvidia/Nemotron-3-Nano-Omni-30B-A3B-Reasoning-NVFP4` |

## Features

-  **`EnableToolCalling`** (default on): Qwen3 Coder tool-call parser with
  automatic tool choice
-  **`EnableReasoning`** (default on): Nemotron v3 reasoning parser
  (chain-of-thought with <think> tags)

## Usage

```sh
fuzzball workflow catalog start vllm_nemotron_3_nano_omni_30b_a3b_reasoning_bf16
fuzzball workflow catalog start vllm_nemotron_3_nano_omni_30b_a3b_reasoning_bf16 --values Hardware=mi355x,Variant=nvfp4
fuzzball workflow catalog start vllm_nemotron_3_nano_omni_30b_a3b_reasoning_bf16 --values ModelVolume=volume://user/models,MaxReplicas=4
```

Clients address the model as
`nvidia/Nemotron-3-Nano-Omni-30B-A3B-Reasoning-BF16` regardless of the variant
served, because the service pins `--served-model-name`. Gated checkpoints need
`HuggingFaceHubToken`. Non-public endpoints need a bearer token from `fuzzball
workflow endpoints generate-token`.

## Default configuration

`Hardware=h200`, `Strategy=single_node_tp`, `Variant=default` requests 1 GPU(s)
per replica and renders:

```sh
vllm serve nvidia/Nemotron-3-Nano-Omni-30B-A3B-Reasoning-BF16 \
  --trust-remote-code \
  --max-model-len 131072 \
  --media-io-kwargs '{"video": {"num_frames": 512, "fps": 1}}' \
  --video-pruning-rate 0.5 \
  --tensor-parallel-size 1 \
  --enable-auto-tool-choice \
  --tool-call-parser qwen3_coder \
  --reasoning-parser nemotron_v3 \
  --served-model-name nvidia/Nemotron-3-Nano-Omni-30B-A3B-Reasoning-BF16
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
-  Deployment parameters track the recipe at
  https://recipes.vllm.ai/nvidia/Nemotron-3-Nano-Omni-30B-A3B-Reasoning-BF16.
  Regenerate this application with `scripts/gen_models.py` after the recipe
  changes.
