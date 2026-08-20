# Copyright 2026 CIQ, Inc. All rights reserved.
---
id: "ciq/ml_and_ai/vllm_paddleocr_vl_1_6"
name: "vLLM PaddleOCR-VL-1.6"
category: "ML_AND_AI"
tags:
- LLM
- inference
- vllm
- autoscaling
- multimodal
- PaddlePaddle
---

Serves
[`PaddlePaddle/PaddleOCR-VL-1.6`](https://recipes.vllm.ai/PaddlePaddle/PaddleOCR-VL-1.6)
from an autoscaled pool of vLLM ([vLLM docs](https://docs.vllm.ai/en/stable))
replicas behind a single OpenAI-compatible base URL. Deployment parameters come
from the [vLLM recipe for
PaddleOCR-VL-1.6](https://recipes.vllm.ai/PaddlePaddle/PaddleOCR-VL-1.6): every
vLLM flag, environment variable, container image, GPU count and parallel layout
below is what that recipe validated for the selected hardware.

PaddleOCR-VL-1.6 (0.9B) — region-aware data optimization + progressive
post-training; new SOTA 96.33% on OmniDocBench v1.6, drop-in replacement for
1.5

## Model

- **Checkpoint**: `PaddlePaddle/PaddleOCR-VL-1.6`
- **Architecture**: dense, 0.9B parameters
- **Active parameters**: 0.9B
- **Context length**: 131072 tokens
- **Minimum vLLM version**: 0.11.1
- **Recipe difficulty**: beginner

## Supported hardware

| Hardware | Node | GPUs per replica | Recipe status |
| --- | --- | --- | --- |
| `b200` | 8x B200, 1440 GB | 1 | untested upstream |
| `b300` | 8x B300, 2144 GB | 1 | untested upstream |
| `gb200` | 4x GB200 NVL4, 768 GB | 1 | untested upstream |
| `gb300` | 4x GB300 NVL4, 1152 GB | 1 | untested upstream |
| `h100` | 8x H100, 640 GB | 1 | untested upstream |
| `h200` | 8x H200, 1128 GB | 1 | untested upstream |
| `mi300x` | 8x MI300X, 1536 GB | 1 | untested upstream |
| `mi325x` | 8x MI325X, 2048 GB | 1 | untested upstream |
| `mi355x` | 8x MI355X, 2304 GB | 1 | untested upstream |

A replica requests exactly the GPUs its parallel size shards across, so one GPU
is requested where the weights fit one GPU. Hardware the recipe marks
`unsupported`, hardware that cannot hold the weights on one node, and profiles
with no Fuzzball device key (TPU, CPU, Intel XPU) are not offered.

## Features

-  **`EnableTextOnly`** (default off): Skip loading the vision encoder for
  text-only workloads — frees VRAM for KV cache. Mutually exclusive with
  encoder_parallel.
-  **`EnableEncoderParallel`** (default off): Run the vision encoder in
  data-parallel mode — avoids TP comm overhead on the small encoder. Mutually
  exclusive with text_only.

## Usage

```sh
fuzzball workflow catalog start vllm_paddleocr_vl_1_6
fuzzball workflow catalog start vllm_paddleocr_vl_1_6 --values Hardware=mi355x
fuzzball workflow catalog start vllm_paddleocr_vl_1_6 --values ModelVolume=volume://user/models,MaxReplicas=4
```

Clients address the model as `PaddlePaddle/PaddleOCR-VL-1.6` regardless of the
variant served, because the service pins `--served-model-name`. Gated
checkpoints need `HuggingFaceHubToken`. Non-public endpoints need a bearer
token from `fuzzball workflow endpoints generate-token`.

## Default configuration

`Hardware=h200`, `Strategy=single_node_tp`, `Variant=default` requests 1 GPU(s)
per replica and renders:

```sh
vllm serve PaddlePaddle/PaddleOCR-VL-1.6 \
  --trust-remote-code \
  --max-num-batched-tokens 16384 \
  --no-enable-prefix-caching \
  --mm-processor-cache-gb 0 \
  --tensor-parallel-size 1 \
  --served-model-name PaddlePaddle/PaddleOCR-VL-1.6
```

Image: `docker://vllm/vllm-openai:v0.11.1`

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
  -  `uv pip install paddlepaddle-gpu==3.2.1 --extra-index-url
    https://www.paddlepaddle.org.cn/packages/stable/cu126/`
  -  `uv pip install -U "paddleocr[doc-parser]>=3.6.0"`
  -  `uv pip install safetensors`
-  Deployment parameters track the recipe at
  https://recipes.vllm.ai/PaddlePaddle/PaddleOCR-VL-1.6. Regenerate this
  application with `scripts/gen_models.py` after the recipe changes.
