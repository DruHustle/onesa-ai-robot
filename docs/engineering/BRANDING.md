# Robot interface branding

Owner supplied the ONESA banner and orbit mark on 2026-10-10. Original image bytes
are preserved independently in this repository:

- `onesa-ai-robot-frontend/public/social/onesa-banner.png`: website/link preview,
  PNG, 1536 × 1024; use Open Graph and Twitter `summary_large_image` metadata.
- `onesa-ai-robot-frontend/public/brand/onesa-orbit.png`: favicon, PNG, 972 × 882;
  browsers scale the supplied image. The original screenshot includes the cursor.
- `onesa-ai-robot-frontend/public/brand/sources.json`: dimensions and SHA-256 provenance.

The public product and authenticated software simulator are implemented. The
October 13 production baseline is recorded in the root CHANGELOG and restricted
deployment receipts. The current public root uses an original static synthetic-joint
SVG with descriptive text and no private telemetry. This illustration makes no
physical robot achievement claim. Its source is in `public/index.html`.

## Shared foundation and Robot identity — 2026-10-14

Both product and `/console` consume shared Onesa design artifact `1.0.0`, pinned by
`design-system.consumer.json`. A teal product accent identifies Robot; safety statuses
use shared semantic roles and explicit text. The operator shell has protected,
simulation and runtime-sourced deployment labels, stable units and observation times.
Browser titles identify Onesa AI Robot independently of color.

Appearance follows CSS `prefers-color-scheme`, with readable light fallback, dark
roles, native controls, forced colors, reduced motion and print mappings. The previous
visitor-clock schedule and old stored/selector behavior are superseded. No script,
timer or appearance preference is retained. Shared artifact updates require deliberate
verified adoption and each consumer's independent release.

The owner-supplied favicon bytes remain unchanged. Browser-tab legibility and a
potential approved square product derivative require separate visual inspection;
the original non-square image is not claimed to be an optimized multi-size icon set.
