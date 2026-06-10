---
name: liteparse
description: Use this skill when the user asks to parse, perform multi-format document conversion or spatially extract text from an unstructured file (PDF, DOCX, PPTX, XLSX, images, etc.) locally without cloud dependencies.
compatibility: Requires Node 18+ and `@llamaindex/liteparse` installed globally via Homebrew (`brew install run-llama/liteparse/llamaindex-liteparse`)
license: MIT
metadata:
  author: LlamaIndex (wrapper by dotfiles)
  version: "0.2.0"
---

# LiteParse Skill (with OCR Server Management)

Parse unstructured documents (PDF, DOCX, PPTX, XLSX, images, and more) locally with LiteParse.
This wrapper adds automatic EasyOCR server management via Docker for reliable OCR.

---

## Step 0 — OCR Server Setup (BEFORE any parse command that needs OCR)

Before running any `lit parse` or `lit batch-parse` command that requires OCR
(i.e. when `--no-ocr` is NOT used), you MUST start the EasyOCR server:

```bash
~/Development/private/dotfiles/scripts/ocr-server.sh start
```

If the script succeeds, add `--ocr-server-url http://localhost:8828/ocr --num-workers 1`
to all `lit parse` and `lit batch-parse` commands. The `--num-workers 1` is critical:
the EasyOCR server is single-threaded, so sending parallel requests causes timeouts.

### If the OCR server fails to start

The script will print an error with options. Present these to the user:

1. **Docker not running**: Ask the user to start Docker Desktop, then retry.
2. **Tesseract fallback**: Run `lit parse` WITHOUT `--ocr-server-url`.
   This uses built-in Tesseract.js and requires `TESSDATA_PREFIX` to be set
   (should be configured in `~/.zshrc` pointing to `~/.local/share/tessdata`).
   If tessdata files are missing, run: `task -d ~/Development/private/dotfiles ocr:provision-tessdata`
3. **Disable OCR entirely**: Use `--no-ocr` flag (fastest, but no text from images/scans).

### After parsing is complete

Always stop the OCR server when done:

```bash
~/Development/private/dotfiles/scripts/ocr-server.sh stop
```

---

## Step 1 — Verify LiteParse Installation

```bash
lit --version
```

For Office document support (DOCX, PPTX, XLSX), LibreOffice is required.
For image parsing, ImageMagick is required.
Both are managed via the dotfiles Brewfile.

---

## Step 2 — Parse Documents

### Parse a Single File (with OCR server)

```bash
lit parse document.pdf --ocr-server-url http://localhost:8828/ocr --num-workers 1

# JSON output
lit parse document.pdf --format json -o output.json --ocr-server-url http://localhost:8828/ocr --num-workers 1

# Specific page range
lit parse document.pdf --target-pages "1-5,10,15-20" --ocr-server-url http://localhost:8828/ocr --num-workers 1

# Swedish document
lit parse document.pdf --ocr-server-url http://localhost:8828/ocr --ocr-language sv --num-workers 1

# Without OCR (text-only PDFs, Office docs)
lit parse document.pdf --no-ocr
```

### Batch Parse a Directory

```bash
lit batch-parse ./input ./output --recursive --format json --ocr-server-url http://localhost:8828/ocr --num-workers 1

# Without OCR
lit batch-parse ./input ./output --recursive --format json --no-ocr
```

### Generate Page Screenshots

```bash
lit screenshot document.pdf -o ./screenshots
lit screenshot document.pdf --pages "1,3,5" -o ./screenshots --dpi 300 --format png
```

---

## Step 3 — Key Options Reference

### OCR Options

| Option | Description |
|--------|-------------|
| `--ocr-server-url <url>` | Use EasyOCR server (default when server is running) |
| `--ocr-language <lang>` | OCR language: `en`, `sv`, `no`, `da`, etc. |
| `--no-ocr` | Disable OCR entirely |
| `--num-workers <n>` | Parallel OCR workers (default: CPU cores - 1) |

### Output Options

| Option | Description |
|--------|-------------|
| `--format json` | Structured JSON with bounding boxes |
| `--format text` | Plain text (default) |
| `-o <file>` | Save output to file |

### Performance / Quality Options

| Option | Description |
|--------|-------------|
| `--dpi <n>` | Rendering DPI (default: 150; use 300 for high quality) |
| `--max-pages <n>` | Limit pages parsed |
| `--target-pages <pages>` | Parse specific pages (e.g. `"1-5,10"`) |
| `--no-precise-bbox` | Disable precise bounding boxes (faster) |
| `--skip-diagonal-text` | Ignore rotated/diagonal text |
| `--preserve-small-text` | Keep very small text that would otherwise be dropped |

---

## Step 4 — Using a Config File

For repeated use, create a `liteparse.config.json`:

```json
{
  "ocrServerUrl": "http://localhost:8828/ocr",
  "ocrLanguage": "en",
  "outputFormat": "json",
  "dpi": 150,
  "preciseBoundingBox": true
}
```

Use with:

```bash
lit parse document.pdf --config liteparse.config.json
```

---

## Supported Input Formats

| Category | Formats |
|----------|---------|
| PDF | `.pdf` |
| Word | `.doc`, `.docx`, `.docm`, `.odt`, `.rtf` |
| PowerPoint | `.ppt`, `.pptx`, `.pptm`, `.odp` |
| Spreadsheets | `.xls`, `.xlsx`, `.xlsm`, `.ods`, `.csv`, `.tsv` |
| Images | `.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.tiff`, `.webp`, `.svg` |

Office documents require LibreOffice; images require ImageMagick.
LiteParse auto-converts these formats to PDF before parsing.

---

## Supported OCR Languages

The EasyOCR server supports 80+ languages. Pre-configured defaults: English (`en`),
Swedish (`sv`), Norwegian (`no`), Danish (`da`).

The Tesseract fallback supports: English (`eng`), Swedish (`swe`),
Norwegian (`nor`), Danish (`dan`).
