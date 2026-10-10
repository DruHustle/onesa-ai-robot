# Robot frontend preview

A dependency-free static visual preview uses the same navy, cyan, typography and
orbit motif as the Onesa company homepage. It is not a connected robot application:
authentication, telemetry, commands and safety qualification are not implemented.
The page is marked noindex until a real release is approved.

Preview locally from this frontend directory:

```bash
python3 -m http.server 3431 --bind 127.0.0.1 --directory public
```

Open http://127.0.0.1:3431. No compilation or package installation is needed for
this preview; `public/index.html` and `public/theme.css` are its source. A working
robot runtime/backend and deployment contract remain pending. Do not expose a
robot listener or represent the static status cards as live device measurements.

Owner-provided assets remain in `public/brand` and `public/social`; see
[branding instructions](../docs/engineering/BRANDING.md).
