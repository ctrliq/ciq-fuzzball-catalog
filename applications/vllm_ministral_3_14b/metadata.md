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
- vllm
- Ministral
- ai
- model
---
Serves Ministral 3 14B Instruct (dense, 14B parameters), Apache-2.0 licensed from an autoscaled pool of
[vLLM](https://docs.vllm.ai/en/stable) replicas. This is the `vllm` catalog
entry preconfigured with the serving flags its
[vLLM recipe](https://recipes.vllm.ai/mistralai/Ministral-3-14B-Instruct-2512) validated,
with the context sized to fit one 24GB GPU.

- **Checkpoint**: `mistralai/Ministral-3-14B-Instruct-2512`
- **License**: apache-2.0
- **Context preset**: 16384 tokens (the model supports 262144)
- **GPU fit**: one 24GB GPU per replica at the default context (FP8 weights are ~16GB); set MaxContextSize=131072 on a 48GB GPU, or the recipe's 262144 on an 80GB GPU

The checkpoint is downloaded from the HuggingFace Hub once, at workflow start,
into the workflow's volume (data ingress); replicas serve fully offline from
that local copy. Set `Volume` to a persistent volume to keep it across
workflow restarts.

```
fuzzball workflow catalog start "Ministral 3 14B"
fuzzball workflow catalog start "Ministral 3 14B" --values Volume=my-models,MaxReplicas=8
fuzzball workflow catalog start "Ministral 3 14B" --values MaxContextSize=131072
fuzzball workflow catalog start "Ministral 3 14B" --values Nodes=2
```

Set `Nodes` above 1 to serve each replica across several nodes; see the `vllm`
entry description for what a multi-node replica needs.

Access, scaling, and gateway discovery are exactly the `vllm` entry's: a
LiteLLM proxy holds the endpoint by default, and with `Proxy=false` the pool
publishes per-replica endpoints with the `ciq.com/api`/`ciq.com/model`
annotations that the LiteLLM Model Gateway entry (`litellm`) discovers. See
the `vllm` entry description for details and scaling caveats.
