# Copyright 2026 CIQ, Inc. All rights reserved.
---
id: "ciq/ml_and_ai/opencode"
name: "opencode"
category: "ML_AND_AI"
tags:
- coding agent
- LLM
- OpenAI API
- development
---
This workflow runs [OpenCode](https://opencode.ai), a coding agent, as a
Fuzzball service already wired to a model served on the cluster. The agent's
files, sessions, and message history live on the workflow's volume, and the
model is reached over an OpenAI-compatible endpoint such as the one published by
the `vllm` or `litellm` entries.

```
fuzzball workflow catalog start opencode --values Endpoint=https://<endpoint-url>,Model=openai/gpt-oss-20b,ApiKey=sk-...
fuzzball workflow catalog start opencode --values Endpoint=https://<endpoint-url>,Model=openai/gpt-oss-20b,ApiKeySecret=secret://user/litellm-key
fuzzball workflow catalog start opencode --values Endpoint=https://<endpoint-url>,Model=openai/gpt-oss-20b,ApiKey=sk-...,ServiceScope=public
```

Get the endpoint URL of the model workflow with `fuzzball workflow endpoints
list`, and its LiteLLM key from its definition (`fuzzball workflow get
<workflow id>`). `Model` is the name the endpoint serves; for the `vllm` entry
that is its `Model` value without the `hf://` prefix.

## Attaching to the model

With the default `EndpointAuth=fuzzball-token`, the workflow authenticates to the
model endpoint itself: at startup the server mints an endpoint access token using
this workflow's own injected identity, so no user credential is stored anywhere in
the definition. Because the Fuzzball endpoint proxy consumes the `Authorization`
header on any endpoint whose scope is not public, the model's own key (`ApiKey`
or `ApiKeySecret`) is sent in the `x-litellm-api-key` header, which LiteLLM
v1.97.0 and later honour and the proxy leaves untouched.

Set `EndpointAuth=api-key` for a public Fuzzball endpoint or a third-party API,
where the key is sent as the bearer token and nothing is minted. A public
endpoint needs no token and the server refuses to mint one for it, so
`fuzzball-token` against a public endpoint stops the workflow with that message.

The token is minted by the service itself rather than a preparatory job, because
the server grants an endpoint token no more lifetime than the calling workflow
token has left: a job's token lives only as long as the job, while a service
without a walltime holds one for seven days. It is minted once and never renewed,
so `TokenLifetime` clamped to that seven days bounds how long the agent can reach
the model. When it lapses the agent starts failing against the model while the
server itself stays healthy -- the readiness probe never touches the endpoint --
so restart the workflow to mint a fresh one.

## Reaching the server

The service publishes one endpoint serving both an HTTP API and a web
application. How you reach it depends on `ServiceScope`, and the choice is not
symmetric:

- At `user`, `group`, or `organization` scope, requests through the endpoint URL
  need a Fuzzball credential: an [endpoint access
  token](https://ui.stable.fuzzball.ciq.dev/docs/advanced-features/workflow-endpoints/)
  for API clients, or a browser session for the web application.
- At `public` scope, Fuzzball performs no authentication of its own.

The server always enforces a basic-auth password, generated at submit time and
printed by the `show-server` job. That is not redundant with the endpoint scope: a
plain service binds its port on the node it runs on, so the server is reachable
directly at that address with no proxy in front of it, whatever the scope says. At
`public` scope the password is the only barrier at all.

`opencode attach <url> -p <password>` therefore works from outside the cluster
only at `public` scope: attach sends its credentials in the `Authorization` header,
which a non-public endpoint's proxy consumes.

Anyone who reaches the server can run shell commands and edit files inside the
container, so prefer the narrowest scope that fits and treat the password as a
real credential.

## Known limitations

- *The web application cannot select this model.* As of OpenCode 1.18.23 a
  provider defined in configuration appears in the server's v1 API but not in the
  v2 API that the bundled web application queries, so the model picker offers only
  OpenCode's own hosted models. Drive the server through the v1 session API
  (`POST /session`, then `POST /session/{id}/message` with
  `{"model":{"providerID":"fuzzball","modelID":"<Model>"},"parts":[...]}`) or
  attach a local client.
- *Tool calling depends on the serving side.* Agentic work needs a model that
  supports tool calls and a server configured to parse them; with the `vllm`
  entry, pass the appropriate flags in `ExtraArgs` (for example
  `--tool-call-parser openai --enable-auto-tool-choice` for gpt-oss models).
  Without them the agent can converse but cannot read or edit files.
- *Private-CA clusters.* Reaching a Fuzzball endpoint over TLS relies on the node
  trust store that Fuzzball bind-mounts into workflow containers, so this entry
  needs a cluster new enough to provide it. OpenCode is a Bun binary and ignores
  the injected `SSL_CERT_DIR`, so the entry points `NODE_EXTRA_CA_CERTS` at
  `root-ca.crt` in that mount instead.

## Storage

`Volume` defaults to `ephemeral`, which destroys the workspace, the session
history, and any work in progress when the workflow stops. Name an existing
persistent volume to keep them. The working directory is `/data/workspace`.
