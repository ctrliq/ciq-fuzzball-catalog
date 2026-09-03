# Copyright 2026 CIQ, Inc. All rights reserved.
---
id: "ciq/ml_and_ai/vllm"
name: "vLLM"
category: "ML_AND_AI"
tags:
- LLM
- inference
- autoscaling
- OpenAI API
- ai
---
This workflow serves a HuggingFace model with a pool of
[vLLM](https://docs.vllm.ai/en/stable) replicas that scales automatically with
demand, and exposes one stable OpenAI-compatible base URL that is independent of
replica churn.

```
fuzzball workflow catalog start vLLM --values Model=hf://openai/gpt-oss-20b
fuzzball workflow catalog start vLLM --values Model=hf://openai/gpt-oss-120b,Gpu=amd
fuzzball workflow catalog start vLLM --values Model=hf://openai/gpt-oss-120b,MinReplicas=1,MaxReplicas=10
fuzzball workflow catalog start vLLM --values Model=hf://openai/gpt-oss-120b,GpusPerNode=4
fuzzball workflow catalog start vLLM --values Model=hf://openai/gpt-oss-20b,GpusPerNode=2,ExpertParallelism=true
fuzzball workflow catalog start vLLM --values Model=hf://openai/gpt-oss-120b,Nodes=2
```

The model is downloaded from the HuggingFace Hub once, at workflow start, into
the workflow's volume (data ingress). Replicas serve fully offline from that
local copy — no Hub access or token is needed at serve time. For gated or
private models, set `HfTokenSecret` to a Fuzzball secret holding your
HuggingFace token; it is used only during ingress.

## Front end

By default (`Proxy=true`) a [LiteLLM](https://docs.litellm.ai/) proxy holds the
workflow's service endpoint and load-balances across the currently-ready vLLM
replicas. Its backend list is kept up to date automatically as the pool scales
(Fuzzball dynamic configuration). LiteLLM's own request metrics drive pool
scale-up: failed requests wake an idle or saturated pool — including starting
the first replica when the pool is at zero — and a request rate at or above
`ScaleUpRequestsPerMinute` adds replicas under load. A request that arrives
while no replica is running fails fast and triggers scale-up; keep retrying at
normal client intervals — the retries themselves sustain the wake signal — and
the request succeeds once a replica is up, which can take several minutes for
a cold start (GPU node provisioning plus model load).

Two scaling caveats worth knowing:

- *Failed requests scale the pool.* Any failing `/v1/*` request — including
  bad API keys or wrong model names — counts toward wake and scale-up. On a
  `public` endpoint this means unauthenticated clients can wake and hold GPU
  replicas; prefer a restricted `Scope` when GPU cost matters.
- *Cold-start overshoot.* Replicas released while earlier ones are still
  loading the model count toward the pool, so continued failing/retrying
  traffic during a long cold start can provision more replicas than the load
  needs (they retire again once idle). Raise `ScaleUpCooldown` toward your
  model's cold-start time to limit this.

Note that when the backend list changes, LiteLLM is restarted to pick up the
new list; requests in flight *through the proxy* at that moment are dropped and
must be retried by the client. Requests already dispatched to a draining
replica are unaffected and run to completion within `DrainPeriod`.

On endpoint scopes other than `public`, the Fuzzball endpoint proxy consumes
the `Authorization` header (it carries your Fuzzball endpoint token), so pass
the LiteLLM API key in the `x-litellm-api-key` header instead:

```sh
curl -H "Authorization: Bearer ${FUZZBALL_ENDPOINT_TOKEN}" \
     -H "x-litellm-api-key: ${API_KEY}" \
     -H "Content-Type: application/json" \
     "${ENDPOINT_URL%/}/v1/chat/completions" \
     -d '{"model": "openai/gpt-oss-20b", "messages": [{"role": "user", "content": "hello"}]}'
```

On a `public` endpoint, pass the key as a standard OpenAI
`Authorization: Bearer` header.

With `Proxy=false` no LiteLLM service is started. Instead the replica pool
itself carries the endpoint: the pool URL stays stable for the life of the
workflow and each request is forwarded to a ready replica. The endpoint also
publishes one address per replica (`per-replica`), so an external gateway can
discover and balance across the replicas directly. The endpoints carry the
`ciq.com/api: openai` and `ciq.com/model` annotations, so the LiteLLM Model
Gateway catalog entry (`litellm`) picks the pool up automatically. An authenticated request to the pool endpoint while the pool
idles at zero starts the first replica and returns `503` with a `Retry-After`
header.

## Expert parallelism and multi-node serving

Mixture-of-experts models can serve with expert parallelism instead of tensor
parallelism, following the
[llm-d wide expert parallelism](https://llm-d.ai/docs/well-lit-paths/foundations/wide-expert-parallelism)
layout: attention runs data-parallel on every GPU of the replica and the expert
layers are split across those same GPUs. Whether a model is mixture-of-experts
is read from its `config.json` when the service starts. With the default
`ExpertParallelism=auto` a replica uses expert parallelism for a
mixture-of-experts model with at least two GPUs and tensor parallelism
otherwise; `true` insists on it and fails the service on other models; `false`
always uses tensor parallelism. Endpoints, the proxy, and autoscaling behave the
same either way. See [BENCHMARK.md](BENCHMARK.md) for how the two layouts are
compared (results pending).

vLLM's default all-to-all backend, `allgather_reducescatter`, is used; it works
across nodes. To select a DeepEP backend, use an image built with the DeepEP
kernels and pass `--all2all-backend <name>` through `ExtraArgs`.

Set `Nodes` above 1 to serve a mixture-of-experts model that does not fit on
one node. Each replica then spans that many nodes, which Fuzzball starts and
stops together; rank 0 serves the endpoint and coordinates the rest. A replica
has `Nodes` x `GpusPerNode` GPUs, and the pool grows and shrinks in whole
replicas. Every node needs `GpusPerNode` GPUs, and a cluster that cannot supply
`Nodes` nodes at once rejects the submission.

Before choosing `Nodes` above 1:

- If a node other than rank 0 dies after startup, the replica is not torn
  down; the endpoint keeps serving from rank 0 with part of the model missing.
- The replica's nodes must reach each other on arbitrary ports. Use `ExtraEnv`
  to point NCCL at a particular interface or otherwise tune it, e.g.
  `ExtraEnv=NCCL_SOCKET_IFNAME=eth0`.
- The GPUs must support GPU-to-GPU collectives. Virtualised GPUs generally do
  not: a vGPU profile such as `NVIDIA A16-2Q` fails at startup with `NCCL WARN
  Cuda failure 'operation not supported'`, right after NCCL reports the
  transport selected successfully. `NCCL_CUMEM_ENABLE=0`, `NCCL_P2P_DISABLE=1`
  and `NCCL_SHM_DISABLE=1` do not work around it; use passthrough or bare-metal
  GPUs. Single-node replicas are unaffected.
- Multi-node serving is untested on `Gpu: amd`.
- A multi-node group caps its prefill steps at 512 tokens
  (`--max-num-batched-tokens 512`, appended after `ExtraArgs`). On vLLM 0.28.0
  the group's data-parallel all-gather asserts as soon as one rank steps a
  larger batch, which any prompt of a few hundred tokens or more triggers;
  with the cap, prompts of 11k tokens and concurrent requests serve normally.
  Long prompts prefill in more steps than on a single node.

## Parameters

- `Model`: HuggingFace model to serve, as an `hf://` URI (e.g.
  `hf://openai/gpt-oss-20b`). Query parameters are passed through to the
  download: pin a revision with `?revision=<rev>`, and skip files the server
  does not read with `?exclude=<glob>` (repeatable). A pinned revision also
  keys the download directory, so revisions of one repository can share a
  persistent `Volume` without overwriting one another. The exclude form is worth
  setting for repositories that ship extra checkpoints alongside the weights —
  `hf://openai/gpt-oss-120b` is roughly three times larger downloaded whole
  than with `?exclude=original/**&exclude=metal/**`.
- `Gpu`: GPU platform, `nvidia` or `amd`.
- `ExpertParallelism`: `auto` (default), `true`, or `false`; see above.
- `Nodes`: nodes per replica, default 1. Above 1 needs a mixture-of-experts
  model, `ExpertParallelism` `auto` or `true`, and at least one GPU per node.
- `ExtraEnv`: extra environment variables for vLLM as space-separated
  `NAME=VALUE` pairs, set on every node of a replica. Values cannot contain
  spaces.
- `Proxy`: whether to front the pool with an in-workflow LiteLLM proxy.
- `Scope`: authorization scope of the service endpoint (`user`, `group`,
  `organization`, `public`). Note that a `public` pool endpoint is served
  without authentication and therefore never wakes a pool idling at zero.
- `MinReplicas` / `MaxReplicas`: replica pool bounds. `MinReplicas=0`
  enables scale-to-zero.
- `ApiKey`: OpenAI API key enforced by the LiteLLM proxy. Must start with
  `sk-`. Auto-generated when left empty — the generated key is visible in the
  started workflow's rendered definition (`fuzzball workflow describe`). Set an
  explicit strong key for `public` endpoints. Unused with `Proxy=false`, where
  access is governed by the endpoint scope instead.

Resource, image-version, scaling, and vLLM tuning knobs are available under
the Resources, Versions, Scaling, and Model Configuration categories. Under
Storage, set `Volume` to the name of a persistent volume (e.g.
`Volume=my-models`) to keep the downloaded model across workflow restarts.
On small or shared vGPU slices, lower `GpuMemoryUtilization` (e.g. to 0.8):
vLLM requires that fraction of *total* VRAM to be free at start, and driver
overhead on a small slice can make the 0.9 default unsatisfiable.

The workflow runs until it is cancelled. The rendered workflow also serves as a
working example of fronting an autoscaled service pool with an in-workflow
proxy; render it with `fuzzball workflow catalog render vLLM` to study or adapt
the pattern.
