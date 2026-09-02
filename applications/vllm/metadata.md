# Copyright 2026 CIQ, Inc. All rights reserved.
---
id: "ciq/ml_and_ai/vllm"
name: "vllm"
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
fuzzball workflow catalog start vllm --values Model=hf://openai/gpt-oss-20b
fuzzball workflow catalog start vllm --values Model=hf://openai/gpt-oss-120b,Gpu=amd
fuzzball workflow catalog start vllm --values Model=hf://openai/gpt-oss-120b,MinReplicas=1,MaxReplicas=10
fuzzball workflow catalog start vllm --values Model=hf://openai/gpt-oss-120b,GpusPerReplica=4
fuzzball workflow catalog start vllm --values Model=hf://openai/gpt-oss-20b,GpusPerReplica=2,ExpertParallelism=true
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

## Expert parallelism

For mixture-of-experts models the replica follows the
[llm-d wide expert parallelism](https://llm-d.ai/docs/well-lit-paths/foundations/wide-expert-parallelism)
layout on one node: attention runs data-parallel across the replica's GPUs and
the expert layers are sharded expert-parallel
(`--data-parallel-size GpusPerReplica --enable-expert-parallel`), instead of
tensor parallelism. Whether the model is MoE is detected at service start from
the downloaded model's `config.json`; with the default `ExpertParallelism=auto` the right
layout is picked automatically, and `ExpertParallelism=true` on a non-MoE model fails the
service at start with a message naming the model's architecture. The replica
still serves one OpenAI-compatible API on the same port, so endpoints, the
LiteLLM proxy, and autoscaling behave exactly as without expert parallelism.
Expert parallelism needs a data-parallel world of at least two, since a single
GPU has nothing to shard the experts across; below that the replica serves with
tensor parallelism instead. That world spans the whole replica, so it is
`Nodes` x `GpusPerReplica` -- two single-GPU nodes qualify just as one two-GPU
node does. See [BENCHMARK.md](BENCHMARK.md) for the methodology used to compare
expert- and tensor-parallel throughput (results pending).

Set `Nodes` above 1 for a mixture-of-experts model too large for any single
node. Each replica then becomes a gang-scheduled group: Fuzzball starts all of
its nodes together or none, gives them a private DNS namespace, and the group
serves one OpenAI-compatible endpoint from rank 0, which coordinates the others
internally. Attention runs data-parallel across every GPU of the group and the
experts are sharded over the same world, so the pool grows and shrinks in whole
groups rather than single nodes.

A group needs as many nodes as it has ranks, since two ranks of one replica are
never placed on the same node, and every node of the group needs
`GpusPerReplica` GPUs. Groups are gang-scheduled, so a pool whose provisioner
definition cannot supply `Nodes` nodes will not start a single replica; the
submission is rejected with the node cost named.

Three limits worth knowing before choosing `Nodes` above 1.

Ranks other than rank 0 do not report container state, so a peer rank dying
after startup raises no failure: the group is not torn down and the endpoint
keeps serving from rank 0 with part of the model missing.

The group's nodes must be able to reach each other on arbitrary ports — the
ranks negotiate data-parallel RPC and collective connections between themselves
— which is a property of the cluster's network rather than something this entry
can arrange. Where the collective library needs pointing at a particular
interface, or otherwise tuning, use `ExtraEnv`.

**The GPUs must support GPU-to-GPU collectives.** A group's ranks build an NCCL
communicator (RCCL on `amd`), and virtualised GPUs generally cannot: a `Q`-series
vGPU profile such as `NVIDIA A16-2Q` fails at startup with

    init.cc:416 NCCL WARN Cuda failure 'operation not supported'
    RuntimeError: NCCL error: unhandled cuda error

because the CUDA memory operations the collective library depends on are not
available to the guest. This is a property of the GPU profile, not of the
network: NCCL reports the transport selected successfully just before failing,
and `NCCL_CUMEM_ENABLE=0`, `NCCL_P2P_DISABLE=1` and `NCCL_SHM_DISABLE=1` do not
work around it. Multi-node serving needs passthrough or bare-metal GPUs. A
single-node replica is unaffected — it never builds a cross-rank communicator.

Multi-node groups are untested on `Gpu: amd`. The layout and every flag are
emitted identically there, but the ROCm image tracks a different vLLM release,
and the DeepEP `All2AllBackend` options are CUDA-only in practice.

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
- `ExpertParallelism`: `auto` (default; enabled when the downloaded model's
  `config.json` indicates a mixture-of-experts model and the replica's
  data-parallel world, `Nodes` x `GpusPerReplica`, is at least 2), `true`
  (require both — on a dense model the service fails at start naming the model's
  architecture, and a data-parallel world below 2 is rejected at submission), or
  `false` (tensor parallelism only).
- `Nodes`: nodes per replica, default 1. Above 1, each replica is a
  gang-scheduled group of that many nodes serving one endpoint from rank 0, for
  a mixture-of-experts model too large for a single node. Requires expert
  parallelism (`ExpertParallelism=false` is rejected) and at least one GPU per
  node; a dense model fails at start rather than serving a group that buys
  nothing.
- `ExtraEnv`: extra environment variables for the vLLM process, as
  space-separated `NAME=VALUE` pairs, applied to **every rank** of a replica.
  For settings with no command-line equivalent — chiefly collective-library
  tuning (`NCCL_*`, which RCCL also reads on `amd`) that a cluster's
  interconnect needs, e.g. `NCCL_SOCKET_IFNAME=eth0 NCCL_DEBUG=WARN`. Each entry
  is validated as `NAME=VALUE`, so values cannot contain spaces.
- `All2AllBackend`: vLLM's all-to-all backend for expert parallelism. Empty
  (default) leaves vLLM's own choice, `allgather_reducescatter`, which works
  with any layout including across nodes. `deepep_high_throughput` and
  `deepep_low_latency` are faster for multi-node serving —
  prefill-dominated and decode-dominated respectively — but need an image with
  the DeepEP kernels built in — which the default image is not — and a vLLM that
  accepts `--all2all-backend`. The default `v0.28.0` does; an older pinned image
  may not (`v0.10.1` does not). The flag is only passed when selected here, so
  leaving it empty keeps a group serving on any of them.
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
proxy; render it with `fuzzball workflow catalog render vllm` to study or adapt
the pattern.
