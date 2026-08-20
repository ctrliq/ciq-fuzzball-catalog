# Copyright 2026 CIQ, Inc. All rights reserved.
---
id: "ciq/ml_and_ai/vllm_nvidia_nemotron_nano_12b_v2_vl_bf16"
name: "vLLM NVIDIA-Nemotron-Nano-12B-v2-VL-BF16"
category: "ML_AND_AI"
tags:
- LLM
- inference
- vllm
- autoscaling
- multimodal
- NVIDIA
---

Serves
[`nvidia/NVIDIA-Nemotron-Nano-12B-v2-VL-BF16`](https://recipes.vllm.ai/nvidia/NVIDIA-Nemotron-Nano-12B-v2-VL-BF16)
from an autoscaled pool of vLLM ([vLLM docs](https://docs.vllm.ai/en/stable))
replicas behind a single OpenAI-compatible base URL. Deployment parameters come
from the [vLLM recipe for NVIDIA
Nemotron-Nano-12B-v2-VL](https://recipes.vllm.ai/nvidia/NVIDIA-Nemotron-Nano-12B-v2-VL-BF16):
every vLLM flag, environment variable, container image, GPU count and parallel
layout below is what that recipe validated for the selected hardware.

NVIDIA Nemotron-Nano 12B vision-language model with video support and Efficient
Video Sampling (EVS)

## Model

- **Checkpoint**: `nvidia/NVIDIA-Nemotron-Nano-12B-v2-VL-BF16`
- **Architecture**: dense, 12B parameters
- **Active parameters**: 12B
- **Context length**: 131072 tokens
- **Minimum vLLM version**: 0.11.1
- **Recipe difficulty**: intermediate

## Supported hardware

| Hardware | Node | GPUs per replica | Recipe status |
| --- | --- | --- | --- |
| `b200` | 8x B200, 1440 GB | 1 | verified |
| `b300` | 8x B300, 2144 GB | 1 | untested upstream |
| `gb200` | 4x GB200 NVL4, 768 GB | 1 | untested upstream |
| `gb300` | 4x GB300 NVL4, 1152 GB | 1 | untested upstream |
| `h100` | 8x H100, 640 GB | 1 | verified |
| `h200` | 8x H200, 1128 GB | 1 | untested upstream |
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
| `default` | bf16 | 29 GB | `nvidia/NVIDIA-Nemotron-Nano-12B-v2-VL-BF16` |
| `fp8` | fp8 | 14 GB | `nvidia/NVIDIA-Nemotron-Nano-12B-v2-VL-FP8` |
| `nvfp4` | nvfp4 | 8 GB | `nvidia/NVIDIA-Nemotron-Nano-12B-v2-VL-NVFP4-QAD` |

## Features

-  **`EnableVideoCompression`** (default on): Efficient Video Sampling (EVS)
  prunes video tokens; 0.75 means 75% pruning
-  **`EnableTextOnly`** (default off): Skip loading the vision encoder for
  text-only workloads — frees VRAM for KV cache. Mutually exclusive with
  encoder_parallel.
-  **`EnableEncoderParallel`** (default off): Run the vision encoder in
  data-parallel mode — avoids TP comm overhead on the small encoder. Mutually
  exclusive with text_only.

## Usage

```sh
fuzzball workflow catalog start vllm_nvidia_nemotron_nano_12b_v2_vl_bf16
fuzzball workflow catalog start vllm_nvidia_nemotron_nano_12b_v2_vl_bf16 --values Hardware=mi355x,Variant=nvfp4
fuzzball workflow catalog start vllm_nvidia_nemotron_nano_12b_v2_vl_bf16 --values ModelVolume=volume://user/models,MaxReplicas=4
```

Clients address the model as `nvidia/NVIDIA-Nemotron-Nano-12B-v2-VL-BF16`
regardless of the variant served, because the service pins
`--served-model-name`. Gated checkpoints need `HuggingFaceHubToken`. Non-public
endpoints need a bearer token from `fuzzball workflow endpoints
generate-token`.

## Default configuration

`Hardware=h200`, `Strategy=single_node_tp`, `Variant=default` requests 1 GPU(s)
per replica and renders:

```sh
vllm serve nvidia/NVIDIA-Nemotron-Nano-12B-v2-VL-BF16 \
  --trust-remote-code \
  --tensor-parallel-size 1 \
  --video-pruning-rate 0.75 \
  --served-model-name nvidia/NVIDIA-Nemotron-Nano-12B-v2-VL-BF16
```

With environment:

```sh
VLLM_VIDEO_LOADER_BACKEND=opencv
```

Image: `docker://vllm/vllm-openai:v0.11.1`

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
  https://recipes.vllm.ai/nvidia/NVIDIA-Nemotron-Nano-12B-v2-VL-BF16.
  Regenerate this application with `scripts/gen_models.py` after the recipe
  changes.
