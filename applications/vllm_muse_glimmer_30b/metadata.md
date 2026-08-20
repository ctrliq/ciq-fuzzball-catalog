# Copyright 2026 CIQ, Inc. All rights reserved.
---
id: "ciq/ml_and_ai/vllm_muse_glimmer_30b"
name: "vLLM Muse-Glimmer-30B"
category: "ML_AND_AI"
tags:
- LLM
- inference
- vllm
- autoscaling
- text
- multimodal
- Muse (Meta)
---

Serves
[`meta-models/Muse-Glimmer-30B`](https://recipes.vllm.ai/meta-models/Muse-Glimmer-30B)
from an autoscaled pool of vLLM ([vLLM docs](https://docs.vllm.ai/en/stable))
replicas behind a single OpenAI-compatible base URL. Deployment parameters come
from the [vLLM recipe for Muse Glimmer
30B](https://recipes.vllm.ai/meta-models/Muse-Glimmer-30B): every vLLM flag,
environment variable, container image, GPU count and parallel layout below is
what that recipe validated for the selected hardware.

Dense 29.6B vision-language model with a ViT-G/14 perception encoder and 128K
context, distilled from Muse Spark for local agentic use. Emits channel-scoped
reasoning and XML-style ATEM tool calls rather than JSON, so it needs the
dedicated `muse_glimmer` tool-call and reasoning parsers.

## Model

- **Checkpoint**: `meta-models/Muse-Glimmer-30B`
- **Architecture**: dense, 29.6B parameters
- **Active parameters**: 29.6B
- **Context length**: 131072 tokens
- **Minimum vLLM version**: 0.27.0
- **Recipe difficulty**: advanced

## Supported hardware

| Hardware | Node | GPUs per replica | Recipe status |
| --- | --- | --- | --- |
| `b200` | 8x B200, 1440 GB | 1 | untested upstream |
| `b300` | 8x B300, 2144 GB | 1 | untested upstream |
| `dgx_spark_gb10` | 1x DGX Spark (GB10), 128 GB | 1 | verified |
| `gb200` | 4x GB200 NVL4, 768 GB | 1 | untested upstream |
| `gb300` | 4x GB300 NVL4, 1152 GB | 1 | verified |
| `h100` | 8x H100, 640 GB | 1 | untested upstream |
| `h200` | 8x H200, 1128 GB | 1 | untested upstream |
| `mi300x` | 8x MI300X, 1536 GB | 1 | verified |
| `mi325x` | 8x MI325X, 2048 GB | 1 | verified |
| `mi355x` | 8x MI355X, 2304 GB | 1 | verified |
| `rtx_5090` | 1x RTX 5090, 32 GB | 1 | verified |
| `rtx_5090_2x` | 2x RTX 5090, 64 GB | 1/2 | verified |

A replica requests exactly the GPUs its parallel size shards across, so one GPU
is requested where the weights fit one GPU. Hardware the recipe marks
`unsupported`, hardware that cannot hold the weights on one node, and profiles
with no Fuzzball device key (TPU, CPU, Intel XPU) are not offered.

## Variants

| Variant | Precision | Minimum VRAM | Checkpoint |
| --- | --- | --- | --- |
| `default` | bf16 | 72 GB | `meta-models/Muse-Glimmer-30B` |
| `fp8_block` | fp8 | 40 GB | `RedHatAI/Muse-Glimmer-30B-FP8-block` |
| `nvfp4` | nvfp4 | 31 GB | `Inferact/Muse-Glimmer-30B-NVFP4-W4A4` |

## Features

-  **`EnableToolCalling`** (default on): ATEM (XML-style) tool calls with
  automatic tool choice. Calls arrive in `message.tool_calls`; do not enable
  guided JSON — this model does not emit JSON tool calls. It emits one tool
  call per message: several calls arrive as consecutive assistant messages, not
  a single multi-element `tool_calls` array.
-  **`EnableReasoning`** (default on): Channel-scoped chain-of-thought.
  Surfaces as `message.reasoning` (non-streaming) and `delta.reasoning`
  (streaming) — note this model uses `reasoning`, not `reasoning_content`.
  Effort is controlled by a `Reasoning strength: <low|medium|high|xhigh>` line
  in the system prompt.
-  **`EnableSpecDecoding`** (default off): DFlash block-diffusion draft head —
  predicts a whole block in one forward, verified in parallel by the target.
  `num_speculative_tokens: 15` is not a tuning knob: the head has `block_size:
  16` and slot 0 re-presents the last accepted token, so 15 is what remains.

## Usage

```sh
fuzzball workflow catalog start vllm_muse_glimmer_30b
fuzzball workflow catalog start vllm_muse_glimmer_30b --values Hardware=rtx_5090_2x,Variant=nvfp4
fuzzball workflow catalog start vllm_muse_glimmer_30b --values ModelVolume=volume://user/models,MaxReplicas=4
```

Clients address the model as `meta-models/Muse-Glimmer-30B` regardless of the
variant served, because the service pins `--served-model-name`. Gated
checkpoints need `HuggingFaceHubToken`. Non-public endpoints need a bearer
token from `fuzzball workflow endpoints generate-token`.

## Default configuration

`Hardware=dgx_spark_gb10`, `Strategy=single_node_tp`, `Variant=default`
requests 1 GPU(s) per replica and renders:

```sh
vllm serve meta-models/Muse-Glimmer-30B \
  --generation-config auto \
  --tensor-parallel-size 1 \
  --enable-auto-tool-choice \
  --tool-call-parser muse_glimmer \
  --reasoning-parser muse_glimmer \
  --served-model-name meta-models/Muse-Glimmer-30B
```

Image: `docker://vllm/vllm-openai:muse-glimmer`

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
  https://recipes.vllm.ai/meta-models/Muse-Glimmer-30B. Regenerate this
  application with `scripts/gen_models.py` after the recipe changes.
