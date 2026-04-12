# Script Tools

`scripts/` contains auxiliary tooling for demo data generation, environment bootstrap, and optional competition document exports.

The main frontend lives in `frontend/`. The Node package manifest was moved here on purpose because its dependencies are only used by the document export scripts:

- `gen_overview.js`
- `gen_detail.js`
- `gen_ppt.js`

Common commands:

```bash
npm install --prefix scripts
python -m pip install Pillow
npm --prefix scripts run diagrams
npm --prefix scripts run overview -- output.docx
npm --prefix scripts run detail -- output.docx
npm --prefix scripts run slides -- output.pptx
```

Generated diagram assets are written to `scripts/diagrams/`.
