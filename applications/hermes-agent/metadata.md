# Copyright 2026 CIQ, Inc. All rights reserved.
---
id: "ciq/ml_and_ai/hermes-agent"
name: "hermes-agent"
category: "ML_AND_AI"
tags:
- agent
- LLM
- OpenAI API
- genAI
- ai
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
fuzzball workflow catalog start hermes-agent --values ApiKeySecret=secret://user/litellm-key,DashboardPasswordSecret=secret://user/hermes-dashboard-password,DashboardSessionSecret=secret://user/hermes-dashboard-session
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

`ATTACHED` is logged when the gateway or model changes and `MINTED` on each
rotation, so a healthy steady state is quiet rather than chatty. A pass that
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

The service publishes one endpoint: the web dashboard. Open its URL in a browser
that is signed in to the Fuzzball web UI and you get the agent's own sign-in
page.

The agent also runs its own OpenAI-compatible API, but **it is not published as
an endpoint**. It accepts its key only as an `Authorization` bearer, and the
Fuzzball endpoint proxy consumes that header before the request reaches the
container -- verified: a request carrying it arrives with the header absent and
`x-fuzzball-account-id` added in its place. An endpoint in front of it therefore
could not be authenticated at any scope this entry offers. The dashboard is
unaffected because it signs in with a form and a cookie, and the application's
own cookies reach the container untouched.

`ApiServerAccess` decides how far that API reaches. At `loopback`, the default,
it is bound inside the container only -- enough for the dashboard and for the
agent's own scheduled work, and the right default for an API that can run shell
commands. At `node` it binds the node's port, where the API key is the only
thing protecting it. Reach it either way with:

```sh
fuzzball workflow exec <workflow id> hermes -- \
  curl -H "Authorization: Bearer <api key>" http://127.0.0.1:<api port>/v1/models
```

Two layers of authentication apply and neither is redundant:

- The endpoint scope. At `user`, `group`, or `organization`, a request through
  the endpoint URL has to carry a Fuzzball credential. A browser already signed
  in to the Fuzzball web UI sends one as a cookie, which is what makes the
  dashboard URL work there. Anything else -- `curl`, a script, a client you
  control -- supplies an [endpoint access
  token](https://ui.stable.fuzzball.ciq.dev/docs/advanced-features/workflow-endpoints/)
  in `Authorization`. There is no interactive sign-in at this layer, so a
  browser carrying no Fuzzball session gets a bare `401`, with no redirect to a
  login and no `WWW-Authenticate` challenge.
- The agent's own credentials -- a dashboard password and an API key, each
  taken from a Fuzzball secret you name or generated at submit time and printed
  by the `show-agent` job (see [Credentials](#credentials)). A plain service
  binds its port on the node it runs on, so the endpoint proxy is not the only
  way in and the scope alone protects nothing -- which is why `ApiServerAccess`
  defaults to `loopback`, so the one listener that can run shell commands is not
  on the node's network unless you ask for it.

Two consequences follow:

- **Shell access here is the workflow's Fuzzball identity.** Anyone who reaches
  the agent can run commands as it, and the agent's own credential file holds a
  token that mints endpoint tokens for everything its owner can see -- not just
  the gateway. The entry drops `FB_TOKEN` from the environment before starting
  the agent, which removes the most obvious route but not the file. Treat
  reaching this agent as equivalent to holding the submitter's endpoint access.
- **Opening any Fuzzball endpoint in a browser shows your own session token to
  scripts running on the page it serves.** The cookie a browser uses to satisfy
  the endpoint scope is set for the whole cluster domain and is not hidden from
  scripts, so the page can read it -- this dashboard's included. That is a
  property of Fuzzball endpoints rather than of this entry, but it weighs more
  here than for a notebook, because the page comes from an agent that runs
  commands. The forwarded port avoids it: no proxy in the path, no cookie sent.

`public` is deliberately not offered as a scope. Hermes refuses to serve an
unauthenticated dashboard on a non-loopback bind at all -- upstream removed the
escape hatch that allowed it, citing exposed dashboards and API servers being
driven into planting SSH-key backdoors. Anyone who
reaches this agent can run shell commands in its container, read everything it
remembers, and spend model capacity, so prefer the narrowest scope that fits.

### From a workstation

Take the dashboard URL from `fuzzball workflow endpoints list`, or use the
**Connect** button on the workflow in the Fuzzball web UI, and open it in the
same browser you signed in to that UI with. The session that browser already
holds satisfies the endpoint scope, so what you see is the agent's own sign-in:
the username in `DashboardUsername` (`hermes` by default) and the password,
which `show-agent` prints unless `DashboardPasswordSecret` names it.

A browser with no Fuzzball session has no way to present a Fuzzball credential
and gets a `401`. Forward the port instead, which takes the proxy out of the
picture entirely -- leaving only the agent's own sign-in, and keeping your
Fuzzball session cookie away from the page:

```sh
fuzzball workflow port-forward <workflow id> hermes <local port>:<dashboard port>
# then open http://127.0.0.1:<local port> and sign in with the dashboard credentials
```

An SSH tunnel to the node the service landed on does the same thing if you have
shell access to it. Verified end to end from a laptop: the sign-in page renders
over the tunnel and the dashboard password is accepted.

A header-setting client reaches the endpoint URL from anywhere, no browser
session involved.

Reaching a *gateway* from outside the cluster works for `curl` and any other
header-setting client, because its two credentials travel in two different
headers -- the proxy consumes `Authorization` and passes `x-litellm-api-key`
through untouched. That is what makes the workstation setup below possible, and
it is exactly what the agent's own API lacks.

## Credentials

The agent enforces three credentials of its own: the dashboard password, the
key the dashboard signs its sessions with, and the key for its OpenAI-compatible
API. By default each is generated at every workflow start and embedded in the
workflow definition, which is convenient and has two costs. Anyone who can read
the workflow can read them, and every start replaces all three -- so each
resubmit means looking up a new password, and no dashboard session survives it.

Name a user-scoped secret of type `value` for any of them and the container
receives the reference instead: Fuzzball resolves it at start, the value never
enters the definition or the `show-agent` log, and it is the same after every
start. Someone who can read the workflow no longer sees it; its owner can
still read it from the running container, as with `ApiKeySecret`. Each secret
left empty keeps the generated behaviour. The username is not a secret, so
`DashboardUsername` takes it in plain text.

| Value                     | What it sets                               | Accepted content            |
|---------------------------|--------------------------------------------|-----------------------------|
| `DashboardUsername`       | the sign-in username                       | plain text; default `hermes` |
| `DashboardPasswordSecret` | the sign-in password                       | non-empty                   |
| `DashboardSessionSecret`  | the key dashboard sessions are signed with | at least 16 bytes           |
| `ApiServerKeySecret`      | the API's bearer key                       | at least 16 characters      |

```sh
printf '%s' 'a password you choose' | fuzzball secret create secret://user/hermes-dashboard-password --type value
openssl rand -hex 32 | fuzzball secret create secret://user/hermes-dashboard-session --type value
openssl rand -hex 32 | fuzzball secret create secret://user/hermes-api-key --type value
fuzzball workflow catalog start hermes-agent --values \
  ApiKeySecret=secret://user/litellm-key,DashboardPasswordSecret=secret://user/hermes-dashboard-password,DashboardSessionSecret=secret://user/hermes-dashboard-session,ApiServerKeySecret=secret://user/hermes-api-key
```

The constraints on the three secrets are Hermes' own, and it enforces them in
ways an operator cannot see: the dashboard plugin declines to register on an empty
password or a session key under 16 bytes, after which the dashboard refuses
every request, and the API server refuses to start on a key under 16
characters, taking the dashboard with it. The template cannot inspect a secret's
contents, so the service checks each resolved value at start and stops with a
message naming the offending value instead.

Rotating a credential means updating the secret and starting the workflow
again; the running container holds the value it started with. A stable session
key only helps where the browser keeps reaching the same address, such as a
forwarded port: a resubmitted workflow publishes its dashboard under a new
endpoint hostname, whose cookies start empty whatever the key. A secret reference is
accepted only in the `user` scope, the one scope environment-variable secrets
take, so a `group` or `organization` reference fails at render.

Hermes also accepts a precomputed scrypt hash of the password, which is its
preferred form for configuration at rest. This entry does not offer it: a
Fuzzball secret already keeps the plaintext out of the definition, and Hermes
gives a plaintext password from the environment precedence over a hash anyway.

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

- **The `vllm` entry is not discoverable at its defaults.** With `Proxy=true`,
  which is its default, its only OpenAI surface is an in-workflow LiteLLM proxy
  whose endpoint carries no annotations -- so a gateway cannot register it and
  this entry cannot discover it. Start `vllm` with `Proxy=false`, which
  publishes annotated per-replica endpoints for a `litellm` gateway to find, or
  point this entry straight at the vllm proxy with an explicit `Endpoint`.
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
- **`MaxContextSize` is not discovered, and 64000 is a hard floor.** Hermes
  refuses to start a session against a context window smaller than that, and it
  refuses at the first message rather than at startup -- the dashboard comes up,
  the agent attaches, and then every prompt fails. So match this to the serving
  entry, but only among models that serve at least 64K: a value above what the
  model serves produces requests the model rejects, and a smaller model cannot
  run this entry at all.
- **The agent borrows the owner's reach.** It discovers and authenticates to the
  gateway as the identity that started it, so its endpoint scope decides who can
  use it, regardless of the callers' own grants.
- **Generated credentials are readable by anyone who can read the workflow,
  and change on every workflow start.** Without `DashboardPasswordSecret`,
  `DashboardSessionSecret` and `ApiServerKeySecret`, the dashboard password,
  its session signing key and the API key are generated fresh at every workflow
  start and embedded in the workflow definition. Changing one then means
  stopping and resubmitting the workflow -- which on an ephemeral `Volume` also
  destroys everything the agent has accumulated -- and no dashboard session
  survives a resubmit. Name secrets to keep the values out of the definition
  and the same from one start to the next; see [Credentials](#credentials).
- **The entry does not use the image's entrypoint.** The published image is
  built for Docker, where it starts as root and drops to its own baked user. Its
  entrypoint and wrapper both refuse to start under any other uid, and Fuzzball
  supplies exactly that, so every writable path the runtime uses is redirected
  onto the volume. So this entry seeds the
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
