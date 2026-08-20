# Copyright 2026 CIQ, Inc. All rights reserved.
---
id: "ciq/ml_and_ai/vllm_nvidia_nemotron_3_ultra_550b_a55b_bf16"
name: "vLLM NVIDIA-Nemotron-3-Ultra-550B-A55B-BF16"
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
[`nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B-BF16`](https://recipes.vllm.ai/nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B-BF16)
from an autoscaled pool of vLLM ([vLLM docs](https://docs.vllm.ai/en/stable))
replicas behind a single OpenAI-compatible base URL. Deployment parameters come
from the [vLLM recipe for NVIDIA
Nemotron-3-Ultra-550B-A55B](https://recipes.vllm.ai/nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B-BF16):
every vLLM flag, environment variable, container image, GPU count and parallel
layout below is what that recipe validated for the selected hardware.

NVIDIA Nemotron 3 Ultra hybrid Transformer-Mamba MoE model for long-context
agentic reasoning, coding, and tool use.

## Model

- **Checkpoint**: `nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B-BF16`
- **Architecture**: moe, 550B parameters
- **Active parameters**: 55B
- **Context length**: 262144 tokens
- **Minimum vLLM version**: 0.22.0
- **Recipe difficulty**: advanced

## Supported hardware

| Hardware | Node | GPUs per replica | Recipe status |
| --- | --- | --- | --- |
| `b200` | 8x B200, 1440 GB | 8 | verified |
| `b300` | 8x B300, 2144 GB | 8 | untested upstream |
| `gb200` | 4x GB200 NVL4, 768 GB | 4 | untested upstream |
| `gb300` | 4x GB300 NVL4, 1152 GB | 4 | untested upstream |
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
| `default` | bf16 | 1320 GB | `nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B-BF16` |
| `fp4` | nvfp4 | 330 GB | `nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B-NVFP4` |

## Features

-  **`EnableToolCalling`** (default on): Qwen3 Coder tool-call parser with
  automatic tool choice
-  **`EnableReasoning`** (default on): Nemotron v3 reasoning parser
-  **`EnableSpecDecoding`** (default on): Multi-Token Prediction with 5
  speculative tokens

## Usage

```sh
fuzzball workflow catalog start vllm_nvidia_nemotron_3_ultra_550b_a55b_bf16
fuzzball workflow catalog start vllm_nvidia_nemotron_3_ultra_550b_a55b_bf16 --values Hardware=mi355x,Variant=fp4
fuzzball workflow catalog start vllm_nvidia_nemotron_3_ultra_550b_a55b_bf16 --values ModelVolume=volume://user/models,MaxReplicas=4
```

Clients address the model as `nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B-BF16`
regardless of the variant served, because the service pins
`--served-model-name`. Gated checkpoints need `HuggingFaceHubToken`. Non-public
endpoints need a bearer token from `fuzzball workflow endpoints
generate-token`.

## Default configuration

`Hardware=b200`, `Strategy=single_node_tp`, `Variant=default` requests 8 GPU(s)
per replica and renders:

```sh
vllm serve nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B-BF16 \
  --served-model-name nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B \
  --trust-remote-code \
  --kv-cache-dtype fp8 \
  --max-num-seqs 16 \
  --max-model-len 262144 \
  --gpu-memory-utilization 0.90 \
  --max-num-batched-tokens 32768 \
  --enable-flashinfer-autotune \
  --async-scheduling \
  --mamba-backend triton \
  --mamba-ssm-cache-dtype float32 \
  --tensor-parallel-size 8 \
  --enable-auto-tool-choice \
  --tool-call-parser qwen3_coder \
  --reasoning-parser nemotron_v3 \
  --speculative-config '{"method":"mtp","num_speculative_tokens":5}' \
  --served-model-name nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B-BF16
```

With environment:

```sh
VLLM_MEMORY_PROFILER_ESTIMATE_CUDAGRAPHS=1
```

Image: `docker://vllm/vllm-openai:v0.22.0`

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
  https://recipes.vllm.ai/nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B-BF16.
  Regenerate this application with `scripts/gen_models.py` after the recipe
  changes.
