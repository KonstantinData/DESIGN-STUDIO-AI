# Verified price evidence and USD 5 acceptance feasibility

Evidence retrieved on 2026-10-18 with normal TLS verification. No paid provider
request was made for this assessment. The prices below are published tariffs,
not actual invoice charges. Sources provide no separate effective-date field;
the recorded retrieval time is the evidence date, not an invented tariff date.

## Published prices

| Exact model entry | Input text / 1M | Input image / 1M | Output text / 1M | Output image / 1M |
| --- | ---: | ---: | ---: | ---: |
| `gpt-image-1.5` | USD 5.00 | USD 8.00 | USD 10.00 | USD 32.00 |
| `gpt-4.1-mini` | USD 0.40 | Same input-token rate | USD 1.60 | Not applicable |
| `gpt-4.1-mini-2025-04-14` | USD 0.40 | Same input-token rate | USD 1.60 | Not applicable |

Image rates are directly displayed on the official GPT Image 1.5 model page.
Responses rates are directly displayed on the GPT-4.1 Mini model page, which
explicitly lists both the alias and the 2025-04-14 snapshot. Register each exact
identity separately in a verified contract; do not infer arbitrary suffixes or
silently map unrelated snapshots. Ignore cache discounts for upperbounds.
The model pages mark older snapshots as deprecated. Read-only model listing
currently exposes the requested aliases, but only an actual separately approved
request can verify that these operations remain usable in the selected project.
The current general pricing page highlights newer image models; its rates must
not replace the older GPT Image 1.5 model's own explicit tariff.

The image-generation guide lists 1,568 output tokens for landscape medium
1536×1024 images in its older-model token table. At USD 32 per million this is
USD 0.050176, while the per-image price table rounds to USD 0.05. Input text
and reference images cost extra; USD 0.05 is not an all-inclusive call price.

## Source integrity

The earlier proxy-403 blockage was resolved by the operator's published network
configuration. The following successful HTTP-200 retrievals supersede that
blockage. Raw HTML evidence remains outside Git under `/tmp/studio-pricing-*`.

- [pricing](https://developers.openai.com/api/docs/pricing), fetched `2026-10-18T22:49:34.549603+00:00`, SHA-256 `2c1986b59d2d771893ac410ec4e5add17d68878fde413764019858b084641f66`.
- [mini](https://developers.openai.com/api/docs/models/gpt-4.1-mini), fetched `2026-10-18T22:49:34.824801+00:00`, SHA-256 `ad5b2685053fc7d42db4247a2a825f0b16103babf4b7153cf528efc68ff865b2`.
- [images](https://developers.openai.com/api/docs/guides/image-generation), fetched `2026-10-18T22:49:35.260589+00:00`, SHA-256 `e0f262151a2b82b024044787654b35e2d557f880568bde9d2c80b26520b5f53b`.
- [vision](https://developers.openai.com/api/docs/guides/images-vision), fetched `2026-10-18T22:49:35.487458+00:00`, SHA-256 `5333a14b31f9d1a69a6b8a3040757771f2987c2414ebd998026cc4a9873a7db7`.
- [image-model](https://developers.openai.com/api/docs/models/gpt-image-1.5), fetched `2026-10-18T22:49:35.708042+00:00`, SHA-256 `e4dca82bf965ab8d2287ea45622220b32e7d073d2800af2e96cec75ef1925ba0`.

## Costing-contract fields

Use decimal strings and exact model identity, following `app/costing.py`:

```json
{
  "gpt-image-1.5": {
    "kind": "image",
    "text_input_usd_per_million": "5.00",
    "image_input_usd_per_million": "8.00",
    "text_output_usd_per_million": "10.00",
    "image_output_usd_per_million": "32.00"
  },
  "gpt-4.1-mini": {
    "kind": "responses",
    "input_usd_per_million": "0.40",
    "output_usd_per_million": "1.60"
  },
  "gpt-4.1-mini-2025-04-14": {
    "kind": "responses",
    "input_usd_per_million": "0.40",
    "output_usd_per_million": "1.60"
  }
}
```

The private immutable runtime contract additionally requires currency, version,
verification timestamp, expiry, verifier, official source URL, and a separately
pinned SHA-256. This document is evidence, not a live spending switch or an
actual-billing record. Successful reported usage may release the difference
between the full reservation and its rounded-up verified-rate upperbound;
`actual_cost_cents` stays null until independent invoice reconciliation.
Malformed usage, missing image-input classification, missing model identity,
unrecognized model/rate or unknown transport outcomes retain the full ceiling.

## First three text concepts: bounded, independently admissible stage

Provider calls reserve 10 cents for briefing, 100 cents per image, and 10 cents
per curation. One briefing plus three images and their reviews reserves at most
USD 3.40 with no retry. This stage fits the separately authorized USD 5 cap even
if no usage-based release is possible.

For image generation without a reference, the complete prompt is capped at
32,000 Unicode characters. A conservative byte-level text-token bound is
128,000 UTF-8 bytes/tokens (four bytes per scalar). Published text input plus
1,568 image output tokens gives:

`128000 × 5 / 1000000 + 1568 × 32 / 1000000 = USD 0.690176`.

Even an additional engineering allowance of 1,000 text tokens remains below
USD 0.70 and the USD 1 reservation. This allowance is headroom, not an official
claim about hidden token framing. No image-input fee exists on this stage's
`images/generations` calls because no reference image is submitted.

Responses requests cap instructions, schema and textual input at 65,536 bytes,
brief output at 6,000 tokens, review output at 1,200. The current vision guide
explicitly documents GPT-4.1 Mini's 6,144-patch budget, 2,048-pixel maximum input
side and 1.62 multiplier, including applicability to the 2025-04-14 snapshot.
Taking `ceil(6144 × 1.62) + 1 = 9955` billable image input tokens conservatively
covers the guide's stated one-token rounding variation. With one image and an
additional 1,000-token engineering framing allowance, the bounds are:

- Briefing: `(65536+9955+1000) × 0.40 / 1M + 6000 × 1.60 / 1M = USD 0.0401964`.
- Curation: same input bound plus `1200 × 1.60 / 1M = USD 0.0325164`.

Both remain below the reserved 10 cents. A real text-only briefing has no image
and therefore costs less than this deliberately broad bound. These calculations
are planning bounds, never actual billed costs. The lead must still verify
kill-switch state, total in-flight exposure and runtime contract before making
any separately authorized paid request.

## Edits and complete fifteen-image acceptance

Current public input-token guidance explicitly labels its high-fidelity extra
4,160/6,240-token rule **GPT Image 1**. It does not explicitly extend that rule
to GPT Image 1.5. Do not copy those input counts to 1.5 by assumption. The current
image-generation guide focuses on newer models and does not supply a precise
1.5 high-fidelity input-token maximum for a 4,096-pixel reference.

Consequently the published rate is verified, but a strict worst-case pre-call
USD 1 ceiling for every supported 1.5 reference-image edit remains unproved by
these sources. Actual successful 1.5 image-token usage supports verified-price
settlement afterwards; it does not retroactively establish a pre-call bound.
Before the two real revisions, obtain a documented 1.5 input-token bound or a
separately justified narrower reference-input/model configuration. Do not lower
fidelity silently, discard the reference, or fabricate room-preservation claims.

Under full unreleased default reservations, five text-path images and reviews
cost USD 5.60 exposure and the full fifteen-image three-source plan USD 16.80.
Successful verified-usage settlements can reduce retained exposure, but a
complete five- or fifteen-image run under USD 5 is **not guaranteed** by the
first-stage calculation. Each later step must check remaining cap and account
for in-flight calls and unknown prior outcomes. No automatic retry may bypass
that reservation check.

## Optional reviewed GPT Image 1 edit path

No default model has been changed. If the lead chooses a mixed-model acceptance
run, the original A can be generated with GPT Image 1.5 and used as the image
reference for two independently requested GPT Image 1 revisions. This is an
explicit alternative, not an undocumented 1.5 input-token assumption. Quality
and spatial preservation still need real image review; use of a reference and
high fidelity cannot guarantee them.

The official [GPT Image 1 model page](https://developers.openai.com/api/docs/models/gpt-image-1)
returned HTTP 200 at `2026-10-18T22:56:07.957035+00:00`, SHA-256
`10c3a6914c82f0adf9830fd4f01d6bf64f6b04de5ca894f28082651f8ba85be9`.
It explicitly lists text input USD 5/M, image input USD 10/M and image output
USD 40/M. **Text output is unsupported; it has no published text-output tariff.**
Authenticated free `GET /v1/models/gpt-image-1` returned HTTP 200 and exact model
identity. This is not proof of successful edit permission or image quality.

The official vision guide's explicitly GPT Image 1 rules apply directly:
fit the reference within 2048 pixels, then reduce the shortest side to 512;
count 512-pixel tiles, with base 65 tokens and 129 per tile. High fidelity adds
4160 for square images or 6240 for portrait/landscape. A 1536×1024 A reference
becomes 768×512 for tile accounting: two tiles, giving
`65 + 2×129 + 6240 = 6563` input image tokens.

With maximum prompt bytes and medium landscape output:

`128000×5/1M + 6563×10/1M + 1568×40/1M = USD 0.76835`.

Adding 1,000 input-text tokens of engineering headroom gives USD 0.77335, below
the USD 1 ceiling. Check the reference dimensions before using that exact
calculation. A broader four-tile bound gives 6821 input-image tokens and
USD 0.77593 including the same headroom, still below USD 1.

Runtime use requires explicit lead selection, actual requested model identity
recorded as `gpt-image-1`, and a verified contract capable of representing a
model without text output. Do not invent a text-output tariff just to satisfy
an existing four-rate schema. A deliberately conservative all-output ceiling
of USD 40/M may be modeled only as that bound, not described as an official
text price; alternatively reject any nonzero text-output count and price all
supported output as image. No paid request or automatic model switch was made.

If every successful response returns complete valid usage and the verified
contract settles it, conservative rounded-up retained bounds are 70 cents per
initial 1.5 generation, 78 cents per GPT Image 1 edit, 5 cents for briefing and
4 cents per review. Five images then retain at most
`3×70 + 2×78 + 5×4 + 5 = 391` cents. After the three initial images settle,
retained exposure is at most 227 cents; admitting both subsequent image/review
reservations adds 220 cents, a transient 447 cents. This supports a scoped
five-image mixed-model plan below USD 5 under those explicit conditions.
Missing usage keeps the full reservation and may correctly block a later step.
This is not a promise that the full fifteen-image plan fits, or an invoice total.

## Project and approval evidence

Authenticated read-only `GET /v1/models` returned HTTP 200 listing both configured
models. This does not prove successful generation. No project header was
returned. Administrative project enumeration returned HTTP 403; no admin secret
was requested. The operator explicitly confirmed that the supplied application
key and enforced USD 25 hard-limit screenshot belong to `Design-Studio-AI`.
Project binding is accepted as that operator attestation. The operator separately
authorized a maximum USD 5 test run. The USD 25 project limit does not enlarge it.
