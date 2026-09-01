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

```
fuzzball workflow catalog start rag
fuzzball workflow catalog start rag --values Volume=corpus,Endpoint=https://<vllm-endpoint-url>/v1
fuzzball workflow catalog start rag --values Volume=corpus,Endpoint=...,EmbeddingModel=Qwen/Qwen3-Embedding-8B,EmbeddingDim=4096
fuzzball workflow catalog start rag --values Volume=corpus,Endpoint=...,ReadOnly=false
```

Embeddings (and generation, when `GenerationModel` is set) are served by the
OpenAI-compatible `Endpoint` — typically the `vllm` catalog entry or a LiteLLM
gateway. For a Fuzzball endpoint in your scope, authentication is automatic:
with no token configured, each service mints an endpoint access token at
startup using this workflow's own identity, so no credential is stored
anywhere. The minted token is valid for up to 7 days and is not renewed; its
expiry is invisible to the readiness probes (they check the port, not the
model endpoint), so a long-lived corpus service starts failing embedding calls
while looking healthy — restart the workflow to mint afresh, or pass a token
minted with `fuzzball workflow endpoints generate-token <endpoint-id>
--expiration <lifetime>` via `EndpointTokenSecret`. That value is also the path for
credentials the endpoint itself requires (a LiteLLM virtual key, a third-party
API key). The workflow makes no network connections beyond the configured
endpoint, so it operates air-gapped (document-parsing models are baked into
the image).

## Ingestion

With the default `ReadOnly=true`, ingestion runs through a dedicated ingester
service:

- **Inbox directory**: any file placed under `/data/inbox` on the volume is
  ingested automatically; re-adding a changed file replaces its previous
  content instead of duplicating it.
- **Jobs monitoring API** on the `ingest` endpoint: `GET /jobs` and
  `GET /jobs/{id}` report each document's status
  (queued/claimed/succeeded/failed), with retry and a dead-letter queue. Failed
  documents leave no partial content in the corpus. Submission itself happens
  through the inbox (or the MCP write tools with `ReadOnly=false`) -- the API
  monitors and manages jobs, it does not accept uploads. Its bearer token is
  the generated `auth_token` in the rendered workflow definition — but at any
  non-public `Scope` the endpoint proxy consumes the `Authorization` header,
  so through the endpoint URL the API is only reachable at `Scope=public`
  (where that token is the sole gate). At other scopes, call it from inside
  the cluster at the service's own address, or follow progress in the
  ingester's logs.

With `ReadOnly=false`, no ingester runs and the MCP surface itself exposes
document-management tools (add/delete) alongside retrieval.

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
