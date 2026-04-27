# Esonero 1 - Software Engineering Lab

Project for the course **Software Engineering Lab**  
**Prof. Roberto Navigli** — **Dr. Domenico Fedele**

## Overview

This project implements an end-to-end pipeline for acquiring, parsing, evaluating, and serving documents from heterogeneous web sources.

The system is designed to:
- extract structured information from web pages belonging to assigned domains;
- clean and normalize textual content;
- evaluate parsing quality against a manually created **Gold Standard**;
- expose functionalities through a **REST API**;
- provide a **Web UI** for testing and interaction;
- run the entire system using **Docker Compose**.

This project contributes to a real-world AI application, supporting web-based information retrieval systems for LLMs.

---

## Project Objectives

The assignment requires the implementation of the following components:

### 1. Web Domain Parsers
Custom Python parsers for extracting relevant information from web pages belonging to assigned domains.

Each parser must return:

```json
{
  "url": "...",
  "domain": "...",
  "title": "...",
  "html_text": "...",
  "parsed_text": "..."
}
```
### 2. Gold Standard (GS)

A manually created dataset used as ground truth to evaluate parser performance.

At least 5 representative URLs per domain
Only relevant textual content (no ads, menus, or boilerplate)

Format:

```json
{
  "url": "...",
  "domain": "...",
  "title": "...",
  "html_text": "...",
  "gold_text": "..."
}
```
### 3. Parser Evaluation

The system evaluates parsing quality by comparing parser output with the Gold Standard.

Token-Level Evaluation (Mandatory)

Tokens are defined as lowercase words split by whitespace.

Precision
Recall
F1-score

Formulas:

```md
Precision = |extracted ∩ gold| / |extracted|
Recall = |extracted ∩ gold| / |gold|
F1 = 2 × (Precision × Recall) / (Precision + Recall)
Jaccard Similarity (Additional Metric)
```

We also implemented Jaccard Similarity to measure the overlap between extracted tokens and Gold Standard tokens:

```md
Jaccard = |extracted ∩ gold| / |extracted ∪ gold|
```

This metric provides a balanced measure of similarity by considering both false positives and false negatives.

Example output:

```json
{
  "token_level_eval": {
    "precision": 0.87,
    "recall": 0.91,
    "f1": 0.89
  },
  "jaccard_similarity": 0.82
}
```
### 4. REST API (FastAPI)

The backend exposes the following endpoints:

```md
GET /parse → Parse a given URL
GET /domains → Return the list of supported domains
GET /gold_standard → Return GS entry for a given URL
GET /full_gold_standard → Return all GS entries for a domain
POST /evaluate → Evaluate parsed text against GS
```

Example input:

```json
{
  "parsed_text": "...",
  "gold_text": "..."
}
```
```md
GET /full_gs_eval → Return aggregated evaluation over a domain
```
### 5. Web UI

The frontend provides:

URL input for parsing
Comparison between raw HTML and cleaned text
Dropdown menu with GS URLs
Evaluation results (Precision, Recall, F1, Jaccard)

### 6. Containerization

The entire system is containerized using Docker.

## Requirements:

Backend (FastAPI) exposed on port 8003
Frontend container
docker-compose.yaml to run everything with a single command
Only relative paths
Project Structure
```md
progetto/
├── docker-compose.yaml
├── domains.json
├── gs_data/
│   ├── domain_x_gs.json
│   └── domain_y_gs.json
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── src/
│       └── server.py
├── frontend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── src/
│       ├── frontend.py
│       └── templates/
└── report.pdf
```
# Installation & Usage

Run the project
```md
docker compose up --build
```

The system must start without any additional steps.

## Testing

The backend must pass the provided automatic test script.

Requirements:

Backend must be accessible on port 8003
The system must work immediately after:
```md
docker compose up --build
```

Expected output:

```md
ALL TESTS PASS!
```
Notes
```md
The project must run correctly on Ubuntu (Linux)
Do not use absolute paths
Ensure full reproducibility on a clean environment
The frontend is not automatically tested but must work correctly
Deliverables
Complete project folder
report.pdf (max 2 pages, written in LaTeX)
Submission as a single .zip file:
studentID1_studentID2_studentID3_lab_esonero_1.zip
Authors
Simone Santamaria 2108086
Francesco Saverio Cioeta 2108245
Matteo Priori 2143781
License
```

This project is developed for academic purposes only.


---
