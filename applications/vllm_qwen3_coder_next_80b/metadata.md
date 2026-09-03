# Copyright 2026 CIQ, Inc. All rights reserved.
---
id: "ciq/ml_and_ai/vllm_qwen3_coder_next_80b"
name: "Qwen3-Coder Next 80B"
template: vllm
category: "ML_AND_AI"
tags:
- LLM
- inference
- autoscaling
- OpenAI API
- Qwen
- ai
- model
---
Serves Qwen3-Coder-Next-FP8 (hybrid-attention MoE, 80B parameters / 3B active, FP8) from an autoscaled pool of
[vLLM](https://docs.vllm.ai/en/stable) replicas. This is the `vllm` catalog
entry preconfigured from the model card; the model has no upstream vLLM recipe yet.

- **Checkpoint**: `Qwen/Qwen3-Coder-Next-FP8`
- **License**: apache-2.0
- **Context preset**: 262144 tokens
- **GPU fit**: two 80GB GPUs per replica

The checkpoint is downloaded from the HuggingFace Hub once, at workflow start,
into the workflow's volume (data ingress); replicas serve fully offline from
that local copy. Set `Volume` to a persistent volume to keep it across
workflow restarts.

```
fuzzball workflow catalog start "Qwen3-Coder Next 80B"
fuzzball workflow catalog start "Qwen3-Coder Next 80B" --values Volume=my-models,MaxReplicas=4
fuzzball workflow catalog start "Qwen3-Coder Next 80B" --values Nodes=2,GpusPerNode=1
```

Set `Nodes` above 1 to serve each replica across several nodes; see the `vllm`
entry description for what a multi-node replica needs.

Access, scaling, and gateway discovery are exactly the `vllm` entry's: a
LiteLLM proxy holds the endpoint by default, and with `Proxy=false` the pool
publishes per-replica endpoints with the `ciq.com/api`/`ciq.com/model`
annotations that the LiteLLM Model Gateway entry (`litellm`) discovers. See
the `vllm` entry description for details and scaling caveats.


## Notes

- No upstream vLLM recipe for this model yet; the configuration follows the model card and the Qwen3-Coder family recipe.
- The Qwen3-Next hybrid architecture needs a recent vLLM; if startup rejects the model, override VllmImage with a newer tag.
