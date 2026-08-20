# Copyright 2026 CIQ, Inc. All rights reserved.
---
id: "ciq/ml_and_ai/vllm_ernie_4_5_21b_a3b_pt"
name: "vLLM ERNIE-4.5-21B-A3B-PT"
category: "ML_AND_AI"
tags:
- LLM
- inference
- vllm
- autoscaling
- text
- Ernie (Baidu)
---

Serves
[`baidu/ERNIE-4.5-21B-A3B-PT`](https://recipes.vllm.ai/baidu/ERNIE-4.5-21B-A3B-PT)
from an autoscaled pool of vLLM ([vLLM docs](https://docs.vllm.ai/en/stable))
replicas behind a single OpenAI-compatible base URL. Deployment parameters come
from the [vLLM recipe for
ERNIE-4.5](https://recipes.vllm.ai/baidu/ERNIE-4.5-21B-A3B-PT): every vLLM
flag, environment variable, container image, GPU count and parallel layout
below is what that recipe validated for the selected hardware.

Baidu ERNIE 4.5 MoE text models (21B-A3B, 300B-A47B) with BF16 and FP8 support
plus ERNIE-MTP speculative decoding

## Model

- **Checkpoint**: `baidu/ERNIE-4.5-21B-A3B-PT`
- **Architecture**: moe, 21B parameters
- **Active parameters**: 3B
- **Context length**: 131072 tokens
- **Minimum vLLM version**: 0.10.1
- **Recipe difficulty**: intermediate

## Supported hardware

| Hardware | Node | GPUs per replica | Recipe status |
| --- | --- | --- | --- |
| `b200` | 8x B200, 1440 GB | 1/8 | untested upstream |
| `b300` | 8x B300, 2144 GB | 1/8 | untested upstream |
| `gb200` | 4x GB200 NVL4, 768 GB | 1/4 | untested upstream |
| `gb300` | 4x GB300 NVL4, 1152 GB | 1/4 | untested upstream |
| `h100` | 8x H100, 640 GB | 8 | untested upstream |
| `h200` | 8x H200, 1128 GB | 1/8 | untested upstream |
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
| `300b` | bf16 | 640 GB | `baidu/ERNIE-4.5-300B-A47B-PT` |
| `default` | bf16 | 106 GB | `baidu/ERNIE-4.5-21B-A3B-PT` |

## Features

-  **`EnableSpecDecoding`** (default off): ERNIE-MTP (multi-token prediction)
  speculative decoding

## Usage

```sh
fuzzball workflow catalog start vllm_ernie_4_5_21b_a3b_pt
fuzzball workflow catalog start vllm_ernie_4_5_21b_a3b_pt --values Hardware=mi355x,Variant=default
fuzzball workflow catalog start vllm_ernie_4_5_21b_a3b_pt --values ModelVolume=volume://user/models,MaxReplicas=4
```

Clients address the model as `baidu/ERNIE-4.5-21B-A3B-PT` regardless of the
variant served, because the service pins `--served-model-name`. Gated
checkpoints need `HuggingFaceHubToken`. Non-public endpoints need a bearer
token from `fuzzball workflow endpoints generate-token`.

## Default configuration

`Hardware=h200`, `Strategy=single_node_tp`, `Variant=default` requests 1 GPU(s)
per replica and renders:

```sh
vllm serve baidu/ERNIE-4.5-21B-A3B-PT \
  --tensor-parallel-size 1 \
  --served-model-name baidu/ERNIE-4.5-21B-A3B-PT
```

Image: `docker://vllm/vllm-openai:v0.10.1`

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
  https://recipes.vllm.ai/baidu/ERNIE-4.5-21B-A3B-PT. Regenerate this
  application with `scripts/gen_models.py` after the recipe changes.
