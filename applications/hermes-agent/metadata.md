# Copyright 2026 CIQ, Inc. All rights reserved.
---
id: "ciq/ml_and_ai/hermes-agent"
name: "Hermes Agent"
category: "ML_AND_AI"
tags:
- agent
- LLM
- OpenAI API
- genAI
---
This workflow runs [Hermes Agent](https://hermes-agent.nousresearch.com), a
general-purpose agent with persistent memory, as a Fuzzball service already
wired to a model served on the cluster. It finds its own model: on startup it
lists the Fuzzball endpoints its identity can reach, takes the one a LiteLLM
gateway has annotated as such, mints its own credential for it, and writes the
provider into the agent's configuration. Nothing has to be copied between
workflows.

```
fuzzball workflow catalog start hermes-agent --values ApiKeySecret=secret://user/litellm-key
fuzzball workflow catalog start hermes-agent --values ApiKeySecret=secret://user/litellm-key,Volume=my-hermes
fuzzball workflow catalog start hermes-agent --values ApiKeySecret=secret://user/litellm-key,Endpoint=https://<endpoint-url>,Model=openai/gpt-oss-20b
```

The one thing you must supply is the gateway's LiteLLM key. Mint a virtual key
from the gateway rather than handing this workflow the master key:

```sh
curl -X POST \
     -H "Authorization: Bearer ${FUZZBALL_TOKEN}" \
     -H "x-litellm-api-key: ${MASTER_KEY}" \
     -H "Content-Type: application/json" \
     "${GATEWAY_URL}/key/generate" -d '{"models": []}'
```

then store it as a user-scoped Fuzzball secret and pass the reference as
`ApiKeySecret` (`secret://user/<name>`).

## Attaching to the gateway

Every call to a LiteLLM gateway on Fuzzball carries two credentials, because
the Fuzzball endpoint proxy consumes the `Authorization` header on any endpoint
whose scope is not public: a Fuzzball credential in `Authorization`, and the
gateway's own LiteLLM key in `x-litellm-api-key`, which the proxy leaves
untouched. The agent supplies the first itself and takes the second from
`ApiKeySecret`.

With `Endpoint` left empty -- the default -- the gateway is discovered rather
than configured. The agent lists `/v4/endpoints` with its own injected identity
and takes the endpoint annotated `ciq.com/api: openai-gateway`, which is what
the `litellm` entry marks its endpoint with. Discovery fails loudly, and the
service stops, when no gateway is visible or when more than one is: at that
point set `Endpoint` to choose. `Model` works the same way -- left empty, the
agent adopts whatever the gateway is serving when it starts.

Attachment then repeats every `AttachInterval` seconds, which is what makes the
credential durable. The server grants an endpoint token no more lifetime than
the calling workflow token has left, so a token minted once at startup would
put a ceiling on how long the agent works. Instead the agent renews its own
workflow token in the background and re-mints the endpoint token at half its
granted lifetime. Credentials are the half that refreshes live: the provider
reads its key through `key_cmd`, so Hermes picks up each new token on its own
without restarting. A gateway that moves to a new URL is written into
`config.yaml` by the same pass, but reaches only sessions started after it: a
conversation already in flight keeps the provider it was created with.

A pass logs `ATTACHED` with the gateway and model it settled on; a pass that
fails logs `ATTACH-FAILED` and changes nothing, so the agent keeps working on
the last good configuration until the credential it holds actually lapses.
The first pass is different: it runs before Hermes starts and stops the service
if it cannot attach, rather than leaving an agent that answers the dashboard and
then errors on every prompt.

Set `EndpointAuth=api-key` to point the agent at an OpenAI-compatible API that
is not a Fuzzball endpoint. `Endpoint` is then required, the key is sent as the
bearer token, and nothing is discovered or minted.

Only the provider entry named `fuzzball` in `config.yaml` is managed this way.
Everything else in that file is yours in value, though not in form: the agent
rewrites the one entry and preserves the rest, but it round-trips the file
through a YAML parser, so comments and hand-formatting do not survive. It sets
the active model on the first attach and then leaves it alone, so a model you
select from the dashboard stays selected.

The gateway key is written into that file, which means a persistent `Volume`
keeps it after the workflow ends, and the agent can read it like any other file
it has shell access to. `ApiKeySecret` keeps the key out of the *rendered
definition*, which is a narrower promise than keeping it off disk.

## Reaching the agent

The service publishes the web dashboard, and -- with `ExposeApiServer`, the
default -- the agent's own OpenAI-compatible API on a second endpoint. Point an
OpenAI client at that one to drive the agent as though it were a model, or set
Hermes Desktop's Gateway URL to the dashboard endpoint to use the agent from
the desktop application.

Two layers of authentication apply and neither is redundant:

- The endpoint scope. At `user`, `group`, or `organization`, requests through
  an endpoint URL need a Fuzzball credential: an [endpoint access
  token](https://ui.stable.fuzzball.ciq.dev/docs/advanced-features/workflow-endpoints/)
  for API clients, or a browser session for the dashboard.
- The agent's own credentials -- a dashboard password and an API key, both
  generated at submit time and printed by the `show-agent` job. A plain service
  binds its port on the node it runs on, so the endpoint proxy is not the only
  way in and the scope alone protects nothing. That is also why turning
  `ExposeApiServer` off is not a way to switch the API off: it removes the
  endpoint, not the listener, and the key remains what protects it.

`public` is deliberately not offered as a scope. Hermes refuses to serve an
unauthenticated dashboard on a non-loopback bind at all, and internet-reachable
agent dashboards and API servers were the entry point for the June 2026
campaign that drove exposed agents into planting SSH-key backdoors. Anyone who
reaches this agent can run shell commands in its container, read everything it
remembers, and spend model capacity, so prefer the narrowest scope that fits.

Because the two credentials travel in two different headers, a client outside
the cluster can present both -- which is what makes the workstation setup below
work. That is not true of the agent's own endpoints: a browser can hold a
Fuzzball session for the dashboard, but a non-browser client outside the
cluster cannot put a Fuzzball token in `Authorization` and its own key there as
well.

## Using a Fuzzball model from Hermes on your workstation

You do not need this entry to use cluster models from Hermes. A Hermes running
on your own machine attaches to the same gateway with the same two credentials,
configured by hand.

Get the gateway URL from `fuzzball workflow endpoints list` and mint a virtual
key as above, then add a named provider to `~/.hermes/config.yaml`:

```yaml
providers:
  fuzzball:
    api: https://endpoint-<id>.endpoints.<cluster domain>/v1
    transport: chat_completions
    key_cmd: "~/.hermes/bin/fuzzball-endpoint-token"
    extra_headers:
      x-litellm-api-key: sk-<your litellm virtual key>
    discover_models: true
    context_length: 32768

model:
  provider: custom:fuzzball
  default: <model as the gateway serves it>
```

`key_cmd` names a command that prints a credential, which Hermes re-runs when
the one it holds is close to expiring. That matters here because Fuzzball
endpoint tokens are short-lived -- the CLI grants an hour by default -- so a
token pasted into `.env` starts returning 401 mid-session.

The CLI prints YAML, not a bare token:

```
token: eyJhbGciOi...
expires_at: "2026-08-31T15:41:24Z"
url: https://endpoint-<id>.endpoints.<cluster domain>/
```

Hermes accepts either a bare token or single-line JSON with an `access_token`
field, and it honours an absolute `expiry`, so hand it both and it re-mints
exactly when the token dies rather than guessing:

```sh
#!/bin/sh
# ~/.hermes/bin/fuzzball-endpoint-token
set -e
fuzzball workflow endpoints generate-token "<endpoint id>" | awk '
  /^token:/      { t = $2 }
  /^expires_at:/ { e = $2; gsub(/"/, "", e) }
  END            { printf "{\"access_token\":\"%s\",\"expiry\":\"%s\"}\n", t, e }'
```

Multi-line output is rejected rather than guessed at, which is why the token
cannot simply be piped through unchanged.

Two further notes for a workstation:

- On a cluster whose API is served with a private CA, add `ssl_ca_cert:` to the
  provider entry, pointing at a PEM file holding that CA. Without it every
  request fails TLS verification.
- Confirm the pair of credentials before involving Hermes at all:

  ```sh
  curl -H "Authorization: Bearer <fuzzball endpoint token>" \
       -H "x-litellm-api-key: <litellm virtual key>" \
       "https://<gateway>/v1/models"
  ```

  A 401 from that means the credential is wrong; an empty model list means the
  gateway has not discovered a model server yet, which is a problem on the
  cluster rather than on your machine.

Switch between the cluster and anything else you have configured with
`/model custom:fuzzball:<model>` inside a session.

## Things to know before you start it

- **A gateway that serves no models yet stops the agent.** Discovery reads
  `/v1/models`, and a gateway whose model pools have not started serves an
  empty list, which is indistinguishable from a misconfigured gateway. Start
  the model workflow first, or set `Model` explicitly to skip the check.
- **A gateway restart can invalidate the key you gave this workflow.** The
  `litellm` entry keeps its virtual keys in its database, which is on an
  ephemeral volume by default, so restarting the gateway destroys them. The agent
  will rediscover the new gateway and mint a fresh Fuzzball token for it, then
  fail authentication with the dead LiteLLM key. Point the gateway's `DataVolume`
  at a persistent volume, or expect to mint a new key and restart the agent.
- **Generation length is bounded by the endpoint proxy's 10-minute idle
  timeout.** A response that produces nothing for longer than that window is
  cut off, which a long agentic turn on a slow model can reach.
- **Only OpenAI-style chat completions.** The provider is written with
  `transport: chat_completions`, so the target must speak
  `POST <Endpoint>/v1/chat/completions`. Hermes can also speak the Anthropic
  Messages protocol, but this entry does not expose that choice. Anthropic's own
  API works because it publishes an OpenAI-compatible layer at that path; a
  Messages-only proxy would not.
- **`MaxContextSize` is not discovered.** Hermes compresses its context against
  whatever this says, so a value above what the model serves produces requests
  the model rejects. Match it to the serving entry.
- **The agent borrows the owner's reach.** It discovers and authenticates to the
  gateway as the identity that started it, so its endpoint scope decides who can
  use it, regardless of the callers' own grants.
- **Anyone who can read the workflow can read both credentials.** The dashboard
  password and API key are generated fresh on every start and embedded in the
  workflow definition.
- **The entry does not use the image's entrypoint.** The published image is
  built for Docker, where it starts as root and drops to its own baked user. Its
  entrypoint and wrapper both refuse to start under any other uid, and Fuzzball
  supplies exactly that -- the same reason the `litellm` and `opencode` entries
  redirect `HOME` and every cache onto their volumes. So this entry seeds the
  state tree itself and execs the `hermes` CLI directly, skipping the container
  bootstrap. What that bootstrap does beyond refusing is set up s6 supervision
  and repair file ownership after a privilege drop, and neither is needed when a
  single uid owns the whole run. The consequence to know about: the image's
  supervised services do not exist here, so the dashboard is started and
  restarted by this entry rather than by s6, and an upstream change to the
  image's startup could need mirroring here.
- **Private-CA clusters.** Reaching the Fuzzball API and the gateway over TLS
  relies on the node trust store Fuzzball bind-mounts into workflow containers,
  so this entry needs a cluster new enough to provide it. The entry merges that
  mount with the image's public roots rather than replacing them, because the
  agent's own tools -- web search, document fetch -- still reach public TLS.

## Storage

`Volume` defaults to `ephemeral`, which destroys the agent's configuration,
sessions, memories, and any skills it has learned when the workflow stops. An
agent whose whole premise is that it improves over time wants a persistent
volume named here instead. It is mounted at `/opt/data`, which is the single
source of truth for all agent state.
