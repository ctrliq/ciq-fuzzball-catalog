# Copyright 2026 CIQ, Inc. All rights reserved.
---
id: "ciq/ml_and_ai/vllm_ling_3_0_flash"
name: "vLLM Ling-3.0-flash"
category: "ML_AND_AI"
tags:
- LLM
- inference
- vllm
- autoscaling
- text
- inclusionAI
---

Serves
[`inclusionAI/Ling-3.0-flash`](https://recipes.vllm.ai/inclusionAI/Ling-3.0-flash)
from an autoscaled pool of vLLM ([vLLM docs](https://docs.vllm.ai/en/stable))
replicas behind a single OpenAI-compatible base URL. Deployment parameters come
from the [vLLM recipe for
Ling-3.0-flash](https://recipes.vllm.ai/inclusionAI/Ling-3.0-flash): every vLLM
flag, environment variable, container image, GPU count and parallel layout
below is what that recipe validated for the selected hardware.

Ling-3.0-flash MoE model with BF16 and serialized block-FP8 checkpoints, 124B
total / 5.5B active parameters, and a 3.1B MTP layer

## Model

- **Checkpoint**: `inclusionAI/Ling-3.0-flash`
- **Architecture**: moe, 124B parameters
- **Active parameters**: 5.5B
- **Context length**: 262144 tokens
- **Minimum vLLM version**: 0.25.0
- **Recipe difficulty**: advanced

## Supported hardware

| Hardware | Node | GPUs per replica | Recipe status |
| --- | --- | --- | --- |
| `b200` | 8x B200, 1440 GB | 2/4 | untested upstream |
| `b300` | 8x B300, 2144 GB | 2/4 | untested upstream |
| `gb200` | 4x GB200 NVL4, 768 GB | 2/4 | untested upstream |
| `gb300` | 4x GB300 NVL4, 1152 GB | 2/4 | untested upstream |
| `h100` | 8x H100, 640 GB | 2/4 | untested upstream |
| `h200` | 8x H200, 1128 GB | 2/4 | verified |
| `mi300x` | 8x MI300X, 1536 GB | 2/4 | untested upstream |
| `mi325x` | 8x MI325X, 2048 GB | 2/4 | untested upstream |
| `mi355x` | 8x MI355X, 2304 GB | 2/4 | untested upstream |

A replica requests exactly the GPUs its parallel size shards across, so one GPU
is requested where the weights fit one GPU. Hardware the recipe marks
`unsupported`, hardware that cannot hold the weights on one node, and profiles
with no Fuzzball device key (TPU, CPU, Intel XPU) are not offered.

## Variants

| Variant | Precision | Minimum VRAM | Checkpoint |
| --- | --- | --- | --- |
| `default` | bf16 | 300 GB | `inclusionAI/Ling-3.0-flash` |
| `fp8` | fp8 | 150 GB | `inclusionAI/Ling-3.0-flash-fp8` |

## Features

-  **`EnableToolCalling`** (default on): Enable Ling 3 automatic tool calling
-  **`EnableReasoning`** (default on): Split Ling 3 thinking traces into
  reasoning_content
-  **`EnableSpecDecoding`** (default off): Use the model's native MTP head with
  three speculative tokens

## Usage

```sh
fuzzball workflow catalog start vllm_ling_3_0_flash
fuzzball workflow catalog start vllm_ling_3_0_flash --values Hardware=mi355x,Variant=fp8
fuzzball workflow catalog start vllm_ling_3_0_flash --values ModelVolume=volume://user/models,MaxReplicas=4
```

Clients address the model as `inclusionAI/Ling-3.0-flash` regardless of the
variant served, because the service pins `--served-model-name`. Gated
checkpoints need `HuggingFaceHubToken`. Non-public endpoints need a bearer
token from `fuzzball workflow endpoints generate-token`.

## Default configuration

`Hardware=h200`, `Strategy=single_node_tp`, `Variant=default` requests 4 GPU(s)
per replica and renders:

```sh
vllm serve inclusionAI/Ling-3.0-flash \
  --trust-remote-code \
  --dtype bfloat16 \
  --gpu-memory-utilization 0.9 \
  --enable-chunked-prefill \
  --compilation-config '{"cudagraph_mode":"FULL_AND_PIECEWISE"}' \
  --enable-prefix-caching \
  --tensor-parallel-size 4 \
  --enable-auto-tool-choice \
  --tool-call-parser ling3 \
  --reasoning-parser ling3 \
  --served-model-name inclusionAI/Ling-3.0-flash
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
  https://recipes.vllm.ai/inclusionAI/Ling-3.0-flash. Regenerate this
  application with `scripts/gen_models.py` after the recipe changes.
