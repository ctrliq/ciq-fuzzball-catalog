# Copyright 2026 CIQ, Inc. All rights reserved.
---
id: "ciq/ml_and_ai/vllm_diffusiongemma_26b_a4b_it"
name: "vLLM diffusiongemma-26B-A4B-it"
category: "ML_AND_AI"
tags:
- LLM
- inference
- vllm
- autoscaling
- multimodal
- text
- Google
---

Serves
[`google/diffusiongemma-26B-A4B-it`](https://recipes.vllm.ai/Google/diffusiongemma-26B-A4B-it)
from an autoscaled pool of vLLM ([vLLM docs](https://docs.vllm.ai/en/stable))
replicas behind a single OpenAI-compatible base URL. Deployment parameters come
from the [vLLM recipe for DiffusionGemma 26B-A4B
IT](https://recipes.vllm.ai/Google/diffusiongemma-26B-A4B-it): every vLLM flag,
environment variable, container image, GPU count and parallel layout below is
what that recipe validated for the selected hardware.

Google's DiffusionGemma — a block-diffusion language model built on Gemma 4's
MoE backbone (26B total / 4B active). Generates tokens via iterative denoising
over a fixed-length canvas rather than left-to-right autoregressive decoding,
enabling higher throughput with parallel block generation.

## Model

- **Checkpoint**: `google/diffusiongemma-26B-A4B-it`
- **Architecture**: moe, 26B parameters
- **Active parameters**: 4B
- **Context length**: 262144 tokens
- **Minimum vLLM version**: 0.24.0
- **Recipe difficulty**: advanced

## Supported hardware

| Hardware | Node | GPUs per replica | Recipe status |
| --- | --- | --- | --- |
| `b200` | 8x B200, 1440 GB | 1 | untested upstream |
| `b300` | 8x B300, 2144 GB | 1 | untested upstream |
| `dgx_spark_gb10` | 1x DGX Spark (GB10), 128 GB | 1 | verified |
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

## Variants

| Variant | Precision | Minimum VRAM | Checkpoint |
| --- | --- | --- | --- |
| `default` | bf16 | 64 GB | `google/diffusiongemma-26B-A4B-it` |
| `fp8` | fp8 | 32 GB | `RedHatAI/diffusiongemma-26B-A4B-it-FP8-dynamic` |
| `nvfp4` | nvfp4 | 24 GB | `RedHatAI/diffusiongemma-26B-A4B-it-NVFP4` |
| `nvidia_nvfp4` | nvfp4 | 24 GB | `nvidia/diffusiongemma-26B-A4B-it-NVFP4` |

## Features

-  **`EnableToolCalling`** (default on): Enable automatic tool choice with
  Gemma 4 parser and chat template
-  **`EnableReasoning`** (default on): Enable structured thinking/reasoning
  output

## Usage

```sh
fuzzball workflow catalog start vllm_diffusiongemma_26b_a4b_it
fuzzball workflow catalog start vllm_diffusiongemma_26b_a4b_it --values Hardware=mi355x,Variant=nvidia_nvfp4
fuzzball workflow catalog start vllm_diffusiongemma_26b_a4b_it --values ModelVolume=volume://user/models,MaxReplicas=4
```

Clients address the model as `google/diffusiongemma-26B-A4B-it` regardless of
the variant served, because the service pins `--served-model-name`. Gated
checkpoints need `HuggingFaceHubToken`. Non-public endpoints need a bearer
token from `fuzzball workflow endpoints generate-token`.

## Default configuration

`Hardware=h200`, `Strategy=single_node_tp`, `Variant=default` requests 1 GPU(s)
per replica and renders:

```sh
vllm serve google/diffusiongemma-26B-A4B-it \
  --max-num-seqs 4 \
  --tensor-parallel-size 1 \
  --enable-auto-tool-choice \
  --tool-call-parser gemma4 \
  --chat-template examples/tool_chat_template_gemma4.jinja \
  --reasoning-parser gemma4 \
  --served-model-name google/diffusiongemma-26B-A4B-it
```

Image: `docker://vllm/vllm-openai:gemma`

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
  https://recipes.vllm.ai/Google/diffusiongemma-26B-A4B-it. Regenerate this
  application with `scripts/gen_models.py` after the recipe changes.
