# Copyright 2026 CIQ, Inc. All rights reserved.
---
id: "ciq/ml_and_ai/vllm_ring_1t_fp8"
name: "vLLM Ring-1T-FP8"
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
[`inclusionAI/Ring-1T-FP8`](https://recipes.vllm.ai/inclusionAI/Ring-1T-FP8)
from an autoscaled pool of vLLM ([vLLM docs](https://docs.vllm.ai/en/stable))
replicas behind a single OpenAI-compatible base URL. Deployment parameters come
from the [vLLM recipe for
Ring-1T-FP8](https://recipes.vllm.ai/inclusionAI/Ring-1T-FP8): every vLLM flag,
environment variable, container image, GPU count and parallel layout below is
what that recipe validated for the selected hardware.

Ring-1T (BailingMoeV2) FP8 model (~1T total params) for 8xH200 or 8xMI300X
deployment

## Model

- **Checkpoint**: `inclusionAI/Ring-1T-FP8`
- **Architecture**: moe, 1T parameters
- **Active parameters**: 50B
- **Context length**: 65536 tokens
- **Minimum vLLM version**: 0.11.0
- **Recipe difficulty**: advanced

## Supported hardware

| Hardware | Node | GPUs per replica | Recipe status |
| --- | --- | --- | --- |
| `b200` | 8x B200, 1440 GB | 8 | untested upstream |
| `b300` | 8x B300, 2144 GB | 8 | untested upstream |
| `mi300x` | 8x MI300X, 1536 GB | 8 | verified |
| `mi325x` | 8x MI325X, 2048 GB | 8 | verified |
| `mi355x` | 8x MI355X, 2304 GB | 8 | verified |

A replica requests exactly the GPUs its parallel size shards across, so one GPU
is requested where the weights fit one GPU. Hardware the recipe marks
`unsupported`, hardware that cannot hold the weights on one node, and profiles
with no Fuzzball device key (TPU, CPU, Intel XPU) are not offered.

## Usage

```sh
fuzzball workflow catalog start vllm_ring_1t_fp8
fuzzball workflow catalog start vllm_ring_1t_fp8 --values Hardware=mi355x
fuzzball workflow catalog start vllm_ring_1t_fp8 --values ModelVolume=volume://user/models,MaxReplicas=4
```

Clients address the model as `inclusionAI/Ring-1T-FP8` regardless of the
variant served, because the service pins `--served-model-name`. Gated
checkpoints need `HuggingFaceHubToken`. Non-public endpoints need a bearer
token from `fuzzball workflow endpoints generate-token`.

## Default configuration

`Hardware=b200`, `Strategy=single_node_tp`, `Variant=default` requests 8 GPU(s)
per replica and renders:

```sh
vllm serve inclusionAI/Ring-1T-FP8 \
  --trust-remote-code \
  --max-num-seqs 32 \
  --kv-cache-dtype fp8 \
  --served-model-name Ring-1T-FP8 \
  --gpu-memory-utilization 0.97 \
  --compilation-config '{"use_inductor": false}' \
  --tensor-parallel-size 8 \
  --served-model-name inclusionAI/Ring-1T-FP8
```

Image: `docker://vllm/vllm-openai:v0.11.0`

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
  https://recipes.vllm.ai/inclusionAI/Ring-1T-FP8. Regenerate this application
  with `scripts/gen_models.py` after the recipe changes.
