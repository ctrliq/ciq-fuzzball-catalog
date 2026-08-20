# Copyright 2026 CIQ, Inc. All rights reserved.
---
id: "ciq/ml_and_ai/vllm_qwen3_8_2_4t_a95b"
name: "vLLM Qwen3.8-2.4T-A95B"
category: "ML_AND_AI"
tags:
- LLM
- inference
- vllm
- autoscaling
- text
- Qwen
---

Serves
[`Qwen/Qwen3.8-2.4T-A95B`](https://recipes.vllm.ai/Qwen/Qwen3.8-2.4T-A95B) from
an autoscaled pool of vLLM ([vLLM docs](https://docs.vllm.ai/en/stable))
replicas behind a single OpenAI-compatible base URL. Deployment parameters come
from the [vLLM recipe for
Qwen3.8-2.4T-A95B](https://recipes.vllm.ai/Qwen/Qwen3.8-2.4T-A95B): every vLLM
flag, environment variable, container image, GPU count and parallel layout
below is what that recipe validated for the selected hardware.

2.4T-parameter hybrid-attention MoE (~95B active) with linear attention on 69
of 92 layers, 512 routed experts, a built-in MTP draft head, 262K native
context window and extensible to 1M context

## Model

- **Checkpoint**: `Qwen/Qwen3.8-2.4T-A95B`
- **Architecture**: moe, 2.4T parameters
- **Active parameters**: 95B
- **Context length**: 262144 tokens
- **Minimum vLLM version**: nightly
- **Recipe difficulty**: advanced

## Supported hardware

| Hardware | Node | GPUs per replica | Recipe status |
| --- | --- | --- | --- |
| `b300` | 8x B300, 2144 GB | 8 | verified |
| `mi325x` | 8x MI325X, 2048 GB | 8 | untested upstream |
| `mi355x` | 8x MI355X, 2304 GB | 8 | untested upstream |

A replica requests exactly the GPUs its parallel size shards across, so one GPU
is requested where the weights fit one GPU. Hardware the recipe marks
`unsupported`, hardware that cannot hold the weights on one node, and profiles
with no Fuzzball device key (TPU, CPU, Intel XPU) are not offered.

## Variants

| Variant | Precision | Minimum VRAM | Checkpoint |
| --- | --- | --- | --- |
| `mxfp4` | mxfp4 | 1917 GB | `Inferact/Qwen3.8-2.4T-A95B-MXFP4` |
| `nvfp4` | nvfp4 | 1737 GB | `Inferact/Qwen3.8-2.4T-A95B-NVFP4` |

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

-  **`EnableToolCalling`** (default on): Enable automatic tool choice. The chat
  template emits tool calls as <tool_call><function=…><parameter=…> XML, which
  is the qwen3_coder format — not JSON.
-  **`EnableReasoning`** (default on): Parse <think> blocks separately from the
  final answer. The template opens every assistant turn with <think>, so
  without this the reasoning lands in message.content.
-  **`EnableSpecDecoding`** (default off): Multi-token prediction using the
  draft head shipped inside the checkpoint — no separate speculator repo
  needed.

## Usage

```sh
fuzzball workflow catalog start vllm_qwen3_8_2_4t_a95b
fuzzball workflow catalog start vllm_qwen3_8_2_4t_a95b --values Hardware=mi355x,Strategy=single_node_tp,Variant=nvfp4
fuzzball workflow catalog start vllm_qwen3_8_2_4t_a95b --values ModelVolume=volume://user/models,MaxReplicas=4
```

Clients address the model as `Qwen/Qwen3.8-2.4T-A95B` regardless of the variant
served, because the service pins `--served-model-name`. Gated checkpoints need
`HuggingFaceHubToken`. Non-public endpoints need a bearer token from `fuzzball
workflow endpoints generate-token`.

## Default configuration

`Hardware=b300`, `Strategy=single_node_tp`, `Variant=nvfp4` requests 8 GPU(s)
per replica and renders:

```sh
vllm serve Inferact/Qwen3.8-2.4T-A95B-NVFP4 \
  --linear-backend flashinfer_cutedsl \
  --tensor-parallel-size 8 \
  --enable-auto-tool-choice \
  --tool-call-parser qwen3_coder \
  --reasoning-parser qwen3 \
  --served-model-name Qwen/Qwen3.8-2.4T-A95B
```

With environment:

```sh
VLLM_ENGINE_READY_TIMEOUT_S=3600
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
  -  `uv pip install -U "transformers>=5.4.0"`
-  Deployment parameters track the recipe at
  https://recipes.vllm.ai/Qwen/Qwen3.8-2.4T-A95B. Regenerate this application
  with `scripts/gen_models.py` after the recipe changes.
