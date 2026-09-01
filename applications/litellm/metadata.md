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
- ai
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

Every call to the gateway carries two credentials: a Fuzzball token in `Authorization`
(the endpoint's scope is the access control), and a LiteLLM key in `x-litellm-api-key`.

1. Get the gateway URL:

   ```sh
   fuzzball workflow endpoints list
   ```

2. Get the master key. It is generated at submit time; read it with
   `fuzzball workflow log <workflow> show-gateway`, or from the workflow definition via
   `fuzzball workflow get <workflow>`.

3. Get a Fuzzball token: your own user token works, or mint one bound to the gateway's
   endpoint with `fuzzball workflow endpoints generate-token <endpoint id>`.

4. Mint a virtual key for each caller, so the master key never leaves the operator:

   ```sh
   curl -X POST \
        -H "Authorization: Bearer ${FUZZBALL_TOKEN}" \
        -H "x-litellm-api-key: ${MASTER_KEY}" \
        -H "Content-Type: application/json" \
        "${GATEWAY_URL}/key/generate" -d '{"models": []}'
   ```

5. Point any OpenAI client at the gateway with the virtual key:

   ```sh
   curl -H "Authorization: Bearer ${FUZZBALL_TOKEN}" \
        -H "x-litellm-api-key: ${VIRTUAL_KEY}" \
        -H "Content-Type: application/json" \
        "${GATEWAY_URL}/v1/chat/completions" \
        -d '{"model": "<alias>", "messages": [{"role": "user", "content": "hello"}]}'
   ```

`GET /v1/models` (same two credentials) lists whatever the gateway has discovered.

## Publishing a model to it

Any workflow can advertise itself by annotating a service endpoint. The gateway reads two
keys and ignores every endpoint that does not carry them, including its own:

```yaml
annotations:
  ciq.com/api: openai
  ciq.com/model: llama-3.3-70b
```

`ciq.com/model` is the name callers ask for, and it must match the name the server serves
under (for vLLM, `--served-model-name`). The endpoint must not be `public`: the gateway
authenticates to models with minted endpoint tokens, and tokens cannot be minted for
public endpoints. Set `per-replica: true` (which requires `type: subdomain` and an
autoscaler on the service) to let the gateway balance across replicas itself, and an
`autoscaler.scale-down.drain-period` comfortably above the gateway's refresh interval
(`RefreshInterval`, default 25s) so a retiring replica leaves the rotation before it
stops.

Do not set an API key on the served model. Fuzzball's proxy consumes the `Authorization`
header on a non-public endpoint, so the model server never sees one -- the endpoint's own
scope is the access control. A model server in the same workflow as the gateway is always
skipped: the gateway only serves other workflows' endpoints.

To confirm a model was picked up, watch `fuzzball workflow log <workflow> gateway` for a
`REGISTERED` line on the next discovery pass, or list `/v1/models`.

## Things to know before you start it

- **The database is pinned to the LiteLLM version.** A different LiteLLM release reading
  another release's schema accepts writes and then never routes the model. Changing
  `LiteLLMVersion` means starting with a fresh database.
- **The default volume is ephemeral**, so virtual keys, budgets and spend history are lost
  when the workflow stops. Point `DataVolume` at a persistent volume for anything you rely
  on.
- **`ClusterCASecret` is effectively required on a cluster whose API is served with a
  private CA.** Without it discovery never reaches the Fuzzball API: the gateway serves no
  models at all and only logs `DISCOVERY-FAILED` SSL errors, while the workflow itself looks
  healthy.
- **A pool that scales to zero surfaces LiteLLM's router cooldown to callers.** Such a
  model has a single LiteLLM deployment, so each drain produces a short burst of 429
  "No deployments available" responses until the next discovery pass swaps the route.
  Clients should retry on 429. Tuning the router's cooldown means adding a LiteLLM config
  file to a copy of this entry; it is not exposed as a value.
- **Generation length is bounded by the endpoint proxy's 10-minute idle timeout.** A
  response that produces nothing for longer than that window is cut off.
- **Callers borrow the owner's reach.** The gateway discovers and authenticates to models
  as the identity that started it, so the gateway's endpoint scope (`ServiceScope`)
  decides who can use every model it serves -- regardless of the callers' own grants.
- **Anyone who can read the workflow can read the master key.** It is generated fresh on
  every workflow start and embedded in the workflow definition. Hand callers virtual keys,
  never the master key.
