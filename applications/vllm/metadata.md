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
fuzzball workflow catalog start vllm --values Model=hf://openai/gpt-oss-20b,GpusPerReplica=2,Ep=true
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
the downloaded model's `config.json`; with the default `Ep=auto` the right
layout is picked automatically, and `Ep=true` on a non-MoE model fails the
service at start with a message naming the model's architecture. The replica
still serves one OpenAI-compatible API on the same port, so endpoints, the
LiteLLM proxy, and autoscaling behave exactly as without expert parallelism.
Multi-node expert-parallel serving groups are future work (FUZZ-8399 Phase 2).
See [BENCHMARK.md](BENCHMARK.md) for the EP-versus-TP throughput comparison.

## Parameters

- `Model`: HuggingFace model to serve, as an `hf://` URI (e.g.
  `hf://openai/gpt-oss-20b`).
- `Gpu`: GPU platform, `nvidia` or `amd`.
- `Ep`: expert parallelism — `auto` (default; enabled when the downloaded
  model's `config.json` indicates a mixture-of-experts model), `true` (require
  a MoE model; on a dense model the service fails at start naming the model's
  architecture), or `false` (tensor parallelism only).
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

The workflow runs until it is cancelled. The rendered workflow also serves as a
working example of fronting an autoscaled service pool with an in-workflow
proxy; render it with `fuzzball workflow catalog render vllm` to study or adapt
the pattern.
