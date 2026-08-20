# Copyright 2026 CIQ, Inc. All rights reserved.
---
id: "ciq/ml_and_ai/vllm_deepseek_v4_pro"
name: "vLLM DeepSeek-V4-Pro"
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
[`deepseek-ai/DeepSeek-V4-Pro`](https://recipes.vllm.ai/deepseek-ai/DeepSeek-V4-Pro)
from an autoscaled pool of vLLM ([vLLM docs](https://docs.vllm.ai/en/stable))
replicas behind a single OpenAI-compatible base URL. Deployment parameters come
from the [vLLM recipe for
DeepSeek-V4-Pro](https://recipes.vllm.ai/deepseek-ai/DeepSeek-V4-Pro): every
vLLM flag, environment variable, container image, GPU count and parallel layout
below is what that recipe validated for the selected hardware.

DeepSeek V4 flagship MoE (1.6T total / 49B active) with hybrid CSA+HCA
attention, manifold-constrained hyper-connections, Muon-trained on 32T+ tokens,
and three-tier reasoning.

## Model

- **Checkpoint**: `deepseek-ai/DeepSeek-V4-Pro`
- **Architecture**: moe, 1600B parameters
- **Active parameters**: 49B
- **Context length**: 1048576 tokens
- **Minimum vLLM version**: 0.20.0
- **Recipe difficulty**: hard

## Supported hardware

| Hardware | Node | GPUs per replica | Recipe status |
| --- | --- | --- | --- |
| `b200` | 8x B200, 1440 GB | 8 | verified |
| `b300` | 8x B300, 2144 GB | 8 | verified |
| `gb300` | 4x GB300 NVL4, 1152 GB | 4 | verified |
| `h200` | 8x H200, 1128 GB | 8 | verified |
| `mi355x` | 8x MI355X, 2304 GB | 8 | verified |

A replica requests exactly the GPUs its parallel size shards across, so one GPU
is requested where the weights fit one GPU. Hardware the recipe marks
`unsupported`, hardware that cannot hold the weights on one node, and profiles
with no Fuzzball device key (TPU, CPU, Intel XPU) are not offered.

## Variants

| Variant | Precision | Minimum VRAM | Checkpoint |
| --- | --- | --- | --- |
| `default` | fp8 | 960 GB | `deepseek-ai/DeepSeek-V4-Pro-0813` |
| `dspark` | fp8 | 960 GB | `deepseek-ai/DeepSeek-V4-Pro-DSpark` |
| `fp8` | fp8 | 960 GB | `deepseek-ai/DeepSeek-V4-Pro` |
| `nvfp4` | nvfp4 | 960 GB | `nvidia/DeepSeek-V4-Pro-NVFP4` |

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
fuzzball workflow catalog start vllm_deepseek_v4_pro
fuzzball workflow catalog start vllm_deepseek_v4_pro --values Hardware=mi355x,Strategy=single_node_tp,Variant=nvfp4
fuzzball workflow catalog start vllm_deepseek_v4_pro --values ModelVolume=volume://user/models,MaxReplicas=4
```

Clients address the model as `deepseek-ai/DeepSeek-V4-Pro` regardless of the
variant served, because the service pins `--served-model-name`. Gated
checkpoints need `HuggingFaceHubToken`. Non-public endpoints need a bearer
token from `fuzzball workflow endpoints generate-token`.

## Default configuration

`Hardware=h200`, `Strategy=single_node_tep`, `Variant=default` requests 8
GPU(s) per replica and renders:

```sh
vllm serve deepseek-ai/DeepSeek-V4-Pro-0813 \
  --trust-remote-code \
  --kv-cache-dtype fp8 \
  --block-size 256 \
  --enable-expert-parallel \
  --tensor-parallel-size 8 \
  --max-model-len 200000 \
  --gpu-memory-utilization 0.95 \
  --max-num-seqs 16 \
  --no-enable-flashinfer-autotune \
  --compilation-config '{"mode": 0, "cudagraph_mode": "FULL_DECODE_ONLY"}' \
  --tokenizer-mode deepseek_v4 \
  --tool-call-parser deepseek_v4 \
  --enable-auto-tool-choice \
  --reasoning-parser deepseek_v4 \
  --served-model-name deepseek-ai/DeepSeek-V4-Pro
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
  https://recipes.vllm.ai/deepseek-ai/DeepSeek-V4-Pro. Regenerate this
  application with `scripts/gen_models.py` after the recipe changes.
