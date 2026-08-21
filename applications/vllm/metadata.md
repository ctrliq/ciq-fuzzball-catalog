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
fuzzball workflow catalog start vllm --values model=hf://openai/gpt-oss-20b
fuzzball workflow catalog start vllm --values model=hf://openai/gpt-oss-120b,gpu=amd
fuzzball workflow catalog start vllm --values model=hf://openai/gpt-oss-120b,min-replicas=1,max-replicas=10
```

The model is downloaded from the HuggingFace Hub once, at workflow start, into
the workflow's volume (data ingress). Replicas serve fully offline from that
local copy — no Hub access or token is needed at serve time. For gated or
private models, set `hf-token-secret` to a Fuzzball secret holding your
HuggingFace token; it is used only during ingress.

## Front end

By default (`proxy=true`) a [LiteLLM](https://docs.litellm.ai/) proxy holds the
workflow's service endpoint and load-balances across the currently-ready vLLM
replicas. Its backend list is kept up to date automatically as the pool scales
(Fuzzball dynamic configuration). LiteLLM's own request metrics drive pool
scale-up: failed requests wake an idle or saturated pool — including starting
the first replica when the pool is at zero — and a request rate at or above
`scale-up-requests-per-minute` adds replicas under load. A request that arrives
while no replica is running fails fast and triggers scale-up; keep retrying at
normal client intervals — the retries themselves sustain the wake signal — and
the request succeeds once a replica is up, which can take several minutes for
a cold start (GPU node provisioning plus model load).

Two scaling caveats worth knowing:

- *Failed requests scale the pool.* Any failing `/v1/*` request — including
  bad API keys or wrong model names — counts toward wake and scale-up. On a
  `public` endpoint this means unauthenticated clients can wake and hold GPU
  replicas; prefer a restricted `scope` when GPU cost matters.
- *Cold-start overshoot.* Replicas released while earlier ones are still
  loading the model count toward the pool, so continued failing/retrying
  traffic during a long cold start can provision more replicas than the load
  needs (they retire again once idle). Raise `scale-up-cooldown` toward your
  model's cold-start time to limit this.

Note that when the backend list changes, LiteLLM is restarted to pick up the
new list; requests in flight *through the proxy* at that moment are dropped and
must be retried by the client. Requests already dispatched to a draining
replica are unaffected and run to completion within `drain-period`.

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

With `proxy=false` no LiteLLM service is started. Instead the replica pool
itself carries the endpoint: the pool URL stays stable for the life of the
workflow and each request is forwarded to a ready replica. The endpoint also
publishes one address per replica (`per-replica`), so an external gateway can
discover and balance across the replicas directly. The endpoints carry the
`ciq.com/api: openai` and `ciq.com/model` annotations, so the LiteLLM Model
Gateway catalog entry (`litellm`) picks the pool up automatically. An authenticated request to the pool endpoint while the pool
idles at zero starts the first replica and returns `503` with a `Retry-After`
header.

## Parameters

- `model`: HuggingFace model to serve, as an `hf://` URI (e.g.
  `hf://openai/gpt-oss-20b`).
- `gpu`: GPU platform, `nvidia` or `amd`.
- `proxy`: whether to front the pool with an in-workflow LiteLLM proxy.
- `scope`: authorization scope of the service endpoint (`user`, `group`,
  `organization`, `public`). Note that a `public` pool endpoint is served
  without authentication and therefore never wakes a pool idling at zero.
- `min-replicas` / `max-replicas`: replica pool bounds. `min-replicas=0`
  enables scale-to-zero.
- `api-key`: OpenAI API key enforced by the LiteLLM proxy. Must start with
  `sk-`. Auto-generated when left empty — the generated key is visible in the
  started workflow's rendered definition (`fuzzball workflow describe`). Set an
  explicit strong key for `public` endpoints. Unused with `proxy=false`, where
  access is governed by the endpoint scope instead.

Resource, image-version, scaling, and vLLM tuning knobs are available under
the Resources, Versions, Scaling, and Model Configuration categories. Under
Storage, point `volume` at a persistent volume to keep the downloaded model
across workflow restarts instead of re-downloading it each start.

The workflow runs until it is cancelled. The rendered workflow also serves as a
working example of fronting an autoscaled service pool with an in-workflow
proxy; render it with `fuzzball workflow catalog render vllm` to study or adapt
the pattern.
