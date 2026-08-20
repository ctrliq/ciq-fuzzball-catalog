# Copyright 2026 CIQ, Inc. All rights reserved.
---
id: "ciq/ml_and_ai/vllm_kimi_k3"
name: "vLLM Kimi-K3"
category: "ML_AND_AI"
tags:
- LLM
- inference
- vllm
- autoscaling
- multimodal
- text
- Moonshot AI
---

Serves [`moonshotai/Kimi-K3`](https://recipes.vllm.ai/moonshotai/Kimi-K3) from
an autoscaled pool of vLLM ([vLLM docs](https://docs.vllm.ai/en/stable))
replicas behind a single OpenAI-compatible base URL. Deployment parameters come
from the [vLLM recipe for Kimi-K3](https://recipes.vllm.ai/moonshotai/Kimi-K3):
every vLLM flag, environment variable, container image, GPU count and parallel
layout below is what that recipe validated for the selected hardware.

Pre-release 2.8T-parameter native multimodal MoE with Kimi Delta Attention,
Gated MLA, Attention Residuals, and a 1M-token context window

## Model

- **Checkpoint**: `moonshotai/Kimi-K3`
- **Architecture**: moe, 2.8T parameters
- **Active parameters**: 16 experts/token + shared (of 896 routed)
- **Context length**: 1048576 tokens
- **Minimum vLLM version**: 0.27.1
- **Recipe difficulty**: hard

## Supported hardware

| Hardware | Node | GPUs per replica | Recipe status |
| --- | --- | --- | --- |
| `b300` | 8x B300, 2144 GB | 8 | verified |
| `mi325x` | 8x MI325X, 2048 GB | 8 | untested upstream |
| `mi355x` | 8x MI355X, 2304 GB | 8 | verified |

A replica requests exactly the GPUs its parallel size shards across, so one GPU
is requested where the weights fit one GPU. Hardware the recipe marks
`unsupported`, hardware that cannot hold the weights on one node, and profiles
with no Fuzzball device key (TPU, CPU, Intel XPU) are not offered.

## Variants

| Variant | Precision | Minimum VRAM | Checkpoint |
| --- | --- | --- | --- |
| `default` | mxfp4 | 1680 GB | `moonshotai/Kimi-K3` |
| `nvfp4` | nvfp4 | 1650 GB | `RedHatAI/Kimi-K3-NVFP4` |

## Features

-  **`EnableToolCalling`** (default on): Enable automatic tool choice with the
  Kimi K3 tool-call parser.
-  **`EnableReasoning`** (default on): Parse Kimi K3 reasoning output
  separately from the final answer.
-  **`EnableSpecDecoding`** (default off): Use DSpark speculative decoding.
-  **`EnableTextOnly`** (default off): Skip the vision encoder for text-only
  workloads. Mutually exclusive with encoder_parallel.
-  **`EnableDecodeContextParallelism`** (default off): Decode context
  parallelism (DCP): shard the decode KV cache across the tensor-parallel ranks
  for decode-heavy long-context serving. The DCP size must divide the
  tensor-parallel size, so the args below assume the TP8 single-node layout.
  Pairs the TOKENSPEED_MLA decode backend with TRTLLM_RAGGED MLA prefill under
  FP8 KV.

## Usage

```sh
fuzzball workflow catalog start vllm_kimi_k3
fuzzball workflow catalog start vllm_kimi_k3 --values Hardware=mi355x,Variant=nvfp4
fuzzball workflow catalog start vllm_kimi_k3 --values ModelVolume=volume://user/models,MaxReplicas=4
```

Clients address the model as `moonshotai/Kimi-K3` regardless of the variant
served, because the service pins `--served-model-name`. Gated checkpoints need
`HuggingFaceHubToken`. Non-public endpoints need a bearer token from `fuzzball
workflow endpoints generate-token`.

## Default configuration

`Hardware=b300`, `Strategy=single_node_tp`, `Variant=default` requests 8 GPU(s)
per replica and renders:

```sh
vllm serve moonshotai/Kimi-K3 \
  --trust-remote-code \
  --gpu-memory-utilization 0.95 \
  --tensor-parallel-size 8 \
  --load-format fastsafetensors \
  --no-enable-flashinfer-autotune \
  --max-model-len 1048576 \
  --kv-cache-dtype fp8 \
  --attention-config '{"use_prefill_query_quantization":true,"mla_prefill_backend":"flashinfer"}' \
  --enable-prefix-caching \
  --enable-auto-tool-choice \
  --tool-call-parser kimi_k3 \
  --reasoning-parser kimi_k3 \
  --served-model-name moonshotai/Kimi-K3
```

With environment:

```sh
VLLM_ALLREDUCE_USE_FLASHINFER=1
VLLM_ENGINE_READY_TIMEOUT_S=3600
VLLM_USE_V2_MODEL_RUNNER=1
VLLM_USE_RUST_FRONTEND=1
```

Image: `docker://vllm/vllm-openai:v0.27.1`

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
  https://recipes.vllm.ai/moonshotai/Kimi-K3. Regenerate this application with
  `scripts/gen_models.py` after the recipe changes.
