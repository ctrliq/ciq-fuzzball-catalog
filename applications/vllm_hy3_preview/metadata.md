# Copyright 2026 CIQ, Inc. All rights reserved.
---
id: "ciq/ml_and_ai/vllm_hy3_preview"
name: "vLLM Hy3-preview"
category: "ML_AND_AI"
tags:
- LLM
- inference
- vllm
- autoscaling
- text
- Hunyuan (Tencent)
---

Serves [`tencent/Hy3-preview`](https://recipes.vllm.ai/tencent/Hy3-preview)
from an autoscaled pool of vLLM ([vLLM docs](https://docs.vllm.ai/en/stable))
replicas behind a single OpenAI-compatible base URL. Deployment parameters come
from the [vLLM recipe for
Hy3-preview](https://recipes.vllm.ai/tencent/Hy3-preview): every vLLM flag,
environment variable, container image, GPU count and parallel layout below is
what that recipe validated for the selected hardware.

Tencent Hunyuan Hy3-preview — scaled-up MoE language model (295B total / 21B
active) with a 3.8B MTP layer for speculative decoding, 256K context, and hy_v3
tool/reasoning parsers

## Model

- **Checkpoint**: `tencent/Hy3-preview`
- **Architecture**: moe, 295B parameters
- **Active parameters**: 21B
- **Context length**: 262144 tokens
- **Minimum vLLM version**: 0.20.0
- **Recipe difficulty**: intermediate

## Supported hardware

| Hardware | Node | GPUs per replica | Recipe status |
| --- | --- | --- | --- |
| `b200` | 8x B200, 1440 GB | 8 | untested upstream |
| `b300` | 8x B300, 2144 GB | 8 | untested upstream |
| `gb200` | 4x GB200 NVL4, 768 GB | 4 | untested upstream |
| `gb300` | 4x GB300 NVL4, 1152 GB | 4 | untested upstream |
| `h200` | 8x H200, 1128 GB | 8 | verified |
| `mi300x` | 8x MI300X, 1536 GB | 8 | verified |
| `mi325x` | 8x MI325X, 2048 GB | 8 | verified |
| `mi355x` | 8x MI355X, 2304 GB | 8 | verified |

A replica requests exactly the GPUs its parallel size shards across, so one GPU
is requested where the weights fit one GPU. Hardware the recipe marks
`unsupported`, hardware that cannot hold the weights on one node, and profiles
with no Fuzzball device key (TPU, CPU, Intel XPU) are not offered.

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

-  **`EnableToolCalling`** (default on): Hunyuan v3 tool call parser with
  automatic tool choice
-  **`EnableReasoning`** (default on): Hunyuan v3 reasoning parser for
  thinking-mode chain-of-thought extraction
-  **`EnableSpecDecoding`** (default off): Multi-Token Prediction speculative
  decoding using the model's built-in MTP layer

## Usage

```sh
fuzzball workflow catalog start vllm_hy3_preview
fuzzball workflow catalog start vllm_hy3_preview --values Hardware=mi355x,Strategy=single_node_tp
fuzzball workflow catalog start vllm_hy3_preview --values ModelVolume=volume://user/models,MaxReplicas=4
```

Clients address the model as `tencent/Hy3-preview` regardless of the variant
served, because the service pins `--served-model-name`. Gated checkpoints need
`HuggingFaceHubToken`. Non-public endpoints need a bearer token from `fuzzball
workflow endpoints generate-token`.

## Default configuration

`Hardware=h200`, `Strategy=single_node_tp`, `Variant=default` requests 8 GPU(s)
per replica and renders:

```sh
vllm serve tencent/Hy3-preview \
  --trust-remote-code \
  --tensor-parallel-size 8 \
  --tool-call-parser hy_v3 \
  --enable-auto-tool-choice \
  --reasoning-parser hy_v3 \
  --served-model-name tencent/Hy3-preview
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
  https://recipes.vllm.ai/tencent/Hy3-preview. Regenerate this application with
  `scripts/gen_models.py` after the recipe changes.
