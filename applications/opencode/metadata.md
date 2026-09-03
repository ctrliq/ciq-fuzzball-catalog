# Copyright 2026 CIQ, Inc. All rights reserved.
---
id: "ciq/ml_and_ai/opencode"
name: "OpenCode"
category: "ML_AND_AI"
tags:
- ai
- agent
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
fuzzball workflow catalog start OpenCode --values Endpoint=https://<endpoint-url>,Model=openai/gpt-oss-20b,ApiKey=sk-...
fuzzball workflow catalog start OpenCode --values Endpoint=https://<endpoint-url>,Model=openai/gpt-oss-20b,ApiKeySecret=secret://user/litellm-key
fuzzball workflow catalog start OpenCode --values Endpoint=https://<endpoint-url>,Model=openai/gpt-oss-20b,ApiKey=sk-...,ServiceScope=public
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
application, and the server enforces a password of its own at every scope,
generated at submit time and printed by the `show-server` job. That password is
not redundant with the endpoint scope: a plain service also binds its port on the
node it runs on, where no endpoint proxy stands in front of it.

The password travels in the `Authorization` header, which the endpoint proxy
consumes at every scope but `public`. The server checks a query parameter first,
so that is how a client authenticates through the endpoint URL:

```
curl "<server url>/api/session?auth_token=<base64 of opencode:PASSWORD>"
```

What that leaves per scope:

- `user`, `group`, `organization`: API clients work by appending `auth_token`, and
  requests additionally carry a Fuzzball [endpoint access
  token](https://ui.stable.fuzzball.ciq.dev/docs/advanced-features/workflow-endpoints/)
  in `Authorization`. The web application does **not** work: its own requests
  carry no query parameter and the header has already been consumed. `opencode
  attach` does not work either, for the same reason.
- `public`: Fuzzball authenticates nothing and the password is the only barrier,
  which is also what makes the browser (it prompts, user `opencode`) and
  `opencode attach <url> -p <password>` work.

Anyone who reaches the server can run shell commands and edit files inside the
container, so prefer the narrowest scope that fits and treat the password as a
real credential. The workflow's own API token is removed from the environment
before the agent starts, so a prompt injection cannot walk off with it.

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
  needs a cluster new enough to provide it. The entry appends that CA to the
  image's public roots in a writable copy and points both TLS stacks at it
  (`SSL_CERT_FILE` for the shell's `wget`, `NODE_EXTRA_CA_CERTS` for the Bun
  runtime, which ignores `SSL_CERT_DIR`); the image's own bundle is read-only to
  the uid Fuzzball runs it under.
- *A minimal image.* It is Alpine plus the OpenCode binary: no `git`, no language
  toolchains, no compilers. The agent can read and write files and run shell
  built-ins, but a task needing a toolchain wants an image that carries one --
  override `Image` with a build of your own.

## Storage

`Volume` defaults to `ephemeral`, which destroys the workspace, the session
history, and any work in progress when the workflow stops. Name an existing
persistent volume to keep them. The working directory is `/data/workspace`.
