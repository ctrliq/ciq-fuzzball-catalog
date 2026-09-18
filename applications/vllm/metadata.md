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
the `Authorization` header (it carries your Fuzzball endpoint token) and signs
the caller's identity for the proxy, which admits the request on that alone --
no key is needed:

```sh
curl -H "Authorization: Bearer ${FUZZBALL_ENDPOINT_TOKEN}" \
     -H "Content-Type: application/json" \
     "${ENDPOINT_URL%/}/v1/chat/completions" \
     -d '{"model": "openai/gpt-oss-20b", "messages": [{"role": "user", "content": "hello"}]}'
```

A key is needed in two cases. On a `public` endpoint, where nothing is signed,
pass it as a standard OpenAI `Authorization: Bearer` header. On a cluster whose
nodes do not sign caller identity, the proxy falls back to its own key check;
pass the key in `x-litellm-api-key`, which the endpoint proxy leaves untouched.

With `Proxy=false` no LiteLLM service is started. Instead the replica pool
itself carries the endpoint: the pool URL stays stable for the life of the
workflow and each request is forwarded to a ready replica. The endpoint also
publishes one address per replica (`per-replica`), so an external gateway can
discover and balance across the replicas directly. The endpoints carry the
`ciq.com/api: openai` and `ciq.com/model` annotations, so the LiteLLM Model
Gateway catalog entry (`litellm`) picks the pool up automatically. An authenticated request to the pool endpoint while the pool
idles at zero starts the first replica and returns `503` with a `Retry-After`
header.

## Being discovered

Which annotation the endpoint carries follows from which mode it is in, and
decides who finds the pool without being given a URL.

`Proxy=true` annotates the proxy endpoint `ciq.com/api: openai-gateway`, the
same marker the `litellm` entry puts on its own endpoint. The `hermes-agent`
entry attaches to it directly, so a single pool and one agent need no gateway
workflow between them. A standalone `litellm` gateway does
not nest one proxy behind another: it registers only endpoints that also carry
`ciq.com/model`, and a proxy endpoint never does. Its `DiscoveryApiValue` knob
is a weaker guard -- it is set to `openai` by default, but it is user-settable.

`Proxy=false` annotates the per-replica endpoints `ciq.com/api: openai` plus
`ciq.com/model`, which is what a `litellm` gateway registers. Agents do not
attach to these; reach them through the gateway. A gateway another identity
runs only sees them if `Scope` is widened to reach it -- at the `user` default
a pool published for someone else's gateway is never registered, and nothing
reports why.

Discovery only considers endpoints the caller's identity can reach, and `Scope`
defaults to `user` so a pool does not appear in a colleague's candidate set.
Widen it deliberately. What an agent does with several visible gateways is the
agent's choice, and `hermes-agent` refuses to guess -- so with several pools
running at once, name the endpoint on the agent. Narrowing `Scope` does not
help: `user` is already the narrowest, and two pools you started yourself
collide inside it.

At `Proxy=true`, `Scope=public` carries no `ciq.com/api` annotation, so a public
proxied pool is not discovered. The listing surfaces a public endpoint to every
member of the organization, and an agent that found one would then fail minting
the token a public endpoint does not need. This does not extend to `Proxy=false`:
the per-replica endpoints carry their annotations at every scope, so a public
pool is still registered by any gateway in the organization -- and that gateway
then cannot mint for it either. Do not publish a pool for a gateway at `public`.

Discovery finds the URL, and on a cluster that signs caller identity that is all
an agent needs: the proxy admits it on the identity the endpoint forwards, so
nothing has to be paired between the two workflows. Where a key does apply -- a
`public` endpoint, or a cluster without caller identity -- the clean way to pair
the two is one Fuzzball secret named on both sides: set this entry's
`ApiKeySecret` to it, and set the agent's own `ApiKeySecret` (`opencode` and
`hermes-agent` each have a value by that name) to the same reference. Neither
workflow definition then carries the key.

Set plainly instead, or left to generate, the key is written into the rendered
workflow definition -- so re-rendering produces a different key, and anyone who
can read the workflow can read it. It is not a secret from them, only from
something that discovered the endpoint alone.

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

Set `Nodes` above 1 to serve a model that does not fit on one node. Each
replica then spans that many nodes, which Fuzzball starts and stops together;
rank 0 serves the endpoint and coordinates the rest. A mixture-of-experts model
with `ExpertParallelism` `auto` or `true` runs expert-parallel across the
group's GPUs; any other model, or `ExpertParallelism=false`, runs
tensor-parallel across them. A replica has `Nodes` x `GpusPerNode` GPUs, the
pool grows and shrinks in whole replicas, every node needs `GpusPerNode` GPUs,
and a cluster that cannot supply `Nodes` nodes at once rejects the submission.

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
- An expert-parallel group caps its prefill steps at 512 tokens
  (`--max-num-batched-tokens 512`, appended after `ExtraArgs`). On vLLM 0.28.0
  the group's data-parallel all-gather asserts as soon as one rank steps a
  larger batch, which any prompt of a few hundred tokens or more triggers;
  with the cap, prompts of 11k tokens and concurrent requests serve normally.
  Long prompts prefill in more steps than on a single node. Tensor-parallel
  groups are not affected and carry no cap.

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
- `Nodes`: nodes per replica, default 1. Above 1 needs at least one GPU per
  node; the layout follows `ExpertParallelism`.
- `ExtraEnv`: extra environment variables for vLLM as space-separated
  `NAME=VALUE` pairs, set on every node of a replica. Values cannot contain
  spaces.
- `Proxy`: whether to front the pool with an in-workflow LiteLLM proxy.
- `Scope`: authorization scope of the service endpoint (`user`, `group`,
  `organization`, `public`), defaulting to `user`. It also bounds who discovers
  the pool, and at `Proxy=true` `public` opts the proxy endpoint out of
  discovery. Note that a `public` pool endpoint is served without authentication
  and therefore never wakes a pool idling at zero.
- `MinReplicas` / `MaxReplicas`: replica pool bounds. `MinReplicas=0`
  enables scale-to-zero.
- `ApiKeySecret`: a Fuzzball secret holding the key the LiteLLM proxy enforces,
  as `secret://user/<name>`. Needed only on a `public` endpoint, or on a cluster
  that does not sign caller identity; otherwise the endpoint identifies the
  caller and the proxy asks for no key. The definition carries the reference, not
  the key, and Fuzzball resolves it at run time. Preferred over `ApiKey`. Unused
  with `Proxy=false`.
- `ApiKey`: the same key in plain text. Must start with `sk-`. `ApiKeySecret`
  wins if both are set; with neither, a key is generated at every workflow
  start. A literal or generated key is stored in the started workflow's definition,
  where anyone who can `fuzzball workflow get` the workflow can read it. Unused
  with `Proxy=false`, where access is governed by the endpoint scope instead.

Both are unset by default, so a pool started without either generates a key the
proxy will also accept, which the request example above does not need. Read it
back with `fuzzball workflow get <workflow>` and look for `LITELLM_MASTER_KEY` on
the `litellm` service. It is fixed for the life of the workflow, and a different
one is generated the next time the entry is started.

On a `public` endpoint this key is the only thing standing in front of the
model — set a strong one deliberately rather than relying on the generated
default. To keep one key across workflow starts and out of the definition,
create a user-scoped secret of type `value` and name it in `ApiKeySecret`:

```sh
printf 'sk-...' | fuzzball secret create secret://user/vllm-proxy-key --type value
fuzzball workflow catalog start vLLM --values ApiKeySecret=secret://user/vllm-proxy-key
```

The secret's content must itself start with `sk-`; the proxy exits at start
with a message naming `ApiKeySecret` if it does not. Naming a secret keeps the
key out of the definition but not out of the running container — its owner can
still read it there.

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
