# Copyright 2026 CIQ, Inc. All rights reserved.
---
id: "ciq/ml_and_ai/vllm_minimax_m3"
name: "vLLM MiniMax-M3"
category: "ML_AND_AI"
tags:
- LLM
- inference
- vllm
- autoscaling
- text
- multimodal
- MiniMax
---

Serves [`MiniMaxAI/MiniMax-M3`](https://recipes.vllm.ai/MiniMaxAI/MiniMax-M3)
from an autoscaled pool of vLLM ([vLLM docs](https://docs.vllm.ai/en/stable))
replicas behind a single OpenAI-compatible base URL. Deployment parameters come
from the [vLLM recipe for
MiniMax-M3](https://recipes.vllm.ai/MiniMaxAI/MiniMax-M3): every vLLM flag,
environment variable, container image, GPU count and parallel layout below is
what that recipe validated for the selected hardware.

MiniMax M3 vision-language MoE (427B total / 26B active) for frontier coding,
agent toolchains, and 1M-token reasoning via MSA sparse attention — native
multimodal (image + video + computer use); BF16 plus MXFP8, NVIDIA Blackwell
NVFP4, and AMD MI355X MXFP4 variants. Runs on NVIDIA (Hopper/Blackwell) and AMD
CDNA4/CDNA3.

## Model

- **Checkpoint**: `MiniMaxAI/MiniMax-M3`
- **Architecture**: moe, 427B parameters
- **Active parameters**: 26B
- **Context length**: 1048576 tokens
- **Minimum vLLM version**: 0.24.0
- **Recipe difficulty**: advanced

## Supported hardware

| Hardware | Node | GPUs per replica | Recipe status |
| --- | --- | --- | --- |
| `b200` | 8x B200, 1440 GB | 8 | verified |
| `b300` | 8x B300, 2144 GB | 1/8 | verified |
| `gb200` | 4x GB200 NVL4, 768 GB | 4 | untested upstream |
| `gb300` | 4x GB300 NVL4, 1152 GB | 1/4 | untested upstream |
| `h100` | 8x H100, 640 GB | 8 | untested upstream |
| `h200` | 8x H200, 1128 GB | 8 | verified |
| `mi300x` | 8x MI300X, 1536 GB | 8 | verified |
| `mi325x` | 8x MI325X, 2048 GB | 8 | untested upstream |
| `mi355x` | 8x MI355X, 2304 GB | 8 | verified |

A replica requests exactly the GPUs its parallel size shards across, so one GPU
is requested where the weights fit one GPU. Hardware the recipe marks
`unsupported`, hardware that cannot hold the weights on one node, and profiles
with no Fuzzball device key (TPU, CPU, Intel XPU) are not offered.

## Variants

| Variant | Precision | Minimum VRAM | Checkpoint |
| --- | --- | --- | --- |
| `default` | bf16 | 1025 GB | `MiniMaxAI/MiniMax-M3` |
| `mxfp4` | mxfp4 | 257 GB | `amd/MiniMax-M3-MXFP4` |
| `mxfp8` | mxfp8 | 513 GB | `MiniMaxAI/MiniMax-M3-MXFP8` |
| `nvfp4` | nvfp4 | 257 GB | `nvidia/MiniMax-M3-NVFP4` |

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

-  **`EnableToolCalling`** (default on): MiniMax M3 tool call parser with
  automatic tool choice
-  **`EnableReasoning`** (default on): MiniMax M3 reasoning parser (supports
  `thinking` and `non-thinking` modes, switchable per request)
-  **`EnableSpecDecoding`** (default off): Eagle3 speculative decoding with an
  Inferact MiniMax-M3 draft head — accelerates decoding. Choose between the
  standard MHA head and the GQA head (16× smaller draft KV cache — better for
  long-context or high-batch deployments).
-  **`EnableTextOnly`** (default off): Skip loading the vision encoder for
  text-only workloads — frees VRAM for KV cache. Mutually exclusive with
  encoder_parallel.
-  **`EnableThinkingAlwaysOn`** (default off): Pin `thinking_mode: enabled`
  server-side — every turn reasons before answering, including after tool
  results. Recommended for agentic workflows.
-  **`EnableEncoderParallel`** (default off): Run the vision encoder
  data-parallel instead of tensor-parallel — avoids TP comm overhead on the
  small encoder. Also enables the host-shared-memory multimodal processor cache
  and the per-brand encoder attention backend (FlashInfer on NVIDIA, AITER
  FlashAttention on AMD). Mutually exclusive with text_only.

## Usage

```sh
fuzzball workflow catalog start vllm_minimax_m3
fuzzball workflow catalog start vllm_minimax_m3 --values Hardware=mi355x,Strategy=single_node_tp,Variant=nvfp4
fuzzball workflow catalog start vllm_minimax_m3 --values ModelVolume=volume://user/models,MaxReplicas=4
```

Clients address the model as `MiniMaxAI/MiniMax-M3` regardless of the variant
served, because the service pins `--served-model-name`. Gated checkpoints need
`HuggingFaceHubToken`. Non-public endpoints need a bearer token from `fuzzball
workflow endpoints generate-token`.

## Default configuration

`Hardware=h200`, `Strategy=single_node_tp`, `Variant=default` requests 8 GPU(s)
per replica and renders:

```sh
vllm serve MiniMaxAI/MiniMax-M3 \
  --block-size 128 \
  --tensor-parallel-size 8 \
  --tool-call-parser minimax_m3 \
  --enable-auto-tool-choice \
  --reasoning-parser minimax_m3 \
  --served-model-name MiniMaxAI/MiniMax-M3
```

Image: `docker://vllm/vllm-openai:minimax-m3`

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
  https://recipes.vllm.ai/MiniMaxAI/MiniMax-M3. Regenerate this application
  with `scripts/gen_models.py` after the recipe changes.
