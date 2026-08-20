# Copyright 2026 CIQ, Inc. All rights reserved.
---
id: "ciq/ml_and_ai/vllm_deepseek_v4_flash"
name: "vLLM DeepSeek-V4-Flash"
category: "ML_AND_AI"
tags:
- LLM
- inference
- vllm
- autoscaling
- text
- DeepSeek
---

Serves
[`deepseek-ai/DeepSeek-V4-Flash`](https://recipes.vllm.ai/deepseek-ai/DeepSeek-V4-Flash)
from an autoscaled pool of vLLM ([vLLM docs](https://docs.vllm.ai/en/stable))
replicas behind a single OpenAI-compatible base URL. Deployment parameters come
from the [vLLM recipe for
DeepSeek-V4-Flash](https://recipes.vllm.ai/deepseek-ai/DeepSeek-V4-Flash):
every vLLM flag, environment variable, container image, GPU count and parallel
layout below is what that recipe validated for the selected hardware.

DeepSeek V4 MoE model with hybrid CSA+HCA attention, manifold-constrained
hyper-connections, and three-tier reasoning (Non-think / Think High / Think
Max).

## Model

- **Checkpoint**: `deepseek-ai/DeepSeek-V4-Flash`
- **Architecture**: moe, 284B parameters
- **Active parameters**: 13B
- **Context length**: 1048576 tokens
- **Minimum vLLM version**: 0.20.0
- **Recipe difficulty**: hard

## Supported hardware

| Hardware | Node | GPUs per replica | Recipe status |
| --- | --- | --- | --- |
| `b200` | 8x B200, 1440 GB | 8 | verified |
| `b300` | 8x B300, 2144 GB | 8 | verified |
| `dgx_station_gb300` | 1x DGX Station (GB300), 252 GB | 1 | verified |
| `gb200` | 4x GB200 NVL4, 768 GB | 4 | verified |
| `gb300` | 4x GB300 NVL4, 1152 GB | 4 | verified |
| `h100` | 8x H100, 640 GB | 8 | untested upstream |
| `h200` | 8x H200, 1128 GB | 8 | verified |
| `mi325x` | 8x MI325X, 2048 GB | 8 | verified |
| `mi355x` | 8x MI355X, 2304 GB | 8 | verified |
| `rtx_pro_6000_8x` | 8x RTX Pro 6000 8x, 768 GB | 8 | verified |

A replica requests exactly the GPUs its parallel size shards across, so one GPU
is requested where the weights fit one GPU. Hardware the recipe marks
`unsupported`, hardware that cannot hold the weights on one node, and profiles
with no Fuzzball device key (TPU, CPU, Intel XPU) are not offered.

## Variants

| Variant | Precision | Minimum VRAM | Checkpoint |
| --- | --- | --- | --- |
| `default` | fp8 | 200 GB | `deepseek-ai/DeepSeek-V4-Flash-0731` |
| `dspark` | fp8 | 200 GB | `deepseek-ai/DeepSeek-V4-Flash-DSpark` |
| `fp8` | fp8 | 170 GB | `deepseek-ai/DeepSeek-V4-Flash` |
| `nvfp4` | nvfp4 | 170 GB | `nvidia/DeepSeek-V4-Flash-NVFP4` |

## Serving strategies

-  **`single_node_dep`** (Data + Expert Parallel): Single-node DEP. Expert
  layers are shared across all GPUs via EP, dense layers run independently in
  DP groups. Best throughput for MoE models on 8-GPU single nodes. For MoE
  models only.
-  **`single_node_tep`** (Tensor + Expert Parallel): Single-node TEP. TP splits
  dense layers and EP splits expert layers across local GPUs. TP must be set to
  GPU count to avoid OOM from replicated dense layers. For MoE models only.
-  **`single_node_tp`** (Tensor Parallel): Single-node tensor parallel. Splits
  the model across all local GPUs. TP size is set to the GPU count at deploy
  time. The simplest multi-GPU strategy — works for all model architectures.

## Features

-  **`EnableToolCalling`** (default on): Enable tool calling with DeepSeek V4
  chat template support.
-  **`EnableReasoning`** (default on): Enable reasoning/thinking mode with the
  DeepSeek V4 reasoning parser.
-  **`EnableSpecDecoding`** (default off): Speculative decoding — pick a
  drafting method.

## Usage

```sh
fuzzball workflow catalog start vllm_deepseek_v4_flash
fuzzball workflow catalog start vllm_deepseek_v4_flash --values Hardware=rtx_pro_6000_8x,Strategy=single_node_tp,Variant=nvfp4
fuzzball workflow catalog start vllm_deepseek_v4_flash --values ModelVolume=volume://user/models,MaxReplicas=4
```

Clients address the model as `deepseek-ai/DeepSeek-V4-Flash` regardless of the
variant served, because the service pins `--served-model-name`. Gated
checkpoints need `HuggingFaceHubToken`. Non-public endpoints need a bearer
token from `fuzzball workflow endpoints generate-token`.

## Default configuration

`Hardware=h200`, `Strategy=single_node_tep`, `Variant=default` requests 8
GPU(s) per replica and renders:

```sh
vllm serve deepseek-ai/DeepSeek-V4-Flash-0731 \
  --trust-remote-code \
  --kv-cache-dtype fp8 \
  --block-size 256 \
  --enable-expert-parallel \
  --tensor-parallel-size 8 \
  --tokenizer-mode deepseek_v4 \
  --tool-call-parser deepseek_v4 \
  --enable-auto-tool-choice \
  --reasoning-parser deepseek_v4 \
  --reasoning-config '{"reasoning_parser":"deepseek_v4","reasoning_start_str":"","reasoning_end_str":""}' \
  --served-model-name deepseek-ai/DeepSeek-V4-Flash
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
  https://recipes.vllm.ai/deepseek-ai/DeepSeek-V4-Flash. Regenerate this
  application with `scripts/gen_models.py` after the recipe changes.
