# Copyright 2026 CIQ, Inc. All rights reserved.
---
id: "ciq/ml_and_ai/litellm_gateway"
name: "LiteLLM Model Gateway"
category: "ML_AND_AI"
tags:
- LLM
- gateway
- OpenAI
- inference
- genAI
---
One OpenAI-compatible base URL in front of every model-serving workflow your identity can
reach. Agents and IDE plugins ask for a model by name; which workflow serves it, and how
many replicas it has, stays invisible to them.

The gateway configures itself. It polls the Fuzzball endpoints API, keeps the endpoints
annotated `ciq.com/api: openai`, and registers one LiteLLM deployment per live replica --
so a pool scaling up or down is reflected without anyone touching the gateway. A request
for a model whose pool has scaled to zero wakes it and succeeds on retry.

This entry is a reference implementation: the reconcile loop is deliberately plain
Python, meant to be copied as the starting point for your own gateway.

## Using it

Create a virtual key against the gateway, then point any OpenAI client at the endpoint
URL. Callers send two credentials: the Fuzzball endpoint token in `Authorization`, and the
LiteLLM virtual key in `x-litellm-api-key`.

```sh
curl -H "Authorization: Bearer ${FUZZBALL_ENDPOINT_TOKEN}" \
     -H "x-litellm-api-key: ${VIRTUAL_KEY}" \
     -H "Content-Type: application/json" \
     "${GATEWAY_URL}v1/chat/completions" \
     -d '{"model": "<alias>", "messages": [{"role": "user", "content": "hello"}]}'
```

`GET /v1/models` lists whatever the gateway has discovered.

## Publishing a model to it

Any workflow can advertise itself by annotating a service endpoint. The gateway reads two
keys and ignores every endpoint that does not carry them, including its own:

```yaml
annotations:
  ciq.com/api: openai
  ciq.com/model: llama-3.3-70b
```

`ciq.com/model` is the name callers ask for, and it must match the name the server serves
under (for vLLM, `--served-model-name`). Set `per-replica: true` on the endpoint to let the
gateway balance across replicas itself, and a `scale-down.drain-period` comfortably above
the gateway's refresh interval so a retiring replica leaves the rotation before it stops.

Do not set an API key on the served model. Fuzzball's proxy consumes the `Authorization`
header on a non-public endpoint, so the model server never sees one -- the endpoint's own
scope is the access control.

## Things to know before you start it

- **The database is pinned to the LiteLLM version.** A different LiteLLM release reading
  another release's schema accepts writes and then never routes the model. Changing
  `litellm-version` means starting with a fresh database.
- **The default volume is ephemeral**, so virtual keys, budgets and spend history are lost
  when the workflow stops. Point `data-volume` at a persistent volume for anything you rely
  on.
- **`cluster-ca-secret` is effectively required on a cluster whose API is served with a
  private CA.** Without it discovery never reaches the Fuzzball API: the gateway serves no
  models at all and only logs `DISCOVERY-FAILED` SSL errors, while the workflow itself looks
  healthy.
- **A pool that scales to zero surfaces LiteLLM's router cooldown to callers.** Such a
  model has a single LiteLLM deployment, so each drain produces a short burst of 429
  "No deployments available" responses until the next discovery pass swaps the route.
  Clients should retry on 429; `cooldown_time` and `allowed_fails` in
  `router_settings` are the tuning knobs if the bursts matter.
- **Generation length is bounded by the cluster's endpoint ingress timeout.** A response
  that produces nothing for longer than that window is cut off. Ask your cluster
  administrator what it is set to.
- The master key must live in a **user-scoped** secret (`secret://user/...`).
