# OpenAI transport contract

Inspected on 2026-10-18. This describes implementation and offline transport
tests. **No paid API request, real render or real vision quality evaluation has
been performed.** An authenticated read-only `GET /v1/models` returned HTTP 200
and listed `gpt-image-1.5` and `gpt-4.1-mini`. Model listing does not prove
successful image generation. Response headers provided no project identity.
`GET /v1/organization/projects` returned HTTP 403; this administrative API is
not accessible using the supplied application credential. No admin key is
requested. The operator subsequently confirmed that the supplied key and
enforced USD 25 hard-limit screenshot belong to `Design-Studio-AI`; project
binding is accepted as that explicit operator attestation, not as API evidence.

## Official sources checked

The direct API-reference sites returned `Tunnel connection failed: 403 Forbidden`
through this environment's proxy. The following official OpenAI repository
sources were successfully retrieved with TLS verification (HTTP 200):

- [Image generation parameters](https://raw.githubusercontent.com/openai/openai-python/main/src/openai/types/image_generate_params.py)
- [Image edit parameters](https://raw.githubusercontent.com/openai/openai-python/main/src/openai/types/image_edit_params.py)
- [Responses parameters](https://raw.githubusercontent.com/openai/openai-python/main/src/openai/types/responses/response_create_params.py)

These generated specification files list `gpt-image-1.5`, `quality=medium`,
`size=1536x1024`, and `output_format=png`. GPT Image returns base64 image data;
the obsolete `response_format` parameter is deliberately omitted. Image editing
uses multipart PNG/JPEG/WebP inputs. `input_fidelity=high` is sent for
`gpt-image-1` and `gpt-image-1.5` only. Responses supports `store=false`,
instructions, and output-token limits. These checks establish schema alignment,
not successful account access or semantic correctness.

Structured requests explicitly select the default service tier, permit at most
64 KiB of instructions, schema and textual input, and cap output at 6,000 tokens
for briefing or 1,200 for curation. Image prompt length is capped at 32,000
characters. These are resource bounds, not independently verified price ceilings.

## Invocation and data boundaries

`Provider.brief`, `Provider.render`, and `Provider.curate` each issue at most
one HTTP request, with no internal retry. The orchestration layer must reserve
budget before **every** invocation, including failed attempts, review requests
and any one explicitly allowed image retry. The transport cannot independently
prove project hard-limit enforcement or approve spending. It cannot enable a
live run by the mere presence of a key.

The server-only key is read from `STUDIO_OPENAI_API_KEY`; `OPENAI_API_KEY` is
accepted as a local compatibility fallback. Text and image models use
`OPENAI_TEXT_MODEL` (default `gpt-4.1-mini`) and `OPENAI_IMAGE_MODEL` (default
`gpt-image-1.5`). API origin is fixed to `https://api.openai.com/v1/`; redirects
are disabled for the managed client. No upstream bodies, prompts, tokens,
images or secret values appear in exception messages.

Briefing produces one shared versioned room, explicit feature provenance,
assumptions and three distinct concept profiles. Image input is first analyzed
as photo or floorplan; `usable=false` prevents image rendering. Local MIME and
size checks supplement semantic analysis. Input images are Pillow-verified and
limited to 4096 pixels per side before any request. Every generated PNG is base64-validated,
bounded to 25 MiB and verified by Pillow before returning. This is file
integrity validation, not architectural acceptance.

Initial text renders use the same shared room description. Photo/floorplan
renders use the supplied source as an image-edit reference. Targeted changes
use the chosen revision as a reference; layout-preservation instructions alone
cannot guarantee exact geometric fidelity. The parent workflow must retain
room/concept revision identity and preserve original references.

Vision review returns exactly three nonempty single-line descriptions and a
critical-error flag with a reason. It is **shadow evidence only**. Expose critical
flags to operators and users with their reasons; never convert a false flag
into an assertion of verified room fidelity. Human source-versus-render review
remains necessary for product acceptance. A critical room error cannot count as
a successfully accepted design.

## Proven local validation failures

HTTP failures expose only a fixed status, a finite diagnostic classification,
allowlisted upstream error codes/types and a format-validated request ID via
`ProviderError.safe_diagnostics()`. For example a 403 explicitly mentioning
organization verification maps to `organization_verification_required` without
retaining or displaying the upstream message. Worker reservation records retain
these safe fields while keeping actual cost unknown and the conservative
reservation charged. This allows diagnosing write permissions even when free
model listing succeeded, without a blind paid retry or content disclosure.

`ProviderPreflightError` identifies locally rejected input before a transport
attempt: unsupported source kind, invalid image, image/text bounds or invalid
concept. Only this classification allows a reservation to be released without
retaining unknown-cost exposure. Provider HTTP errors, timeouts, response-schema
errors and invalid returned images remain ordinary `ProviderError` even when
their diagnosis resembles an input-validation failure. Response-side MIME
validation is explicitly wrapped into the ordinary error class.

## Usage versus cost

Successful structured responses include `_provider_usage` and
`_provider_request_id`, plus `_provider_model` from the upstream Responses model
field and `_provider_model_identity_source="response"`. Missing upstream model
identity remains null; configured aliases are not substituted. `RenderedImage`,
a `bytes` subclass, has `.usage`, `.request_id`, `.model` and
`.model_identity_source`. The official ImagesResponse schema contains no model
field, so its identity is the exact request model with source `"request"`,
never described as a returned model identity. Usage is the provider's returned raw token accounting, **not
actual billed USD**. Missing usage is unknown, not zero. Failed or disconnected
requests may still incur charges. Reservations must remain conservatively
accounted for when actual usage is unavailable. Any price-based calculation
must be labeled an estimate with its model, effective price source and date;
billing reconciliation is a separate operation. No monetary precision or
actual-cost claim is derived from these offline tests.

Official usage contracts inspected with HTTP 200 on 2026-10-18:

- [Image usage](https://raw.githubusercontent.com/openai/openai-python/main/src/openai/types/images_response.py):
  `input_tokens`, `input_tokens_details.text_tokens` and `.image_tokens`,
  `output_tokens`, `total_tokens`; optional `output_tokens_details.text_tokens`
  and `.image_tokens`. Usage itself is optional. Never synthesize missing counts.
- [Responses usage](https://raw.githubusercontent.com/openai/openai-python/main/src/openai/types/responses/response_usage.py):
  `input_tokens`, `output_tokens`, `total_tokens`, input cache details and
  output reasoning details. Billing upperbounds may conservatively ignore
  cache discounts only with an official applicable tariff.

Malformed counts, missing image-input classification, missing model identity or
unrecognized model/rates must keep the entire reservation. If image-output
classification is absent, a verified-rate upperbound may assign every output
token the larger applicable output rate. Such a bound remains distinct from
invoice reconciliation; it does not establish actual billed cost.
