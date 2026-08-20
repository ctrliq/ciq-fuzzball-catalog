# Copyright 2026 CIQ, Inc. All rights reserved.
---
id: "ciq/ml_and_ai/vllm_glm_5_2"
name: "vLLM GLM-5.2"
category: "ML_AND_AI"
tags:
- LLM
- inference
- vllm
- autoscaling
- text
- GLM (Z-AI)
---

Serves [`zai-org/GLM-5.2`](https://recipes.vllm.ai/zai-org/GLM-5.2) from an
autoscaled pool of vLLM ([vLLM docs](https://docs.vllm.ai/en/stable)) replicas
behind a single OpenAI-compatible base URL. Deployment parameters come from the
[vLLM recipe for GLM-5.2](https://recipes.vllm.ai/zai-org/GLM-5.2): every vLLM
flag, environment variable, container image, GPU count and parallel layout
below is what that recipe validated for the selected hardware.

GLM-5.2 — frontier-scale MoE language model (~743B total parameters, 39B
active) with up to 5-token MTP speculative decoding and thinking mode

## Model

- **Checkpoint**: `zai-org/GLM-5.2`
- **Architecture**: moe, 743B parameters
- **Active parameters**: 39B
- **Context length**: 1048576 tokens
- **Minimum vLLM version**: 0.23.0
- **Recipe difficulty**: advanced

## Supported hardware

| Hardware | Node | GPUs per replica | Recipe status |
| --- | --- | --- | --- |
| `b200` | 8x B200, 1440 GB | 8 | verified |
| `b300` | 8x B300, 2144 GB | 8 | verified |
| `gb200` | 4x GB200 NVL4, 768 GB | 4 | untested upstream |
| `gb300` | 4x GB300 NVL4, 1152 GB | 4 | untested upstream |
| `h200` | 8x H200, 1128 GB | 8 | untested upstream |
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
| `bf16` | bf16 | 1786 GB | `zai-org/GLM-5.2` |
| `default` | fp8 | 893 GB | `zai-org/GLM-5.2-FP8` |
| `mxfp4` | mxfp4 | 446 GB | `amd/GLM-5.2-MXFP4` |
| `nvfp4` | nvfp4 | 558 GB | `nvidia/GLM-5.2-NVFP4` |

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
  decoding (up to 7 draft tokens)

## Usage

```sh
fuzzball workflow catalog start vllm_glm_5_2
fuzzball workflow catalog start vllm_glm_5_2 --values Hardware=mi355x,Strategy=single_node_tp,Variant=nvfp4
fuzzball workflow catalog start vllm_glm_5_2 --values ModelVolume=volume://user/models,MaxReplicas=4
```

Clients address the model as `zai-org/GLM-5.2` regardless of the variant
served, because the service pins `--served-model-name`. Gated checkpoints need
`HuggingFaceHubToken`. Non-public endpoints need a bearer token from `fuzzball
workflow endpoints generate-token`.

## Default configuration

`Hardware=h200`, `Strategy=single_node_tp`, `Variant=default` requests 8 GPU(s)
per replica and renders:

```sh
vllm serve zai-org/GLM-5.2-FP8 \
  --tensor-parallel-size 8 \
  --kv-cache-dtype fp8 \
  --tool-call-parser glm47 \
  --enable-auto-tool-choice \
  --reasoning-parser glm45 \
  --served-model-name zai-org/GLM-5.2
```

Image: `docker://vllm/vllm-openai:v0.23.0`

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
  https://recipes.vllm.ai/zai-org/GLM-5.2. Regenerate this application with
  `scripts/gen_models.py` after the recipe changes.
