# Copyright 2026 CIQ, Inc. All rights reserved.
---
id: "ciq/ml_and_ai/vllm_mistral_medium_3_5"
name: "Mistral Medium 3.5"
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
Serves Mistral Medium 3.5 (dense, 128B parameters) from an autoscaled pool of
[vLLM](https://docs.vllm.ai/en/stable) replicas. This is the `vllm` catalog
entry preconfigured with the deployment its
[vLLM recipe](https://recipes.vllm.ai/mistralai/Mistral-Medium-3.5-128B) validated.

- **Checkpoint**: `mistralai/Mistral-Medium-3.5-128B`
- **License**: other (see the HuggingFace model card)
- **Context preset**: 262144 tokens
- **GPU fit**: an 8-GPU 80GB+ node per replica

The checkpoint is downloaded from the HuggingFace Hub once, at workflow start,
into the workflow's volume (data ingress); replicas serve fully offline from
that local copy. Set `Volume` to a persistent volume to keep it across
workflow restarts.

```
fuzzball workflow catalog start "Mistral Medium 3.5"
fuzzball workflow catalog start "Mistral Medium 3.5" --values Volume=my-models,MaxReplicas=4
```

Access, scaling, and gateway discovery are exactly the `vllm` entry's: a
LiteLLM proxy holds the endpoint by default, and with `Proxy=false` the pool
publishes per-replica endpoints with the `ciq.com/api`/`ciq.com/model`
annotations that the LiteLLM Model Gateway entry (`litellm`) discovers. See
the `vllm` entry description for details and scaling caveats.

## Notes

- The reasoning parser (--reasoning-parser mistral) is part of this model's recipe-validated flags; Mistral Medium 3.5 supports reasoning output even though this entry's summary line does not advertise it.
