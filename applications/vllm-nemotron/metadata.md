# Copyright 2026 CIQ, Inc. All rights reserved.
---
id: "ciq/ml_and_ai/nemotron_on_vllm"
name: "NVIDIA Nemotron 3 on vLLM"
category: "ML_AND_AI"
tags:
- LLM
- inference
- Nemotron
---
This workflow provides turnkey deployments of NVIDIA Nemotron 3 models on a vLLM
([vLLM docs](https://docs.vllm.ai/en/stable)) inference server and exposes an OpenAI-compatible
API through a server endpoint.

Pick a checkpoint from the **Model** dropdown and submit. Every other setting defaults to the
configuration published for that checkpoint in the [vLLM recipes](https://recipes.vllm.ai/nvidia),
the vLLM day-0 blog posts and the NVIDIA model cards — container image, tensor parallelism, GPU
count and model, KV cache type, reasoning and tool-call parsers, Mamba cache settings and
speculative decoding are all selected for you.

The server will run until the workflow is cancelled.

## Available models

| Model option | Params (total / active) | Weights | GPUs (tensor parallel) | vLLM image |
| --- | --- | --- | --- | --- |
| `nano-30b-fp8` (default) | 30B / ~3.5B | ~35 GB | 1 | `v0.12.0` |
| `nano-30b-bf16` | 30B / ~3.5B | ~72 GB | 1 | `v0.12.0` |
| `super-120b-fp8` | 120B / 12B | ~149 GB | 4 | `v0.17.1` |
| `super-120b-bf16` | 120B / 12B | ~298 GB | 4 | `v0.17.1` |
| `super-120b-nvfp4` | 120B / 12B | ~75 GB | 2 (Blackwell only) | `v0.24.0-ubuntu2404` |
| `ultra-550b-nvfp4` | 550B / 55B | ~330 GB | 8 | `v0.22.0` |
| `ultra-550b-bf16` | 550B / 55B | ~1320 GB | 8 | `v0.22.0` |

- [Nano](https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16) (30B-A3B) — Mamba-2 +
  MoE hybrid, single GPU.
- [Super](https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-BF16) (120B-A12B) —
  Mamba-hybrid LatentMoE with an MTP head.
- [Ultra](https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B-NVFP4) (550B-A55B) —
  Mamba-2 + attention + LatentMoE, NVFP4-pretrained.

`nano-30b-fp8` is the default because it is the only variant that fits a single 80 GB card with
room for a large KV cache, so it starts fastest and costs least to try.

## Storage

Weights are downloaded on first run into the HuggingFace cache under `/data`. The default
`DataVolume` is ephemeral, which means re-downloading on every run — acceptable for Nano, wasteful
for Super and impractical for Ultra. Point `DataVolume` at a persistent volume sized for the
weights in the table above before running anything larger than Nano.

## Access

The endpoint is created at `user` scope by default, so no API key is needed to get started. If you
widen `ServiceScope` to `group` or `organization`, set `ApiKeySecret` to a Fuzzball secret first —
clients then pass that value as a bearer token.

## Calling the server

The endpoint speaks the standard OpenAI API:

```python
from openai import OpenAI

client = OpenAI(base_url="https://<endpoint>/v1", api_key="EMPTY")

resp = client.chat.completions.create(
    model="nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-FP8",
    messages=[{"role": "user", "content": "Give me 3 bullet points about vLLM"}],
    temperature=1.0,
    top_p=1.0,
    max_tokens=10000,
)
msg = resp.choices[0].message
print("Reasoning:", getattr(msg, "reasoning_content", None))
print("Content:", msg.content)
```

All three models are reasoning-first: they emit a reasoning trace before the answer. The workflow
configures the matching reasoning parser (`nano_v3` for Nano, `nemotron_v3` for Super and Ultra),
so the trace arrives separately in `reasoning_content` rather than mixed into `content`. Give
reasoning requests plenty of headroom — around 10,000 `max_tokens` for Nano in thinking mode, more
for the larger models on agentic work.

Reasoning is toggled per request rather than per server:

```python
extra_body={"chat_template_kwargs": {"enable_thinking": False}}                         # off
extra_body={"chat_template_kwargs": {"enable_thinking": True}}                          # on (default)
extra_body={"chat_template_kwargs": {"enable_thinking": True, "medium_effort": True}}   # fewer reasoning tokens
```

Tool calling is enabled on the server (`--enable-auto-tool-choice` with the `qwen3_coder` parser).
When you send `tools` and want both the reasoning trace and the tool calls parsed, add
`"force_nonempty_content": True` to `chat_template_kwargs`. This is also the recommended addition
for coding-agent scaffolds pointed at these endpoints.

Suggested sampling: `temperature=1.0, top_p=1.0` for Nano reasoning tasks,
`temperature=0.6, top_p=0.95` for Nano tool calling, `temperature=1.0, top_p=0.95` for Ultra, and
greedy decoding with reasoning off.

## Long context

The models train to 1M tokens but their HuggingFace configs cap `max_model_len` at 262144, which is
what the recipes use. Setting `MaxModelLen` above 262144 (up to 1048576) turns on long-context mode
automatically. Budget for it: at 1M you also need to reduce `MaxNumSeqs` substantially, since KV
cache comes out of the same GPU memory.

## Tuning

The defaults reproduce the published configurations, so treat the **Tuning** category as the place
to trade throughput against latency once a baseline is running:

- `GPUDevices` doubles as the tensor parallel size. At a fixed batch size, more GPUs lowers latency
  but also lowers aggregate per-GPU throughput; it does free memory for a larger batch, so the two
  interact and the net effect has to be measured.
- `MaxNumSeqs` raises throughput and worsens per-user latency, bounded by GPU memory left after the
  weights load.
- `MaxModelLen` should match your real worst-case input plus output. An over-large value spends KV
  cache budget for no benefit.
- `MambaSsmCacheDtype` is the first thing to set to `float32` if output quality regresses against
  the published benchmarks.
- `EnableSpeculativeDecoding` controls MTP, which only Ultra's recipes define here. The accepted
  flag spelling differs between checkpoints and vLLM versions, so the workflow emits the spelling
  documented for the selected model.

## Not included

- **Multi-node BF16 Ultra with Ray.** This workflow runs a single service, so Ultra BF16 is the
  single-node 8 GPU configuration. The two-node Ray deployment is a separate topology.
- **Single-device and edge variants.** The DGX Spark (GB10), Jetson Thor and RTX PRO 6000 recipes
  need platform-specific containers and backend flags; use `ExtraServeArgs` and `VllmImage` if you
  are targeting those.
- **`Nemotron-3-Nano-4B` and `Nemotron-3-Nano-Omni-30B-A3B`.** Both have their own recipes.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| Out of memory during startup | Lower `GPUMemoryUtilization`, then `MaxModelLen` and `MaxNumSeqs`. |
| Reasoning trace appears inside `content` | The client is talking to a different server, or `ExtraServeArgs` overrode the parser. |
| Tool calls returned as plain text | Send `tools` in the request; the server-side parser is already enabled. |
| Tool calls parse but reasoning is lost, or vice versa | Send `chat_template_kwargs: {enable_thinking: true, force_nonempty_content: true}`. |
| Quality regression against published benchmarks | Set `MambaSsmCacheDtype` to `float32` and verify your sampling parameters. |
| Workflow never becomes ready on first run | The weights are still downloading. Ultra BF16 pulls ~1.3 TB; use a persistent `DataVolume` so this happens once. |

## References

- vLLM recipes (the maintained configurations): <https://recipes.vllm.ai/nvidia>
- Usage cookbooks: <https://github.com/NVIDIA-NeMo/Nemotron>
- Model cards: [Nano](https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B-BF16),
  [Super](https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Super-120B-A12B-BF16),
  [Ultra](https://huggingface.co/nvidia/NVIDIA-Nemotron-3-Ultra-550B-A55B-BF16)
