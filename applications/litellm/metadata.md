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

A caller on this cluster needs no key. The endpoint signs the caller's Fuzzball
identity, the gateway authenticates it, and access is the endpoint's scope -- the same
control that governs every other Fuzzball endpoint. Spend is recorded against the
Fuzzball user who made the call.

1. Get the gateway URL:

   ```sh
   fuzzball workflow endpoints list
   ```

2. Get a Fuzzball token: your own user token works, or mint one bound to the gateway's
   endpoint with `fuzzball workflow endpoints generate-token <endpoint id>`.

3. Point any OpenAI client at the gateway:

   ```sh
   curl -H "Authorization: Bearer ${FUZZBALL_TOKEN}" \
        -H "Content-Type: application/json" \
        "${GATEWAY_URL}/v1/chat/completions" \
        -d '{"model": "<alias>", "messages": [{"role": "user", "content": "hello"}]}'
   ```

`GET /v1/models` (same credential) lists whatever the gateway has discovered.

The gateway's own endpoint is annotated `ciq.com/api: openai-gateway`, so a client
can find it without being told a URL -- that is how the `hermes-agent` entry attaches
itself. The value deliberately differs from the one the gateway discovers models on,
so a second gateway does not mistake this one for a model server.

### Where a key is still needed

Two cases. A `public` endpoint authenticates nothing and forwards no identity, so the
key is the only barrier and travels as a standard `Authorization: Bearer`. And on a
cluster whose nodes do not sign caller identity, the gateway falls back to its own key
check; the call then carries two credentials, a Fuzzball token in `Authorization` and a
LiteLLM key in `x-litellm-api-key`, which the endpoint proxy leaves untouched.

The master key is generated at submit time; read it with
`fuzzball workflow log <workflow> show-gateway`, or from the workflow definition via
`fuzzball workflow get <workflow>`. To use your own instead, store it in a user-scoped
secret of type `value` and name that secret in `MasterKeySecret`. The key then stays out
of the workflow definition, so someone who can read the workflow no longer sees it (its
owner can still read it from the running container), and it stays the same across
workflow starts:

```sh
printf 'sk-...' | fuzzball secret create secret://user/gateway-master-key --type value
fuzzball workflow catalog start "LiteLLM Model Gateway" \
     --values MasterKeySecret=secret://user/gateway-master-key
```

Mint a virtual key for each caller, so the master key never leaves the operator:

```sh
curl -X POST \
     -H "Authorization: Bearer ${FUZZBALL_TOKEN}" \
     -H "x-litellm-api-key: ${MASTER_KEY}" \
     -H "Content-Type: application/json" \
     "${GATEWAY_URL}/key/generate" -d '{"models": []}'
```

then send `x-litellm-api-key: ${VIRTUAL_KEY}` alongside the Fuzzball token.

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
  when the workflow stops. Set `Volume` to the name of a persistent volume for anything you
  rely on. A persistent volume brings its own constraints -- see below.
- **The cluster CA comes from the node trust store.** Fuzzball mounts its CA into every
  workflow container at `/run/fuzzball-substrate/trusted-certs/root-ca.crt` and the gateway
  appends it to its bundle, so a private-CA cluster needs no configuration. Nodes must run
  the orchestrate extension that publishes it (v4.2.0-58 or newer); on older nodes the
  gateway logs a warning at start, discovery never reaches the Fuzzball API, and it serves
  no models while the workflow itself looks healthy.
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
  It defaults to `user`, so a gateway meant to be shared has to be widened on purpose.
  `group` is not "my team": it binds to whichever group the submitter had selected, frozen
  at creation. Pick the reach you actually want, usually `organization`.
- **A generated master key is readable by anyone who can read the workflow.** Without
  `MasterKeySecret` it is generated once, when the template is rendered, and embedded in
  the rendered workflow definition. Set `MasterKeySecret` to keep the key out of the
  definition, and hand callers virtual keys, never the master key.

### On a persistent volume

None of these apply while `Volume` is `ephemeral`.

- **The volume name is resolved across the organization.** Fuzzball searches every
  provisioner you can reach for a volume of that name and binds the single match. `Volume`
  cannot pin a provisioner, which the `volume://<scope>/<provisioner>/<name>` form this
  entry used to take could: give the volume a name that is unique across provisioners.
  Two matches fail the submit, and the error's advice to specify a provisioner with `use:`
  is not something this entry can express.
- **Give it an empty volume you created yourself.** Fuzzball never changes a volume's
  ownership when it mounts one, and new volumes are created 0750, so a volume created by
  another user or imported with `fuzzball volume provisioner scan` leaves the data
  directory unwritable. That surfaces as `FATAL: postgres exited before the password was
  reset`, which mentions neither permissions nor the volume.
- **The PostgreSQL major version comes from the data directory, not `PostgresVersion`.** A
  reused volume carries the cluster `initdb` wrote, so raising `PostgresVersion` across a
  major boundary makes the image refuse the directory and produce that same FATAL. Dump and
  restore, or point `Volume` at a new volume. The same goes for a `LiteLLMVersion` change:
  starting with a fresh database is automatic only while the volume is ephemeral.
- **`POSTGRES_INITDB_ARGS` applies only to an empty volume.** A data directory initialized
  anywhere else brings its own `pg_hba.conf`, and with `network: host: true` `initdb`'s
  default `trust` on 127.0.0.1 lets any process on the node connect as superuser. Only a
  data directory this entry initialized is known to close that.
- **Run one gateway per volume.** Nothing stops a second workflow from mounting the same
  volume. Its password reset succeeds and rewrites the shared role's password, so the first
  workflow's `DATABASE_URL` stops working while both keep looking healthy.
