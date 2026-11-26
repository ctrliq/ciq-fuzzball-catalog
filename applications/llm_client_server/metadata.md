# Copyright 2025 CIQ, Inc. All rights reserved.
---
id: "ciq/ml_and_ai/llm_client_server"
name: "Local LLM chat"
category: "ML_AND_AI"
tags:
- LLM
- inference
---
This workflow starts an OpenAI-compatible REST API server implemented with vLLM ([vLLM docs](https://docs.vllm.ai/en/stable)) using a model downloaded from HuggingFace ([Hugging Face](https://huggingface.co/)) and provides a web-based chat interface. All processing is local.

See [Supported Models](https://docs.vllm.ai/en/stable/models/supported_models.html#supported-models) for a list of supported models.

The server will run until the workflow is cancelled.

**Container images.** `VllmImage` and `UIImage` each take a full image reference with an
explicit tag or digest, so a site without access to public registries can point them at its
own copies. For a mirror that requires credentials, set `ImageSecret` to a Fuzzball image
secret; it goes with both pulls, so they must then come from one registry. `VllmImage`
replaces the earlier `VllmVersion` value: saved overrides of that value no longer apply.
