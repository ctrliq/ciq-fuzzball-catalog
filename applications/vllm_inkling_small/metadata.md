# Copyright 2026 CIQ, Inc. All rights reserved.
---
id: "ciq/ml_and_ai/vllm_inkling_small"
name: "vLLM Inkling-Small"
category: "ML_AND_AI"
tags:
- LLM
- inference
- vllm
- autoscaling
- multimodal
- Thinking Machines Lab
---

Serves
[`thinkingmachines/Inkling-Small-NVFP4`](https://recipes.vllm.ai/thinkingmachines/Inkling-Small)
from an autoscaled pool of vLLM ([vLLM docs](https://docs.vllm.ai/en/stable))
replicas behind a single OpenAI-compatible base URL. Deployment parameters come
from the [vLLM recipe for TML
Inkling-Small](https://recipes.vllm.ai/thinkingmachines/Inkling-Small): every
vLLM flag, environment variable, container image, GPU count and parallel layout
below is what that recipe validated for the selected hardware.

Natively multimodal 276B-parameter MoE from Thinking Machines Lab — 12B active
parameters, text/image/audio in, text out, and up to 1M context.

## Model

- **Checkpoint**: `thinkingmachines/Inkling-Small-NVFP4`
- **Architecture**: moe, 276B parameters
- **Active parameters**: 12B
- **Context length**: 1048576 tokens
- **Minimum vLLM version**: 0.26.0
- **Recipe difficulty**: intermediate

## Supported hardware

| Hardware | Node | GPUs per replica | Recipe status |
| --- | --- | --- | --- |
| `b200` | 8x B200, 1440 GB | 2/8 | untested upstream |
| `b300` | 8x B300, 2144 GB | 1/4/8 | untested upstream |
| `gb200` | 4x GB200 NVL4, 768 GB | 2/4 | untested upstream |
| `gb300` | 4x GB300 NVL4, 1152 GB | 1/4 | untested upstream |
| `h200` | 8x H200, 1128 GB | 2/8 | untested upstream |
| `mi300x` | 8x MI300X, 1536 GB | 2/4/8 | verified |
| `mi325x` | 8x MI325X, 2048 GB | 2/4/8 | untested upstream |
| `mi355x` | 8x MI355X, 2304 GB | 1/4/8 | verified |

A replica requests exactly the GPUs its parallel size shards across, so one GPU
is requested where the weights fit one GPU. Hardware the recipe marks
`unsupported`, hardware that cannot hold the weights on one node, and profiles
with no Fuzzball device key (TPU, CPU, Intel XPU) are not offered.

## Variants

| Variant | Precision | Minimum VRAM | Checkpoint |
| --- | --- | --- | --- |
| `bf16` | bf16 | 600 GB | `thinkingmachines/Inkling-Small` |
| `default` | nvfp4 | 180 GB | `thinkingmachines/Inkling-Small-NVFP4` |
| `mxfp4` | mxfp4 | 160 GB | `EmbeddedLLM/Inkling-Small-MXFP4` |

## Serving strategies

-  **`single_node_tep`** (Tensor + Expert Parallel): Single-node TEP. TP splits
  dense layers and EP splits expert layers across local GPUs. TP must be set to
  GPU count to avoid OOM from replicated dense layers. For MoE models only.
-  **`single_node_tp`** (Tensor Parallel): Single-node tensor parallel. Splits
  the model across all local GPUs. TP size is set to the GPU count at deploy
  time. The simplest multi-GPU strategy — works for all model architectures.

## Features

-  **`EnableToolCalling`** (default on): Enable auto tool choice with the
  Inkling tool-call parser.
-  **`EnableReasoning`** (default on): Enable reasoning output parsing with the
  Inkling reasoning parser.
-  **`EnableSpecDecoding`** (default off): Multi-Token Prediction (MTP)
  speculative decoding. Inkling ships 8 chained MTP heads, but the stable
  version of vLLM only supports 1 speculative token for now. Will support 8 in
  the next release.

## Usage

```sh
fuzzball workflow catalog start vllm_inkling_small
fuzzball workflow catalog start vllm_inkling_small --values Hardware=mi355x,Strategy=single_node_tp,Variant=mxfp4
fuzzball workflow catalog start vllm_inkling_small --values ModelVolume=volume://user/models,MaxReplicas=4
```

Clients address the model as `thinkingmachines/Inkling-Small-NVFP4` regardless
of the variant served, because the service pins `--served-model-name`. Gated
checkpoints need `HuggingFaceHubToken`. Non-public endpoints need a bearer
token from `fuzzball workflow endpoints generate-token`.

## Default configuration

`Hardware=h200`, `Strategy=single_node_tp`, `Variant=default` requests 2 GPU(s)
per replica and renders:

```sh
vllm serve thinkingmachines/Inkling-Small-NVFP4 \
  --trust-remote-code \
  --tokenizer-mode inkling \
  --kernel-config.enable_flashinfer_autotune=False \
  --tensor-parallel-size 2 \
  --enable-auto-tool-choice \
  --tool-call-parser inkling \
  --reasoning-parser inkling \
  --served-model-name thinkingmachines/Inkling-Small-NVFP4
```

With environment:

```sh
VLLM_USE_V2_MODEL_RUNNER=1
FLASH_ATTENTION_CUTE_DSL_CACHE_ENABLED=1
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
-  The recipe lists extra install steps that apply to its pip install path; the
  container image used here already carries them:
  -  `uv pip install "vllm[audio]"`
-  Deployment parameters track the recipe at
  https://recipes.vllm.ai/thinkingmachines/Inkling-Small. Regenerate this
  application with `scripts/gen_models.py` after the recipe changes.
