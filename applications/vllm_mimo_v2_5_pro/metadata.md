# Copyright 2026 CIQ, Inc. All rights reserved.
---
id: "ciq/ml_and_ai/vllm_mimo_v2_5_pro"
name: "vLLM MiMo-V2.5-Pro"
category: "ML_AND_AI"
tags:
- LLM
- inference
- vllm
- autoscaling
- text
- MiMo (Xiaomi)
---

Serves
[`XiaomiMiMo/MiMo-V2.5-Pro`](https://recipes.vllm.ai/XiaomiMiMo/MiMo-V2.5-Pro)
from an autoscaled pool of vLLM ([vLLM docs](https://docs.vllm.ai/en/stable))
replicas behind a single OpenAI-compatible base URL. Deployment parameters come
from the [vLLM recipe for
MiMo-V2.5-Pro](https://recipes.vllm.ai/XiaomiMiMo/MiMo-V2.5-Pro): every vLLM
flag, environment variable, container image, GPU count and parallel layout
below is what that recipe validated for the selected hardware.

Xiaomi's flagship MoE reasoning model (1.02T total / 42B active) with hybrid
attention, native FP8 weights, and Multi-Token Prediction

## Model

- **Checkpoint**: `XiaomiMiMo/MiMo-V2.5-Pro`
- **Architecture**: moe, 1T parameters
- **Active parameters**: 42B
- **Context length**: 1048576 tokens
- **Minimum vLLM version**: 0.21.0
- **Recipe difficulty**: advanced

## Supported hardware

| Hardware | Node | GPUs per replica | Recipe status |
| --- | --- | --- | --- |
| `b200` | 8x B200, 1440 GB | 8 | untested upstream |
| `b300` | 8x B300, 2144 GB | 8 | untested upstream |
| `mi300x` | 8x MI300X, 1536 GB | 8 | untested upstream |
| `mi325x` | 8x MI325X, 2048 GB | 8 | untested upstream |
| `mi355x` | 8x MI355X, 2304 GB | 8 | untested upstream |

A replica requests exactly the GPUs its parallel size shards across, so one GPU
is requested where the weights fit one GPU. Hardware the recipe marks
`unsupported`, hardware that cannot hold the weights on one node, and profiles
with no Fuzzball device key (TPU, CPU, Intel XPU) are not offered.

## Serving strategies

-  **`single_node_tep`** (Tensor + Expert Parallel): Single-node TEP. TP splits
  dense layers and EP splits expert layers across local GPUs. TP must be set to
  GPU count to avoid OOM from replicated dense layers. For MoE models only.
-  **`single_node_tp`** (Tensor Parallel): Single-node tensor parallel. Splits
  the model across all local GPUs. TP size is set to the GPU count at deploy
  time. The simplest multi-GPU strategy — works for all model architectures.

## Features

-  **`EnableToolCalling`** (default on): MiMo tool-call parser
-  **`EnableReasoning`** (default on): MiMo reasoning parser
-  **`EnableSpecDecoding`** (default off): Multi-Token Prediction

## Usage

```sh
fuzzball workflow catalog start vllm_mimo_v2_5_pro
fuzzball workflow catalog start vllm_mimo_v2_5_pro --values Hardware=mi355x,Strategy=single_node_tp
fuzzball workflow catalog start vllm_mimo_v2_5_pro --values ModelVolume=volume://user/models,MaxReplicas=4
```

Clients address the model as `XiaomiMiMo/MiMo-V2.5-Pro` regardless of the
variant served, because the service pins `--served-model-name`. Gated
checkpoints need `HuggingFaceHubToken`. Non-public endpoints need a bearer
token from `fuzzball workflow endpoints generate-token`.

## Default configuration

`Hardware=b200`, `Strategy=single_node_tp`, `Variant=default` requests 8 GPU(s)
per replica and renders:

```sh
vllm serve XiaomiMiMo/MiMo-V2.5-Pro \
  --trust-remote-code \
  --max-model-len auto \
  --generation-config vllm \
  --gpu-memory-utilization 0.95 \
  --max-model-len auto \
  --tensor-parallel-size 8 \
  --tool-call-parser mimo \
  --enable-auto-tool-choice \
  --reasoning-parser mimo \
  --served-model-name XiaomiMiMo/MiMo-V2.5-Pro
```

Image: `docker://vllm/vllm-openai:v0.21.0`

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
  https://recipes.vllm.ai/XiaomiMiMo/MiMo-V2.5-Pro. Regenerate this application
  with `scripts/gen_models.py` after the recipe changes.
