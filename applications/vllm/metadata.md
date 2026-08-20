# Copyright 2026 CIQ, Inc. All rights reserved.
---
id: "ciq/ml_and_ai/vllm_autoscaled_pool"
name: "vLLM autoscaled inference pool"
category: "ML_AND_AI"
tags:
- LLM
- inference
- autoscaling
- litellm
---

Serves one model from an autoscaled pool of vLLM ([vLLM docs](https://docs.vllm.ai/en/stable))
replicas behind a single OpenAI-compatible base URL. By default a LiteLLM
([LiteLLM docs](https://docs.litellm.ai/docs/simple_proxy)) proxy runs inside the
workflow, holds the workflow's service endpoint, and forwards to whichever
replicas are currently ready. Callers see one stable URL for the life of the
workflow; the pool grows and shrinks behind it.

This is the reference pattern for fronting a Fuzzball autoscaled service pool
with an in-workflow proxy. See
[service autoscaling](https://ui.stable.fuzzball.ciq.dev/docs/advanced-features/service-autoscaling/)
for the underlying feature.

## Usage

```sh
fuzzball workflow catalog start vllm --values ModelName=hf://openai/gpt-oss-120b
fuzzball workflow catalog start vllm --values ModelName=hf://openai/gpt-oss-120b,GPUVendor=amd
fuzzball workflow catalog start vllm --values ModelName=hf://openai/gpt-oss-120b,MinReplicas=1,MaxReplicas=10
```

`ModelName` accepts either a bare HuggingFace repo id or an `hf://` URI. Gated
models require `HuggingFaceHubToken`.

## Services

- **vllm**: The replica pool. Every replica serves the same model on the same
  port and reports Prometheus metrics on that port. Replicas share one
  autoscaler DNS record that tracks only the replicas that have passed their
  readiness probe, so a client never sees a replica that is still loading
  weights.
- **litellm**: The proxy, present only when `EnableProxy` is true. It holds the
  endpoint, exposes `/v1` OpenAI-compatible routes, and is the workflow's
  cross-service scaling source for the pool. It deliberately declares no
  `depends-on`, because it must answer requests while the pool holds zero
  replicas.

The proxy reaches the pool through the pool's autoscaler DNS name rather than
through a rendered list of replica addresses. The name resolves to the ready
replicas and remains valid while the pool is empty, so no configuration reload
is needed as replicas come and go. `dynamic-config` is the alternative when a
proxy needs per-replica backend stanzas.

## Scaling behavior

- `MinReplicas` replicas start with the workflow; capacity for `MaxReplicas` is
  pre-allocated.
- **Scale up from zero.** With `MinReplicas=0` no replica exists, so no vLLM
  metric exists either. The proxy's own request counter is the only available
  signal: any request arriving at the proxy trips
  `sum(rate(litellm_proxy_total_requests_metric_total[1m])) > bool 0` and starts
  the first replica. That request fails while the pool is cold; retry after the
  replica reports ready. Activation is repeatable, not one-shot, because the
  trigger is a rate over a live counter rather than workflow state.
- **Scale up under load.** Once replicas are running,
  `max(vllm:num_requests_waiting) >= bool ScaleUpPendingRequests` grows the pool
  toward `MaxReplicas`.
- **Scale down.** `max(vllm:num_requests_running) == bool 0` retires a replica
  only when no replica in the pool is serving a request, held for
  `ScaleDownCooldownSeconds`. Aggregating with `max` rather than per replica is
  what keeps a scale-down from cutting off a generation in flight on a sibling
  replica.

## Running without the in-workflow proxy

With `EnableProxy=false` no LiteLLM proxy is started and the pool itself carries
the service endpoint, for an external LiteLLM instance to discover and route to.
In this mode:

- `MinReplicas` must be at least 1. Nothing inside the workflow observes
  incoming requests, so an idle pool cannot wake itself.
- Scale-up is driven by the pool's own queue depth instead of proxy metrics.
- Callers authenticate directly against vLLM, so `ServerApiKey` is the key they
  present. If it is left empty, vLLM runs unauthenticated behind the endpoint's
  `ServiceScope`.

## Notes and limitations

- The autoscaler has no drain or termination grace setting. The
  `max(vllm:num_requests_running) == bool 0` scale-down condition plus
  `ScaleDownCooldownSeconds` is the drain window; size it to cover the longest
  expected streaming generation.
- Use a persistent `ModelVolume`. On the default ephemeral volume every replica
  added during scale-up re-downloads the model, which dominates cold-start time.
- Replicas do not use host networking, because two replicas placed on one node
  would collide on the shared port.
- The endpoint URL is fixed when the workflow starts and does not change as
  replicas churn. Non-public endpoints need a bearer token from
  `fuzzball workflow endpoints generate-token`.
