# Copyright 2026 CIQ, Inc. All rights reserved.
---
id: "ciq/ml_and_ai/vllm_glm_4_6v"
name: "vLLM GLM-4.6V"
category: "ML_AND_AI"
tags:
- LLM
- inference
- vllm
- autoscaling
- multimodal
- GLM (Z-AI)
---

Serves [`zai-org/GLM-4.6V`](https://recipes.vllm.ai/zai-org/GLM-4.6V) from an
autoscaled pool of vLLM ([vLLM docs](https://docs.vllm.ai/en/stable)) replicas
behind a single OpenAI-compatible base URL. Deployment parameters come from the
[vLLM recipe for GLM-4.6V](https://recipes.vllm.ai/zai-org/GLM-4.6V): every
vLLM flag, environment variable, container image, GPU count and parallel layout
below is what that recipe validated for the selected hardware.

GLM-4.6 vision-language MoE model — image-text-to-text with 128K context,
native FP8 checkpoint, and expert parallelism

## Model

- **Checkpoint**: `zai-org/GLM-4.6V`
- **Architecture**: moe, 107B parameters
- **Active parameters**: 12B
- **Context length**: 131072 tokens
- **Minimum vLLM version**: 0.12.0
- **Recipe difficulty**: intermediate

## Supported hardware

| Hardware | Node | GPUs per replica | Recipe status |
| --- | --- | --- | --- |
| `b200` | 8x B200, 1440 GB | 1/8 | untested upstream |
| `b300` | 8x B300, 2144 GB | 1/8 | untested upstream |
| `gb200` | 4x GB200 NVL4, 768 GB | 1/4 | untested upstream |
| `gb300` | 4x GB300 NVL4, 1152 GB | 1/4 | untested upstream |
| `h100` | 8x H100, 640 GB | 8 | verified |
| `h200` | 8x H200, 1128 GB | 1/8 | verified |
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
| `default` | bf16 | 257 GB | `zai-org/GLM-4.6V` |
| `fp8` | fp8 | 128 GB | `zai-org/GLM-4.6V-FP8` |

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

-  **`EnableToolCalling`** (default on): GLM-4.5 tool call parser with
  automatic tool choice
-  **`EnableReasoning`** (default on): GLM-4.5 reasoning parser
-  **`EnableTextOnly`** (default off): Skip loading the vision encoder for
  text-only workloads — frees VRAM for KV cache. Mutually exclusive with
  encoder_parallel.

## Usage

```sh
fuzzball workflow catalog start vllm_glm_4_6v
fuzzball workflow catalog start vllm_glm_4_6v --values Hardware=mi355x,Strategy=single_node_tp,Variant=fp8
fuzzball workflow catalog start vllm_glm_4_6v --values ModelVolume=volume://user/models,MaxReplicas=4
```

Clients address the model as `zai-org/GLM-4.6V` regardless of the variant
served, because the service pins `--served-model-name`. Gated checkpoints need
`HuggingFaceHubToken`. Non-public endpoints need a bearer token from `fuzzball
workflow endpoints generate-token`.

## Default configuration

`Hardware=h200`, `Strategy=single_node_tp`, `Variant=default` requests 8 GPU(s)
per replica and renders:

```sh
vllm serve zai-org/GLM-4.6V \
  --trust-remote-code \
  --enable-expert-parallel \
  --allowed-local-media-path / \
  --mm-encoder-tp-mode data \
  --mm-processor-cache-type shm \
  --tensor-parallel-size 8 \
  --tool-call-parser glm45 \
  --enable-auto-tool-choice \
  --reasoning-parser glm45 \
  --served-model-name zai-org/GLM-4.6V
```

Image: `docker://vllm/vllm-openai:v0.12.0`

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
  https://recipes.vllm.ai/zai-org/GLM-4.6V. Regenerate this application with
  `scripts/gen_models.py` after the recipe changes.
