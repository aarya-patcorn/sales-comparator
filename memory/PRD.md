# Kamdhenu Adhesives — Sales Comparator Tool (PRD)

## Overview
Mobile-first internal tool for Kamdhenu Adhesives sales reps to recommend the right product for any tile installation and produce a side-by-side pitch vs MYK Laticrete, Roff, Mapei, and Kerakoll.

## Core Flow (per uploaded flowchart)
1. **Login** — Emergent Google OAuth (or "Continue as Dev" for testing)
2. **Substrate** — pick from 15 substrates (Concrete, Plywood, Gypsum, Tile-on-Tile, etc.)
3. **Tile Type** — filtered list of compatible tile types per substrate
4. **Tile Size** — standard sizes for the chosen tile type
5. **Application Area** — Kitchen / Bathroom / Outdoor / Pool / Industrial / etc.
6. **Recommendation** — Kamdhenu product (K50, K60, K80, K90, KX) with reasoning + key specs
7. **Select Competitors** — pre-checked closest matches per brand + add custom
8. **Comparison** — GSMArena-style horizontal table with Kamdhenu column highlighted
9. **AI Sales Pitch** — GPT-5.2 generated 3 punchy one-liners per competitor citing exact param differences (cached in MongoDB)

## Stack
- Frontend: Expo Router (React Native), red+white B2B theme
- Backend: FastAPI + Motor + MongoDB
- Auth: Emergent-managed Google OAuth (`/api/auth/session`, `/api/auth/me`)
- AI: GPT-5.2 via Emergent LLM key (`emergentintegrations.llm.chat.LlmChat`)

## Key Endpoints
- `GET /api/catalog/{substrates|tile-types|areas|kamdhenu|competitors}`
- `POST /api/recommend` → returns Kamdhenu product code + reasoning
- `POST /api/compare` → returns columns + parameter rows for the table
- `POST /api/pitch` → returns AI-generated per-competitor pitch lines (cached)
- `POST /api/admin/products` → auth-gated custom product addition

## Data Sources
- `Substarte & Tiles.xlsx` — 15 substrates + 14 tile types (with sizes)
- `Infinia_TDS_merged.pdf` — full TDS for K50/K60/K80/K90/KX
- `Competitor Product.xlsx` — MYK Laticrete, Roff, Mapei, Kerakoll product range with IS/EN type mapping

## Deferred (Phase 2 per user choice)
- Coverage Calculator
- Pricing Tool
- Share/Export PDF

## Smart Business Enhancement
**AI Sales Pitch** — instead of a static "we are better" banner, every comparison auto-generates fresh, quantitative talking points (e.g., "K80 covers 5-6 m² per 20kg vs Keraflex 4-5 m² — up to 50% more area per bag") that sales reps can read straight off the screen. Cached in MongoDB so repeat opens are instant. This is the unique sales weapon competitors can't easily replicate.
