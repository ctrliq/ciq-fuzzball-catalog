# Copyright 2026 CIQ, Inc. All rights reserved.
---
id: "ciq/ml_and_ai/vllm_dots3_note_prev"
name: "vLLM dots3-note-prev"
category: "ML_AND_AI"
tags:
- LLM
- inference
- vllm
- autoscaling
- multimodal
- text
- Dots
---

Serves
[`dots-studio/dots3-note-prev`](https://recipes.vllm.ai/dots-studio/dots3-note-prev)
from an autoscaled pool of vLLM ([vLLM docs](https://docs.vllm.ai/en/stable))
replicas behind a single OpenAI-compatible base URL. Deployment parameters come
from the [vLLM recipe for
dots3-note-prev](https://recipes.vllm.ai/dots-studio/dots3-note-prev): every
vLLM flag, environment variable, container image, GPU count and parallel layout
below is what that recipe validated for the selected hardware.

Multimodal MoE model available in BF16 and native FP8, with hybrid DSA and SWA,
512K context, and MTP speculative decoding.

## Model

- **Checkpoint**: `dots-studio/dots3-note-prev`
- **Architecture**: moe, 288B parameters
- **Active parameters**: 17B
- **Context length**: 524288 tokens
- **Minimum vLLM version**: 0.28.0
- **Recipe difficulty**: advanced

## Supported hardware

| Hardware | Node | GPUs per replica | Recipe status |
| --- | --- | --- | --- |
| `h100` | 8x H100, 640 GB | 8 | verified |
| `h200` | 8x H200, 1128 GB | 8 | untested upstream |

A replica requests exactly the GPUs its parallel size shards across, so one GPU
is requested where the weights fit one GPU. Hardware the recipe marks
`unsupported`, hardware that cannot hold the weights on one node, and profiles
with no Fuzzball device key (TPU, CPU, Intel XPU) are not offered.

## Variants

| Variant | Precision | Minimum VRAM | Checkpoint |
| --- | --- | --- | --- |
| `bf16` | bf16 | 692 GB | `dots-studio/dots3-note-prev` |
| `default` | fp8 | 359 GB | `dots-studio/dots3-note-prev-fp8` |

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

-  **`EnableReasoning`** (default off): Extract Qwen3-style <think> traces into
  the OpenAI reasoning field.
-  **`EnableToolCalling`** (default off): Parse dots3-note-prev's native XML
  tool-call format with automatic tool choice.
-  **`EnableTextOnly`** (default off): Load only the language model for text
  workloads, skipping the vision and audio encoders.
-  **`EnableSpecDecoding`** (default off): Enable MTP speculative decoding with
  the checkpoint's prediction head.

## Usage

```sh
fuzzball workflow catalog start vllm_dots3_note_prev
fuzzball workflow catalog start vllm_dots3_note_prev --values Hardware=h200,Strategy=single_node_tp,Variant=default
fuzzball workflow catalog start vllm_dots3_note_prev --values ModelVolume=volume://user/models,MaxReplicas=4
```

Clients address the model as `dots-studio/dots3-note-prev` regardless of the
variant served, because the service pins `--served-model-name`. Gated
checkpoints need `HuggingFaceHubToken`. Non-public endpoints need a bearer
token from `fuzzball workflow endpoints generate-token`.

## Default configuration

`Hardware=h200`, `Strategy=single_node_tep`, `Variant=default` requests 8
GPU(s) per replica and renders:

```sh
vllm serve dots-studio/dots3-note-prev-fp8 \
  --served-model-name dots3-note-prev \
  --gpu-memory-utilization 0.9 \
  --max-model-len 262144 \
  --max-num-batched-tokens 8192 \
  --block-size 64 \
  --mm-processor-cache-gb 32 \
  --enable-expert-parallel \
  --tensor-parallel-size 8 \
  --moe-backend deep_gemm \
  --served-model-name dots-studio/dots3-note-prev
```

Image: `docker://vllm/vllm-openai:nightly`

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
  https://recipes.vllm.ai/dots-studio/dots3-note-prev. Regenerate this
  application with `scripts/gen_models.py` after the recipe changes.
