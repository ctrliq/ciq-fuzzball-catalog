# Copyright 2026 CIQ, Inc. All rights reserved.
---
id: "ciq/ml_and_ai/vllm_ministral_3_8b"
name: "Ministral 3 8B"
template: vllm
category: "ML_AND_AI"
tags:
- LLM
- inference
- autoscaling
- OpenAI API
- Mistral
- ai
- model
---
Serves Ministral 3 8B Reasoning (dense, 8B parameters), the compact Apache-2.0 Mistral from an autoscaled pool of
[vLLM](https://docs.vllm.ai/en/stable) replicas. This is the `vllm` catalog
entry preconfigured with the deployment its
[vLLM recipe](https://recipes.vllm.ai/mistralai/Ministral-3-8B-Reasoning-2512) validated.

- **Checkpoint**: `mistralai/Ministral-3-8B-Reasoning-2512`
- **License**: apache-2.0
- **Context preset**: 262144 tokens
- **GPU fit**: one 24GB+ GPU per replica; at 24GB, lower MaxContextSize so the KV cache fits beside the ~16GB weights

The checkpoint is downloaded from the HuggingFace Hub once, at workflow start,
into the workflow's volume (data ingress); replicas serve fully offline from
that local copy. Set `Volume` to a persistent volume to keep it across
workflow restarts.

```
fuzzball workflow catalog start "Ministral 3 8B"
fuzzball workflow catalog start "Ministral 3 8B" --values Volume=my-models,MaxReplicas=8
```

Access, scaling, and gateway discovery are exactly the `vllm` entry's: a
LiteLLM proxy holds the endpoint by default, and with `Proxy=false` the pool
publishes per-replica endpoints with the `ciq.com/api`/`ciq.com/model`
annotations that the LiteLLM Model Gateway entry (`litellm`) discovers. See
the `vllm` entry description for details and scaling caveats.
