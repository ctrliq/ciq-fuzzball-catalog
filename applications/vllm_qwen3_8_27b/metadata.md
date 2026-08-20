# Copyright 2026 CIQ, Inc. All rights reserved.
---
id: "ciq/ml_and_ai/vllm_qwen3_8_27b"
name: "vLLM Qwen3.8-27B"
category: "ML_AND_AI"
tags:
- LLM
- inference
- vllm
- autoscaling
- multimodal
- text
- Qwen
---

Serves [`Qwen/Qwen3.8-27B`](https://recipes.vllm.ai/Qwen/Qwen3.8-27B) from an
autoscaled pool of vLLM ([vLLM docs](https://docs.vllm.ai/en/stable)) replicas
behind a single OpenAI-compatible base URL. Deployment parameters come from the
[vLLM recipe for Qwen3.8-27B](https://recipes.vllm.ai/Qwen/Qwen3.8-27B): every
vLLM flag, environment variable, container image, GPU count and parallel layout
below is what that recipe validated for the selected hardware.

27B-parameter dense hybrid-attention model with linear attention on 48 of 64
layers, a vision tower, a built-in MTP draft head, 262K native context window
and extensible to 1M context

## Model

- **Checkpoint**: `Qwen/Qwen3.8-27B`
- **Architecture**: dense, 27B parameters
- **Active parameters**: 27B
- **Context length**: 262144 tokens
- **Minimum vLLM version**: 0.17.0
- **Recipe difficulty**: beginner

## Supported hardware

| Hardware | Node | GPUs per replica | Recipe status |
| --- | --- | --- | --- |
| `b200` | 8x B200, 1440 GB | 1 | untested upstream |
| `b300` | 8x B300, 2144 GB | 1 | untested upstream |
| `gb200` | 4x GB200 NVL4, 768 GB | 1 | untested upstream |
| `gb300` | 4x GB300 NVL4, 1152 GB | 1 | verified |
| `h100` | 8x H100, 640 GB | 1 | untested upstream |
| `h200` | 8x H200, 1128 GB | 1 | untested upstream |
| `mi300x` | 8x MI300X, 1536 GB | 1 | untested upstream |
| `mi325x` | 8x MI325X, 2048 GB | 1 | untested upstream |
| `mi355x` | 8x MI355X, 2304 GB | 1 | untested upstream |
| `rtx_5090` | 1x RTX 5090, 32 GB | 1 | verified |
| `rtx_5090_2x` | 2x RTX 5090, 64 GB | 1/2 | verified |

A replica requests exactly the GPUs its parallel size shards across, so one GPU
is requested where the weights fit one GPU. Hardware the recipe marks
`unsupported`, hardware that cannot hold the weights on one node, and profiles
with no Fuzzball device key (TPU, CPU, Intel XPU) are not offered.

## Variants

| Variant | Precision | Minimum VRAM | Checkpoint |
| --- | --- | --- | --- |
| `default` | bf16 | 67 GB | `Qwen/Qwen3.8-27B` |
| `fp8` | fp8 | 38 GB | `Qwen/Qwen3.8-27B-FP8` |
| `nvfp4` | nvfp4 | 32 GB | `Inferact/Qwen3.8-27B-NVFP4` |

## Features

-  **`EnableToolCalling`** (default on): Enable automatic tool choice. The chat
  template emits tool calls as <tool_call><function=…><parameter=…> XML, which
  is the qwen3_coder format — not JSON.
-  **`EnableReasoning`** (default on): Parse <think> blocks separately from the
  final answer. The template opens every assistant turn with <think>, so
  without this the reasoning lands in message.content.
-  **`EnableSpecDecoding`** (default off): Multi-token prediction using the
  draft head shipped inside the checkpoint — no separate speculator repo
  needed.
-  **`EnableTextOnly`** (default off): Skip loading the vision encoder for
  text-only workloads — frees VRAM for KV cache. Mutually exclusive with
  encoder_parallel.
-  **`EnableEncoderParallel`** (default on): Run the vision encoder in
  data-parallel mode — avoids TP comm overhead on the small encoder. Mutually
  exclusive with text_only.

## Usage

```sh
fuzzball workflow catalog start vllm_qwen3_8_27b
fuzzball workflow catalog start vllm_qwen3_8_27b --values Hardware=rtx_5090_2x,Variant=nvfp4
fuzzball workflow catalog start vllm_qwen3_8_27b --values ModelVolume=volume://user/models,MaxReplicas=4
```

Clients address the model as `Qwen/Qwen3.8-27B` regardless of the variant
served, because the service pins `--served-model-name`. Gated checkpoints need
`HuggingFaceHubToken`. Non-public endpoints need a bearer token from `fuzzball
workflow endpoints generate-token`.

## Default configuration

`Hardware=h200`, `Strategy=single_node_tp`, `Variant=default` requests 1 GPU(s)
per replica and renders:

```sh
vllm serve Qwen/Qwen3.8-27B \
  --tensor-parallel-size 1 \
  --enable-auto-tool-choice \
  --tool-call-parser qwen3_coder \
  --reasoning-parser qwen3 \
  --mm-encoder-tp-mode data \
  --served-model-name Qwen/Qwen3.8-27B
```

Image: `docker://vllm/vllm-openai:qwen38`

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
-  The recipe lists extra install steps that apply to its pip install path; the
  container image used here already carries them:
  -  `uv pip install -U "transformers>=5.8.0"`
-  Deployment parameters track the recipe at
  https://recipes.vllm.ai/Qwen/Qwen3.8-27B. Regenerate this application with
  `scripts/gen_models.py` after the recipe changes.
