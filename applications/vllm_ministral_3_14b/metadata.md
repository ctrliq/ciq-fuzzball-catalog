# Copyright 2026 CIQ, Inc. All rights reserved.
---
id: "ciq/ml_and_ai/vllm_ministral_3_14b"
name: "Ministral 3 14B"
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
Serves Ministral 3 14B Instruct (dense, 14B parameters), Apache-2.0 licensed from an autoscaled pool of
[vLLM](https://docs.vllm.ai/en/stable) replicas. This is the `vllm` catalog
entry preconfigured with the deployment its
[vLLM recipe](https://recipes.vllm.ai/mistralai/Ministral-3-14B-Instruct-2512) validated.

- **Checkpoint**: `mistralai/Ministral-3-14B-Instruct-2512`
- **License**: apache-2.0
- **Context preset**: 262144 tokens
- **GPU fit**: one 48GB+ GPU per replica (BF16 weights are ~28GB)

The checkpoint is downloaded from the HuggingFace Hub once, at workflow start,
into the workflow's volume (data ingress); replicas serve fully offline from
that local copy. Set `Volume` to a persistent volume to keep it across
workflow restarts.

```
fuzzball workflow catalog start "Ministral 3 14B"
fuzzball workflow catalog start "Ministral 3 14B" --values Volume=my-models,MaxReplicas=8
```

Access, scaling, and gateway discovery are exactly the `vllm` entry's: a
LiteLLM proxy holds the endpoint by default, and with `Proxy=false` the pool
publishes per-replica endpoints with the `ciq.com/api`/`ciq.com/model`
annotations that the LiteLLM Model Gateway entry (`litellm`) discovers. See
the `vllm` entry description for details and scaling caveats.
