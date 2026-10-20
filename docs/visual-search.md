# Local picture search

Enable the optional CPU-only model service:

```bash
docker compose -f server/compose.yaml --profile vision up -d --build visual-recognition
docker compose -f server/compose.yaml up -d --build --no-deps api
```

The first start downloads pinned `openai/clip-vit-base-patch32` revision
`b527df4b30e5cc18bde1cc712833a741d2d8c362` (about 605 MB of weights)
into the separate `vision-models` Docker volume. Downloads need internet access;
subsequent inference is local. User images and embeddings are not persisted or
sent to an external vision provider. The service has no published host port.
Docker limits it to 2 CPUs and 2 GiB RAM, with one inference request at a time.
Allow additional host memory for the database, search, API and monitoring.
Health becomes ready only after model initialization.

Compose configures `CONTAINER_LOCAL_VISION_URL` (default
`http://visual-recognition:8010`). For a non-Docker API, set `LOCAL_VISION_URL`
to an internally accessible model endpoint; do not expose inference publicly.
The API still starts without this service; picture search returns a clean 503
and suggests text search when inference is unavailable.

`POST /api/v1/products/visual-search/` accepts a JPEG, PNG or WebP image up to
5 MiB / 16 megapixels and an optional normalized `focus_box`
`[ymin, xmin, ymax, xmax]`. It selects one subject at a time; ambiguous photos can offer up to three
possible item choices. These are classification suggestions, not detected
objects or object bounding boxes. Both narrow and wide images go through the same model.
Optional category, store and literal text-query filters narrow the candidates.

Uploads must pass both header verification and full pixel decoding. Truncated
JPEG data with valid headers returns a clean validation error, not HTTP 500.

Subject cosine >= 0.20 and a different-category margin >= 0.015 are heuristic
acceptance gates, not calibrated confidence. Unknown/weak predictions do not automatically search the catalog. The internal
model may offer up to three allowlisted product labels with cosine >= 0.20 and
within 0.04 of the top label. These suggestions require explicit selection;
responses use `selection_required=true`, no selected item and no search results.
Clients resubmit the same photo with the offered `candidate-…` item ID. Unoffered
IDs are rejected. Explicit selections are described as user selections, never
confirmed recognition. A photo with no eligible suggestions remains unknown. Up to 256 recent products in the recognized category are ranked by
image-to-description cosine; a 0.18 gate and 24-result cap apply. Eligibility
(visible, unblocked, active verified store) is rechecked after inference using
current authoritative product records. This bounded shortlist can miss older
inventory. Text embeddings have a bounded 2,048-entry in-memory cache.

This is **not image-to-product-photo matching**, OCR/ISBN lookup, multi-object
detection, or proof of product identity. A local model can still misclassify an
image, especially illustrations, cluttered scenes and unfamiliar categories.
Validate thresholds and taxonomy against representative production photos
before treating relevance as established. No raw cosine is shown as a match
percentage. No catalog match is preferable to unrelated fallback inventory.

API responses identify `method` (`local_clip` or `preset_metadata`) and provide
a user-facing `message`. Confidence and similarity percentages are null.
Presets are explicitly curated category/text examples, not AI recognition.
Anonymous picture search is scoped to 6 requests/minute per client identity
under the existing DRF throttling configuration. Internal calls have 2-second
connect and 15-second read timeouts; the model does not maintain a durable queue.

The browser uses only the same-origin `/api/*` proxy. Source files remain in
memory for selection requests, are cleared on reload, and late responses cannot
restore a cleared search. Existing theme variables style both light and dark
modes. The original uploaded book photo is required to verify that exact case;
a screenshot of the result page alone is not that source image.

The vocabulary includes “Suit jacket / blazer” with a worn-garment prompt.
That subject narrows candidates to suit/blazer/sport-coat/tailored-jacket catalog
text before semantic ranking; it does not fall back to arbitrary fashion items.
The UI distinguishes choosing a possible item, recognizing/selecting an item
without catalog matches, and being unable to identify any product. Suggestions
carry no calibrated confidence or invented object coordinates.

## Picture-search item-type precision

Recognized product labels are narrowed by bounded, whole-word title patterns in
`product.visual_retrieval` before semantic ranking. Broad catalog categories such
as Fashion are not sufficient evidence of a matching item type. Footwear accepts
shoe/sneaker/boot/loafer/Oxford/derby/brogue and related names, while a parka whose
description mentions shoes is excluded. Selected accessories/compound names are
excluded where they contradict the requested item (shoe-care kit, watch strap,
and dress shoes when searching dresses).

The same constraint is reapplied when hydrating ranked records, alongside current
visibility, moderation, store, category and query checks. Unknown labels fail
closed. If eligible inventory is absent, return no results; do not refill from
unrelated category stock. This is a precision guard on catalog titles, not
image-to-product-photo matching. Valid products without a recognizable item-type
name in their title can be omitted; accurate structured catalog metadata remains
important. No seed/database records are rewritten by picture search.
