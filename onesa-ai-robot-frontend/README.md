# Robot frontend (planned)

Independent application boundary; implementation, runtime and package manifest are
not yet selected. No build/start command or deployable image exists. Add a dedicated
Dockerfile, lockfile, tests and deployment contract when the implementation is approved.
See the repository build and deployment guides. Do not reuse a sibling build context.

Owner-provided [ONESA banner](public/social/onesa-banner.png) and [orbit favicon](public/brand/onesa-orbit.png) are prepared; see [branding instructions](../docs/engineering/BRANDING.md).

---

## Next.js Frontend Implementation

This frontend is now implemented using Next.js 14 with TypeScript and Tailwind CSS.
Vercel Web Analytics has been configured for tracking.

### Development

```bash
npm install
npm run dev
```

### Build

```bash
npm run build
```

### Lint

```bash
npm run lint
```
