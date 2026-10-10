# Robot interface branding

Owner supplied the ONESA banner and orbit mark on 2026-10-10. Original image bytes
are preserved independently in this repository:

- `onesa-ai-robot-frontend/public/social/onesa-banner.png`: website/link preview,
  PNG, 1536 × 1024; use Open Graph and Twitter `summary_large_image` metadata.
- `onesa-ai-robot-frontend/public/brand/onesa-orbit.png`: favicon, PNG, 972 × 882;
  browsers scale the supplied image. The original screenshot includes the cursor.
- `onesa-ai-robot-frontend/public/brand/sources.json`: dimensions and SHA-256 provenance.

The frontend runtime is not implemented. These are prepared assets; no live robot
page, favicon route or social preview exists yet. When the approved interface is
implemented, serve these public paths and use `https://robot.onesa.eu` as its
metadata base. Keep assets in this repository rather than importing sibling source.
No generated reinterpretation, image edit or license assignment was made.
