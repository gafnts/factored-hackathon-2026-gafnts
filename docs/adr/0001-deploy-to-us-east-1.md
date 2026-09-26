# ADR-0001: Deploy to us-east-1

## Status

Accepted (2026-09-25).

## Context

Every stack (state bucket, IAM roles, service) needs a home region, and the choice gets expensive to reverse once state exists. Nothing was deployed when this decision was made.

Three forces pull on it:

- **The dataset lives in us-east-2.** The organizer-provided dataset (about 5 GB) sits in a read-only S3 bucket in the organizers' AWS account, in us-east-2.
- **The agent depends on Amazon Bedrock.** Bedrock serves the LLM calls, and is the likely source of embeddings, reranking over Spanish and Portuguese policy text, and Guardrails for prompt-injection defense. Model availability differs by region.
- **The prototype will be served on a subdomain of `gabriel.com.gt`.** That domain's DNS is hosted on Netlify, not Route 53. If the prototype sits behind CloudFront, its ACM certificate must be issued in us-east-1 regardless of where the rest of the stack runs.

## Decision

Deploy every stack to us-east-1, the region already set as the default in the Terraform roots, bootstrap scripts, and workflows.

## Alternatives considered

**us-east-2, co-located with the dataset.** Its only advantage is proximity to the organizers' bucket, and at 5 GB the cross-region transfer costs cents. Against it, from the [Bedrock regional availability page](https://docs.aws.amazon.com/bedrock/latest/userguide/models-region-compatibility.html) as of 2026-09-25:

| Model | From us-east-1 | From us-east-2 |
|---|---|---|
| Claude Fable 5.1 | Geo, Global | Geo, Global |
| Claude Opus 5.5, Sonnet 5, Haiku 4.5 | **In-Region**, Geo, Global | Geo, Global |
| Cohere Embed v4 (multilingual) | In-Region, Geo, Global | Geo, Global |
| Titan Text Embeddings V2 | In-Region | In-Region |
| Cohere Rerank 3.5 | In-Region | **Not available** |

Across all 138 models on the page, 25 are usable only from us-east-1 and 5 only from us-east-2 (DeepSeek V3.1, two Qwen3 models, two GPT-5.6 variants), none of which this project needs. Bedrock Guardrails, including the Standard tier, is available in both.

Co-location also buys no data-residency claim: from us-east-2, every current Claude model is reachable only through cross-Region inference, so prompts may be processed in other US Regions anyway.

Calling Bedrock in us-east-1 from compute in us-east-2 would work, but it splits region configuration around the dependency the product relies on most.

## Consequences

Positive:
- In-Region inference is available for Opus 5.5, Sonnet 5, and Haiku 4.5, so LLM calls can be kept inside a single Region where that matters.
- The full set of embedding and reranking options is available, including Cohere Rerank 3.5.
- A CloudFront front door can use an ACM certificate from the default provider, with no second provider block.
- No change to the scaffold: us-east-1 is already the default everywhere.

Negative:
- The organizer dataset stays in us-east-2, so anything that reads it crosses Regions.
- Fable 5.1 is only offered through cross-Region inference in either Region. If it is used, the calling role's IAM policy must allow the inference profile and the foundation model in every Region the profile can route to, not just us-east-1 (see [IAM policy requirements for Geographic cross-Region inference](https://docs.aws.amazon.com/bedrock/latest/userguide/geographic-cross-region-inference.html)).
- The availability table above is a snapshot. Bedrock's regional coverage changes often; re-check it before relying on a model that is not already in the table.
