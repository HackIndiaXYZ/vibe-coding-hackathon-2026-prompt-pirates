# RxLens — Frontend

Next.js 15 web interface for the RxLens prescription analysis platform. Handles image upload, real-time analysis progress, safety report display, and local history.

---

## Table of Contents

- [Overview](#overview)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Architecture](#architecture)
- [Routes](#routes)
- [Key Components](#key-components)
- [Hooks](#hooks)
- [Data Layer](#data-layer)
- [State & Caching](#state--caching)
- [Environment Variables](#environment-variables)

---

## Overview

The frontend is a Next.js 15 App Router application. It communicates exclusively with the FastAPI backend over HTTP — it does no AI or OCR work itself. The two-phase flow (upload → analyse) is managed entirely on the client using custom hooks, with results persisted to `localStorage` for 24-hour access without re-fetching.

---

## Tech Stack

| Concern | Library |
|---|---|
| Framework | Next.js 15 (App Router) |
| Language | TypeScript 5 |
| Styling | Tailwind CSS 3 |
| UI Primitives | Radix UI + shadcn/ui |
| Animation | Framer Motion 11 |
| Data Fetching | TanStack Query v5 (React Query) |
| HTTP Client | Axios |
| Icons | Lucide React |
| Toasts | Sonner |
| File Drop | react-dropzone |
| Themes | next-themes |

---

## Project Structure

```
src/
├── app/                        # Next.js App Router pages
│   ├── layout.tsx              # Root layout — Navbar, Providers, Toaster
│   ├── page.tsx                # Landing page (/)
│   ├── error.tsx               # Global error boundary
│   ├── not-found.tsx           # 404 page
│   ├── upload/
│   │   ├── layout.tsx          # Upload layout wrapper
│   │   └── page.tsx            # Upload & analysis flow (/upload)
│   ├── results/
│   │   └── [id]/
│   │       ├── layout.tsx      # Results layout wrapper
│   │       └── page.tsx        # Safety report display (/results/:id)
│   └── history/
│       ├── layout.tsx          # History layout wrapper
│       └── page.tsx            # Past prescriptions list (/history)
│
├── components/
│   ├── shared/
│   │   ├── Navbar.tsx          # Top navigation bar
│   │   └── Providers.tsx       # QueryClientProvider + ThemeProvider
│   ├── ui/                     # shadcn/ui primitives
│   │   ├── button.tsx
│   │   ├── badge.tsx
│   │   ├── progress.tsx
│   │   └── separator.tsx
│   ├── upload/
│   │   ├── DropZone.tsx        # Drag-and-drop file input
│   │   └── UploadProgress.tsx  # Upload/OCR stage progress bar
│   └── results/
│       ├── MedicineCard.tsx    # Per-medicine expandable card
│       ├── ReportSummary.tsx   # Aggregate stats (total meds, warnings)
│       ├── WarningBanner.tsx   # Drowsiness / dosage / age warning banners
│       ├── OcrTextPanel.tsx    # Collapsible raw vs. cleaned OCR text
│       ├── SeverityBadge.tsx   # Colour-coded Low/Medium/High/Critical badge
│       └── ResultSkeleton.tsx  # Loading skeleton for the results page
│
├── hooks/
│   ├── useUpload.ts            # Upload state machine (idle → uploading → ocr → refining → done)
│   └── useAnalysis.ts          # Analysis state machine + animated per-medicine progress
│
├── lib/
│   ├── api.ts                  # Axios instance + all typed API call functions
│   ├── cache.ts                # localStorage read/write for 24-hour result caching
│   ├── medicines.ts            # Client-side medicine list deduplication / cleaning
│   ├── queryClient.ts          # TanStack Query client config + query key factories
│   └── utils.ts                # cn(), severity colours, confidence formatting
│
└── types/
    └── api.ts                  # TypeScript interfaces mirroring backend schemas
```

---

## Architecture

The frontend is a purely client-driven SPA built on the Next.js App Router. There are no server actions or API routes — all data flows through the FastAPI backend.

### Two-phase upload flow

```
User drops image
      │
      ▼
useUpload hook
  POST /api/v1/upload  ──► OCR on server ──► detected_medicines[]
      │
      ▼ (auto-triggers after upload succeeds)
useAnalysis hook
  POST /api/v1/analysis  ──► per-medicine LLM analysis ──► FullAnalysisResponse
      │
      ▼
Cache to localStorage (24 h)  +  React Query cache
      │
      ▼
Navigate to /results/:id
```

### Query strategy

TanStack Query is used for all GET requests (results page, history page). The results page checks `localStorage` first for instant render, then fires the query in the background to validate freshness. History merges backend entries with any locally-cached IDs that haven't synced.

### Security headers

`next.config.ts` applies `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, and `Referrer-Policy: strict-origin-when-cross-origin` to every route.

---

## Routes

| Route | Page | Description |
|---|---|---|
| `/` | `app/page.tsx` | Landing page — hero, how-it-works steps, feature list, disclaimer |
| `/upload` | `app/upload/page.tsx` | Two-phase upload + analysis flow |
| `/results/:id` | `app/results/[id]/page.tsx` | Full safety report for a prescription ID |
| `/history` | `app/history/page.tsx` | List of past prescriptions from backend + localStorage |

All pages use `"use client"` and Framer Motion `fadeUp` / `stagger` variants for entry animations.

---

## Key Components

### `DropZone`
Wraps `react-dropzone`. Accepts `.jpg`, `.jpeg`, `.png`, `.tiff`, `.bmp`, `.webp`. Calls the `onFileSelect` callback with the `File` object; all upload logic lives in the hook, not here.

### `UploadProgress`
Renders four stages: `uploading` (network progress bar), `ocr` (server processing), `refining` (LLM name correction), and `done` / `error`. Each stage has its own icon and copy.

### `MedicineCard`
Expandable card rendered for each medicine in the analysis result. Shows:
- Name, drug class, severity badge
- Plain-English explanation and use case
- Side effects (common + serious)
- Dosage info and notes
- Drowsiness flag, age warnings, contraindications
- RAG source attribution if present

### `ReportSummary`
Grid of aggregate stat cards: total medicines, drowsiness warning, dosage concern, age warning, provider used, OCR confidence.

### `WarningBanner`
Renders up to three sticky banners (drowsiness / dosage concern / age warning) only when the corresponding flags on `FullAnalysisResponse` are true.

### `SeverityFilter`
Button-group filter on the results page that filters `MedicineCard` list by severity level. Only shows severity levels that have at least one medicine.

---

## Hooks

### `useUpload`

Manages the upload state machine. Tracks:

- `stage`: `idle | uploading | ocr | refining | done | error`
- `uploadProgress`: 0–100 (network progress mapped to 0–70; server OCR phase fakes 70→100)
- `error`: human-readable error from `parseApiError()`
- `result`: `UploadResponse | null`

Exposes `upload(file)` and `reset()`.

### `useAnalysis`

Manages the analysis state machine. Tracks:

- `stage`: `idle | analysing | loading | done | error`
- `progress`: 0–100 (animated per-medicine as the request runs)
- `currentMedicine`: name of the medicine currently being shown as "in progress" in the UI
- `error`: error string on failure

Before calling the backend, it runs `cleanMedicineList()` on the detected medicines list to deduplicate and strip OCR artefacts (e.g. "Tab.", "Cap." prefixes, duplicates).

On success, it writes to both the React Query cache and `localStorage` via `cacheResult()`.

---

## Data Layer

### `src/lib/api.ts`

Central Axios instance configured with:

- `baseURL`: `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`)
- `timeout`: 5 minutes globally, overridden to 8 minutes for `POST /api/v1/analysis`

Exported functions:

| Function | Method | Endpoint |
|---|---|---|
| `uploadPrescription(file, onProgress?)` | POST | `/api/v1/upload` |
| `analysePresciption(request)` | POST | `/api/v1/analysis` |
| `getAnalysis(id, age?, lang?)` | GET | `/api/v1/analysis/:id` |
| `listPrescriptions(limit, offset)` | GET | `/api/v1/prescriptions` |
| `getPrescription(id)` | GET | `/api/v1/prescriptions/:id` |
| `getHealth()` | GET | `/api/v1/health` |
| `getModels()` | GET | `/api/v1/health/models` |

`parseApiError(error)` normalises Axios errors to user-friendly strings (handles 404, 413, 422, 429, 5xx, network down, timeout).

### `src/lib/medicines.ts`

Client-side preprocessing before the medicine list reaches the backend:

- Strips common prefix noise (`Tab.`, `Cap.`, `Inj.`, `Syp.`)
- Deduplicates case-insensitively
- Filters very short tokens (likely OCR garbage)

### `src/types/api.ts`

TypeScript interfaces that mirror the Pydantic schemas on the backend: `UploadResponse`, `AnalysisRequest`, `MedicineAnalysis`, `FullAnalysisResponse`, `PrescriptionSummary`, `PrescriptionListResponse`, `HealthResponse`, `CachedResult`.

---

## State & Caching

Results are stored in `localStorage` under the key `rxlens:result:<id>` as a JSON blob containing the `UploadResponse` and `FullAnalysisResponse`. Entries expire after 24 hours. The history page reads all `rxlens:result:*` keys, merges them with the backend list, and de-duplicates by prescription ID.

React Query caches GET responses with `staleTime: 10 minutes` for results and `2 minutes` for the history list.

---

## Environment Variables

Copy `.env.local.example` to `.env.local` and set:

| Variable | Default | Description |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Full base URL of the FastAPI backend. No trailing slash. Change this for staging/production deployments. |

For production deployments (e.g. Vercel), set `NEXT_PUBLIC_API_URL` to your backend's public URL in the project's environment variable settings. The `vercel.json` file in the repo is pre-configured for Vercel deployment with no extra steps.
