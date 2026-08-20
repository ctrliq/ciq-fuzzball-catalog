# Copyright 2026 CIQ, Inc. All rights reserved.
---
id: "ciq/ml_and_ai/vllm_lfm2_5_vl_450m"
name: "vLLM LFM2.5-VL-450M"
category: "ML_AND_AI"
tags:
- LLM
- inference
- vllm
- autoscaling
- multimodal
- LiquidAI
---

Serves
[`LiquidAI/LFM2.5-VL-450M`](https://recipes.vllm.ai/LiquidAI/LFM2.5-VL-450M)
from an autoscaled pool of vLLM ([vLLM docs](https://docs.vllm.ai/en/stable))
replicas behind a single OpenAI-compatible base URL. Deployment parameters come
from the [vLLM recipe for LFM2.5 VL
450M](https://recipes.vllm.ai/LiquidAI/LFM2.5-VL-450M): every vLLM flag,
environment variable, container image, GPU count and parallel layout below is
what that recipe validated for the selected hardware.

Liquid AI's smallest vision-language model (450M) — LFM2 hybrid LM backbone
plus a SigLIP2 vision tower for image+text chat, light enough for edge GPUs.

## Model

- **Checkpoint**: `LiquidAI/LFM2.5-VL-450M`
- **Architecture**: dense, 450M parameters
- **Active parameters**: 450M
- **Context length**: 32768 tokens
- **Minimum vLLM version**: 0.23.0
- **Recipe difficulty**: beginner

## Supported hardware

| Hardware | Node | GPUs per replica | Recipe status |
| --- | --- | --- | --- |
| `b200` | 8x B200, 1440 GB | 1 | verified |
| `b300` | 8x B300, 2144 GB | 1 | untested upstream |
| `gb200` | 4x GB200 NVL4, 768 GB | 1 | untested upstream |
| `gb300` | 4x GB300 NVL4, 1152 GB | 1 | untested upstream |
| `h100` | 8x H100, 640 GB | 1 | verified |
| `h200` | 8x H200, 1128 GB | 1 | verified |
| `mi300x` | 8x MI300X, 1536 GB | 1 | untested upstream |
| `mi325x` | 8x MI325X, 2048 GB | 1 | untested upstream |
| `mi355x` | 8x MI355X, 2304 GB | 1 | untested upstream |

A replica requests exactly the GPUs its parallel size shards across, so one GPU
is requested where the weights fit one GPU. Hardware the recipe marks
`unsupported`, hardware that cannot hold the weights on one node, and profiles
with no Fuzzball device key (TPU, CPU, Intel XPU) are not offered.

## Usage

```sh
fuzzball workflow catalog start vllm_lfm2_5_vl_450m
fuzzball workflow catalog start vllm_lfm2_5_vl_450m --values Hardware=mi355x
fuzzball workflow catalog start vllm_lfm2_5_vl_450m --values ModelVolume=volume://user/models,MaxReplicas=4
```

Clients address the model as `LiquidAI/LFM2.5-VL-450M` regardless of the
variant served, because the service pins `--served-model-name`. Gated
checkpoints need `HuggingFaceHubToken`. Non-public endpoints need a bearer
token from `fuzzball workflow endpoints generate-token`.

## Default configuration

`Hardware=h200`, `Strategy=single_node_tp`, `Variant=default` requests 1 GPU(s)
per replica and renders:

```sh
vllm serve LiquidAI/LFM2.5-VL-450M \
  --tensor-parallel-size 1 \
  --served-model-name LiquidAI/LFM2.5-VL-450M
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
  https://recipes.vllm.ai/LiquidAI/LFM2.5-VL-450M. Regenerate this application
  with `scripts/gen_models.py` after the recipe changes.
