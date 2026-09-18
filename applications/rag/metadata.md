# Copyright 2026 CIQ, Inc. All rights reserved.
---
id: "ciq/ml_and_ai/rag"
name: "rag"
category: "ML_AND_AI"
tags:
- RAG
- LLM
- MCP
- vector search
- retrieval
- ai
---
This workflow runs a retrieval-augmented-generation (RAG) corpus service built on
[haiku.rag](https://github.com/ggozad/haiku.rag): document ingestion (PDF, DOCX,
PPTX, HTML, plain text — including OCR for scanned PDFs), hybrid vector +
full-text search with citation metadata, and retrieval exposed as **MCP tools**
over streamable HTTP that any MCP-capable agent can call from outside the
cluster. The corpus and its index are files on the workflow's volume (embedded
LanceDB) — there is no database service to operate.

`Endpoint` and `EmbeddingModel` are required (no catalog endpoint serves
embeddings, so there is no default that works), and `EmbeddingDim` must match
the model's true vector dimension -- the startup check fails fast, naming the
correct value, if it does not:

```
fuzzball workflow catalog start rag --values Endpoint=https://<vllm-endpoint-url>,EmbeddingModel=Qwen/Qwen3-Embedding-8B,EmbeddingDim=4096
fuzzball workflow catalog start rag --values Volume=corpus,Endpoint=https://<vllm-endpoint-url>,EmbeddingModel=Qwen/Qwen3-Embedding-8B,EmbeddingDim=4096
fuzzball workflow catalog start rag --values Volume=corpus,Endpoint=...,EmbeddingModel=...,EmbeddingDim=...,GenerationModel=<chat-model>
fuzzball workflow catalog start rag --values Volume=corpus,Endpoint=...,EmbeddingModel=...,EmbeddingDim=...,ReadOnly=false
```

A trailing `/v1` or `/` on `Endpoint` is accepted and normalized.

Embeddings (and generation, when `GenerationModel` is set) are served by the
OpenAI-compatible `Endpoint` — typically the `vllm` catalog entry or a LiteLLM
gateway. At startup each service embeds a probe string against the endpoint and
checks the result is `EmbeddingModel` returning `EmbeddingDim`-length vectors,
so the failure surfaces in the service log (`fuzzball workflow log <workflow id>
mcp`) rather than as a provider error on the first search. A bad credential, a
mismatched dimension, or an endpoint that answers but cannot embed fails fast; a
still-warming pool (a scaled-to-zero backend answers 400/404/503 until a replica
is live) is retried for up to fifteen minutes so a cold endpoint is not mistaken
for a broken one. The cost of that patience: a wrong URL, an unreachable
endpoint, or a wrong model name looks the same as a warming pool, so it is
retried too and surfaces only when the window expires (as `not ready after
900s`, naming the last error seen).

For a Fuzzball endpoint in your scope, **no key is needed**: each service mints
an endpoint access token at startup with this workflow's own identity, the
endpoint proxy consumes it and signs the caller's identity for the model
gateway, and access is simply the endpoint's scope — the same control as any
Fuzzball endpoint. No credential is stored anywhere. (The minted token is valid
up to 7 days; because the startup check runs only at startup, a token that
lapses mid-life leaves the service looking healthy while embedding calls fail —
restart to mint afresh.)

A key is needed only for a **public** endpoint (nothing is signed there, so the
key is the barrier), a **third-party/external** OpenAI-compatible API, or a
cluster whose nodes **do not sign caller identity** (the gateway falls back to
its own key check). Supply it via `EndpointTokenSecret` (preferred) or
`EndpointToken`; a key that is sent decides the request, and the signed identity
is used only when no key is sent. haiku.rag sends that key as a bearer, so the
one case rag cannot serve is a non-signing cluster fronted by a LiteLLM gateway,
which wants a Fuzzball token *and* a separate `x-litellm-api-key` at once — use a
signing cluster or a direct (non-gateway) endpoint there. The workflow makes no
network connections beyond the configured endpoint, so it operates air-gapped
(document-parsing models are baked into the image).

## Ingestion

With the default `ReadOnly=true`, ingestion runs through a dedicated ingester
service:

- **Inbox directory**: any file placed under `/data/inbox` on the volume is
  ingested automatically; re-adding a changed file replaces its previous
  content instead of duplicating it.
- **Jobs monitoring API**: `GET /jobs` and `GET /jobs/{id}` report each
  document's status (queued/claimed/succeeded/failed), with retry and a
  dead-letter queue. Failed documents leave no partial content in the corpus.
  Submission itself happens through the inbox (or the MCP write tools with
  `ReadOnly=false`) -- the API monitors and manages jobs, it does not accept
  uploads. It is deliberately not published as an endpoint: it is a read-only
  status API that accepts no uploads, and — being a third-party surface with no
  caller-identity integration — publishing it would add an outward endpoint
  gated only by its static `auth_token`, for no gain. Reach it from inside the
  cluster with `fuzzball workflow port-forward <workflow id> ingester <local
  port>:<ingest port>`, authenticating with the generated `auth_token`, or just
  follow the ingester's logs. The `show-connection` job prints the token and the
  exact port-forward command.

With `ReadOnly=false`, no ingester runs and the MCP surface itself exposes
document-management tools (add/delete) alongside retrieval. **Note:** haiku.rag
is a third-party service with no caller-identity seam, so the `mcp` endpoint
authorizes purely by scope — it cannot distinguish one in-scope caller from
another. At `ReadOnly=false` with a group or organization scope, the add/delete
tools are therefore open to everyone in that scope. Per-caller authorization
would require a sidecar verifying the proxy's `x-fuzzball-caller-identity`
assertion; that is out of scope for this entry. Keep `ReadOnly=true` (or a
`user` scope) where that matters.

## Retrieval over MCP

The `mcp` endpoint serves MCP over streamable HTTP. Configure an agent with the
endpoint URL and, for non-public scopes, the Fuzzball endpoint token in the
`Authorization` header:

```json
{
  "url": "https://<mcp-endpoint-host>/mcp",
  "headers": { "Authorization": "Bearer <fuzzball endpoint token>" }
}
```

With the default `ReadOnly=true`, the MCP surface exposes retrieval only
(`search_documents`, `get_document`, `list_documents`, `ask_question`). Document
management tools appear only with `ReadOnly=false`; the code-execution analysis
tool is disabled by this entry in both modes. Search results carry the
source document URI, page numbers, and heading paths for citation.

## Model consistency

The corpus is bound to its embedding model. Query and corpus embeddings always
use the same model; pointing the entry at an existing corpus with a different
`EmbeddingModel` or `EmbeddingDim` fails at startup naming the conflict. To
migrate a corpus to a new embedding model, run
`haiku-rag rebuild --set-embedder` against the volume (documents are re-embedded
from stored text; no re-ingestion needed).

## Persistence

The default `Volume=ephemeral` is for evaluation only — cancelling the workflow
destroys the corpus. For real use, create a persistent volume and pass its name
(`Volume=corpus`): ingest, cancel the workflow, start a new one on the same
volume, and searches return the same results. One corpus per workflow; separate
corpora get separate volumes and endpoint scopes.
