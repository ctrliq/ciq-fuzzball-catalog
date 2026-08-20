# Copyright 2026 CIQ, Inc. All rights reserved.
---
id: "ciq/ml_and_ai/vllm_nvidia_nemotron_3_5_lightning_30b_a3b_bf16"
name: "vLLM NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16"
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
[`nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16`](https://recipes.vllm.ai/nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16)
from an autoscaled pool of vLLM ([vLLM docs](https://docs.vllm.ai/en/stable))
replicas behind a single OpenAI-compatible base URL. Deployment parameters come
from the [vLLM recipe for NVIDIA Nemotron 3.5
Lightning](https://recipes.vllm.ai/nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16):
every vLLM flag, environment variable, container image, GPU count and parallel
layout below is what that recipe validated for the selected hardware.

NVIDIA Nemotron 3.5 Lightning hybrid Mamba-MoE (30B total / 3B active) with
NVFP4 and BF16 checkpoints, 1M context, and MTP / DSpark / DFlash speculative
decoding

## Model

- **Checkpoint**: `nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16`
- **Architecture**: moe, 30B parameters
- **Active parameters**: 3B
- **Context length**: 1048576 tokens
- **Minimum vLLM version**: 0.27.1
- **Recipe difficulty**: intermediate

## Supported hardware

| Hardware | Node | GPUs per replica | Recipe status |
| --- | --- | --- | --- |
| `b200` | 8x B200, 1440 GB | 1/8 | untested upstream |
| `b300` | 8x B300, 2144 GB | 1/8 | untested upstream |
| `dgx_spark_gb10` | 1x DGX Spark (GB10), 128 GB | 1 | verified |
| `dgx_station_gb300` | 1x DGX Station (GB300), 252 GB | 1 | verified |
| `gb200` | 4x GB200 NVL4, 768 GB | 1/4 | untested upstream |
| `gb300` | 4x GB300 NVL4, 1152 GB | 1/4 | untested upstream |
| `h100` | 8x H100, 640 GB | 1/8 | verified |
| `h200` | 8x H200, 1128 GB | 1/8 | untested upstream |
| `mi300x` | 8x MI300X, 1536 GB | 1/8 | untested upstream |
| `mi325x` | 8x MI325X, 2048 GB | 1/8 | untested upstream |
| `mi355x` | 8x MI355X, 2304 GB | 1/8 | untested upstream |

A replica requests exactly the GPUs its parallel size shards across, so one GPU
is requested where the weights fit one GPU. Hardware the recipe marks
`unsupported`, hardware that cannot hold the weights on one node, and profiles
with no Fuzzball device key (TPU, CPU, Intel XPU) are not offered.

## Variants

| Variant | Precision | Minimum VRAM | Checkpoint |
| --- | --- | --- | --- |
| `bf16` | bf16 | 72 GB | `nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16` |
| `default` | nvfp4 | 18 GB | `nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4` |

## Serving strategies

-  **`single_node_tep`** (Tensor + Expert Parallel): Single-node TEP. TP splits
  dense layers and EP splits expert layers across local GPUs. TP must be set to
  GPU count to avoid OOM from replicated dense layers. For MoE models only.
-  **`single_node_tp`** (Tensor Parallel): Single-node tensor parallel. Splits
  the model across all local GPUs. TP size is set to the GPU count at deploy
  time. The simplest multi-GPU strategy — works for all model architectures.

## Features

-  **`EnableReasoning`** (default on): Nemotron v3 reasoning parser —
  per-request reasoning toggle with a configurable token budget
-  **`EnableToolCalling`** (default on): Qwen3 XML tool-call parser with
  automatic tool choice
-  **`EnableMambaFastSsmCache`** (default on): FP16 Mamba SSM cache with
  stochastic rounding — faster decode than the FP32 default; the Philox rounds
  control the rounding stream
-  **`EnableSpecDecoding`** (default off): Speculative decoding — built-in MTP
  heads, the DSpark hybrid speculator, or the DFlash diffusion drafter

## Usage

```sh
fuzzball workflow catalog start vllm_nvidia_nemotron_3_5_lightning_30b_a3b_bf16
fuzzball workflow catalog start vllm_nvidia_nemotron_3_5_lightning_30b_a3b_bf16 --values Hardware=mi355x,Strategy=single_node_tp,Variant=default
fuzzball workflow catalog start vllm_nvidia_nemotron_3_5_lightning_30b_a3b_bf16 --values ModelVolume=volume://user/models,MaxReplicas=4
```

Clients address the model as
`nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16` regardless of the variant
served, because the service pins `--served-model-name`. Gated checkpoints need
`HuggingFaceHubToken`. Non-public endpoints need a bearer token from `fuzzball
workflow endpoints generate-token`.

## Default configuration

`Hardware=h200`, `Strategy=single_node_tp`, `Variant=default` requests 1 GPU(s)
per replica and renders:

```sh
vllm serve nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4 \
  --mamba-backend flashinfer \
  --mamba-cache-mode align \
  --enable-prefix-caching \
  --kv-cache-dtype fp8 \
  --tensor-parallel-size 1 \
  --quantization modelopt_fp4 \
  --moe-backend humming \
  --linear-backend humming \
  --mamba-ssu-algorithm horizontal \
  --async-scheduling \
  --max-num-seqs 256 \
  --max-num-batched-tokens 32768 \
  --reasoning-parser nemotron_v3 \
  --enable-auto-tool-choice \
  --tool-call-parser qwen3_xml \
  --mamba-ssm-cache-dtype float16 \
  --enable-mamba-cache-stochastic-rounding \
  --mamba-cache-philox-rounds 5 \
  --served-model-name nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16
```

Image: `docker://vllm/vllm-openai:v0.27.1`

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
  https://recipes.vllm.ai/nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16.
  Regenerate this application with `scripts/gen_models.py` after the recipe
  changes.
