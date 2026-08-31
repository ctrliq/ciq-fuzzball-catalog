# Copyright 2026 CIQ, Inc. All rights reserved.
---
id: "ciq/ml_and_ai/vllm_gpt_oss_120b"
name: "gpt-oss-120b"
template: vllm
category: "ML_AND_AI"
tags:
- LLM
- inference
- autoscaling
- OpenAI API
- gpt-oss
- ai
- model
---
Serves OpenAI's gpt-oss-120b (MoE, 120B parameters / 5.1B active, MXFP4) from an autoscaled pool of
[vLLM](https://docs.vllm.ai/en/stable) replicas. This is the `vllm` catalog
entry preconfigured with the deployment its
[vLLM recipe](https://recipes.vllm.ai/openai/gpt-oss-120b) validated.

- **Checkpoint**: `openai/gpt-oss-120b`
- **License**: apache-2.0
- **Context preset**: 131072 tokens
- **GPU fit**: one 80GB GPU per replica (H100/H200/B200/MI300X-class)

The checkpoint is downloaded from the HuggingFace Hub once, at workflow start,
into the workflow's volume (data ingress). Note that gpt-oss also loads the
OpenAI harmony token encoding (`o200k_base`) at startup, which vLLM fetches
from the internet on first run -- so a replica is not fully air-gapped unless
that encoding is staged locally and vLLM is pointed at it with the
`TIKTOKEN_ENCODINGS_BASE` environment variable, which this entry does not
currently expose a value for. Set `Volume` to a persistent volume to keep the checkpoint across
workflow restarts.

```
fuzzball workflow catalog start "gpt-oss-120b"
fuzzball workflow catalog start "gpt-oss-120b" --values Volume=my-models,MaxReplicas=8
```

Access, scaling, and gateway discovery are exactly the `vllm` entry's: a
LiteLLM proxy holds the endpoint by default, and with `Proxy=false` the pool
publishes per-replica endpoints with the `ciq.com/api`/`ciq.com/model`
annotations that the LiteLLM Model Gateway entry (`litellm`) discovers. See
the `vllm` entry description for details and scaling caveats.

## Notes

- The recipe's optional EAGLE3 speculative decoding takes a JSON --speculative-config that ExtraArgs cannot carry; see the recipe.
