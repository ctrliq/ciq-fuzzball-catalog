# rag — workflow catalog entry

Catalog entry for a RAG corpus service built on haiku.rag (see metadata.md).

The container image this entry consumes (`Image` value) is built from
`definition_files/haiku-rag.def` by this repo's container CI
(`.github/workflows/build-containers.yaml`): PRs touching the definition get a
PR-scoped tag for testing, and merging retags that exact image to the release
tag `rag-haiku-rag:<version>-<arch>` on ghcr.

The image bundles the full haiku.rag package with the ingester extra, bakes
the document-parsing models for air-gapped operation (docling ships its model
weights outside the HF cache — the definition pins HF_HOME, DOCLING_CACHE_DIR,
and DOCLING_ARTIFACTS_PATH), pins CPU-only torch (parsing is CPU-bound;
embeddings/generation are remote), and carries the `analysis.enabled` gate
patch until upstream haiku.rag ships it.
