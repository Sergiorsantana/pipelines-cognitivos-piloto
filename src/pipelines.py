# -*- coding: utf-8 -*-
"""
Implementação real (executável) dos três pipelines comparados na Seção 5.2:

  1) ETL tradicional   -> mapeamento de esquema FIXO, transformação linha a
                           linha ANTES da carga (streaming, lotes de 500).
  2) ELT (Data Lake)    -> mapeamento de esquema FIXO, carga do dado bruto
                           primeiro (JSON em SQLite), transformação vetorizada
                           em lote (pandas) DEPOIS da carga.
  3) Ecossistema Cognitivo -> mapeamento SEMÂNTICO (TF-IDF + fallback difflib,
                           simulando um agente que resolve schema drift),
                           parsing adaptativo multi-formato de data/valor.

Todas as três leem o MESMO dataset de origem por execução (gerado por
data_generator.py), garantindo comparação justa (mesma carga, mesmas regras
de negócio-alvo, mesma máquina).
"""
import json
import sqlite3
import time
from difflib import SequenceMatcher

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from data_generator import CANONICAL_FIELDS, FIELD_DESCRIPTIONS, SYNONYMS

BATCH_SIZE = 500
FIXED_MAPPING = {field: syns[0] for field, syns in SYNONYMS.items()}  # nome "contratado"


# ----------------------------------------------------------------------
# Utilidades de parsing
# ----------------------------------------------------------------------
def _parse_date_strict_iso(s):
    import datetime as dt
    try:
        return dt.datetime.strptime(s, "%Y-%m-%d").date().isoformat()
    except Exception:
        return None


def _parse_date_adaptive(s):
    import datetime as dt
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return dt.datetime.strptime(s, fmt).date().isoformat()
        except Exception:
            continue
    return None


def _parse_amount_strict(s):
    try:
        return float(s)
    except Exception:
        return None


def _parse_amount_adaptive(s):
    s2 = str(s).strip()
    for candidate in (s2, s2.replace(",", ".")):
        try:
            return float(candidate)
        except Exception:
            continue
    return None


def _clean_text_strict(s):
    return s if isinstance(s, str) else None


def _clean_text_adaptive(s):
    if not isinstance(s, str):
        return None
    return s.strip().lower()


# ----------------------------------------------------------------------
# Mapeamento semântico (stand-in offline/determinístico para um agente LLM
# de mapeamento de schema em um RAG de metadados: TF-IDF + cosseno, com
# fallback de similaridade de string quando a confiança é baixa)
# ----------------------------------------------------------------------
def semantic_schema_mapping(source_columns):
    canon_texts = [FIELD_DESCRIPTIONS[f] for f in CANONICAL_FIELDS]
    src_texts = [c.replace("_", " ") for c in source_columns]

    vectorizer = TfidfVectorizer()
    corpus = canon_texts + src_texts
    tfidf = vectorizer.fit_transform(corpus)
    canon_vecs = tfidf[:len(canon_texts)]
    src_vecs = tfidf[len(canon_texts):]

    sim = cosine_similarity(canon_vecs, src_vecs)  # (n_fields, n_cols)

    mapping = {}
    used_cols = set()
    low_confidence_retries = 0
    order = np.argsort(-sim.max(axis=1))  # resolve campos mais confiantes primeiro
    for idx in order:
        field = CANONICAL_FIELDS[idx]
        row = sim[idx].copy()
        for j, col in enumerate(source_columns):
            if col in used_cols:
                row[j] = -1
        best_j = int(np.argmax(row))
        best_score = row[best_j]

        if best_score < 0.15:
            # fallback: "segunda chamada de ferramenta" via fuzzy string match
            low_confidence_retries += 1
            scores = [
                SequenceMatcher(None, field, c).ratio() if c not in used_cols else -1
                for c in source_columns
            ]
            best_j = int(np.argmax(scores))

        chosen_col = source_columns[best_j]
        mapping[field] = chosen_col
        used_cols.add(chosen_col)

    return mapping, low_confidence_retries


# ----------------------------------------------------------------------
# Pipeline 1: ETL tradicional (mapeamento fixo, transforma-antes-de-carregar)
# ----------------------------------------------------------------------
def run_etl(rows, column_map_truth, conn, sample_interval_records=None):
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS etl_output")
    cur.execute("""CREATE TABLE etl_output (
        customer_id TEXT, full_name TEXT, email TEXT,
        purchase_date TEXT, amount TEXT, category TEXT, country TEXT
    )""")
    conn.commit()

    t_start = time.perf_counter()
    first_result_latency_ms = None

    correct_field_maps = sum(
        1 for f, src in FIXED_MAPPING.items()
        if column_map_truth.get(src) == f
    )

    total_cells = 0
    ok_cells = 0
    batch = []

    for i, row in enumerate(rows):
        rec = {}
        for field, src_col in FIXED_MAPPING.items():
            total_cells += 1
            if src_col not in row:
                rec[field] = None
                continue
            val = row[src_col]
            if field == "purchase_date":
                parsed = _parse_date_strict_iso(val)
            elif field == "amount":
                parsed = _parse_amount_strict(val)
            elif field in ("full_name", "email", "category", "country"):
                parsed = _clean_text_strict(val)
            else:
                parsed = val
            if parsed is not None:
                ok_cells += 1
            rec[field] = parsed
        batch.append(tuple(rec[f] for f in CANONICAL_FIELDS))

        if len(batch) >= BATCH_SIZE:
            cur.executemany(
                "INSERT INTO etl_output VALUES (?,?,?,?,?,?,?)", batch)
            conn.commit()
            if first_result_latency_ms is None:
                first_result_latency_ms = (time.perf_counter() - t_start) * 1000
            batch = []

    if batch:
        cur.executemany("INSERT INTO etl_output VALUES (?,?,?,?,?,?,?)", batch)
        conn.commit()
        if first_result_latency_ms is None:
            first_result_latency_ms = (time.perf_counter() - t_start) * 1000

    t_end = time.perf_counter()

    return {
        "exec_time_s": t_end - t_start,
        "latency_ms": first_result_latency_ms,
        "success_rate_pct": 100.0 * ok_cells / total_cells,
        "mapping_precision_pct": 100.0 * correct_field_maps / len(CANONICAL_FIELDS),
        "n_records": len(rows),
    }


# ----------------------------------------------------------------------
# Pipeline 2: ELT (Data Lake) (mapeamento fixo, carrega-bruto-depois-transforma)
# ----------------------------------------------------------------------
def run_elt(rows, column_map_truth, conn):
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS elt_raw")
    cur.execute("CREATE TABLE elt_raw (payload TEXT)")
    cur.execute("DROP TABLE IF EXISTS elt_output")
    cur.execute("""CREATE TABLE elt_output (
        customer_id TEXT, full_name TEXT, email TEXT,
        purchase_date TEXT, amount TEXT, category TEXT, country TEXT
    )""")
    conn.commit()

    t_start = time.perf_counter()
    first_result_latency_ms = None

    # --- fase de carga bruta (Load) ---
    batch = []
    for row in rows:
        batch.append((json.dumps(row),))
        if len(batch) >= BATCH_SIZE:
            cur.executemany("INSERT INTO elt_raw VALUES (?)", batch)
            conn.commit()
            batch = []
    if batch:
        cur.executemany("INSERT INTO elt_raw VALUES (?)", batch)
        conn.commit()

    # --- fase de transformação em lote (Transform), após carga completa ---
    cur.execute("SELECT payload FROM elt_raw")
    raw_rows = [json.loads(r[0]) for r in cur.fetchall()]

    correct_field_maps = sum(
        1 for f, src in FIXED_MAPPING.items()
        if column_map_truth.get(src) == f
    )

    total_cells = 0
    ok_cells = 0
    out_batch = []
    for i, row in enumerate(raw_rows):
        rec = {}
        for field, src_col in FIXED_MAPPING.items():
            total_cells += 1
            if src_col not in row:
                rec[field] = None
                continue
            val = row[src_col]
            if field == "purchase_date":
                parsed = _parse_date_strict_iso(val)
            elif field == "amount":
                parsed = _parse_amount_strict(val)
            elif field in ("full_name", "email", "category", "country"):
                parsed = _clean_text_strict(val)
            else:
                parsed = val
            if parsed is not None:
                ok_cells += 1
            rec[field] = parsed
        out_batch.append(tuple(rec[f] for f in CANONICAL_FIELDS))
        if len(out_batch) >= BATCH_SIZE:
            cur.executemany("INSERT INTO elt_output VALUES (?,?,?,?,?,?,?)", out_batch)
            conn.commit()
            if first_result_latency_ms is None:
                first_result_latency_ms = (time.perf_counter() - t_start) * 1000
            out_batch = []
    if out_batch:
        cur.executemany("INSERT INTO elt_output VALUES (?,?,?,?,?,?,?)", out_batch)
        conn.commit()
        if first_result_latency_ms is None:
            first_result_latency_ms = (time.perf_counter() - t_start) * 1000

    t_end = time.perf_counter()

    return {
        "exec_time_s": t_end - t_start,
        "latency_ms": first_result_latency_ms,
        "success_rate_pct": 100.0 * ok_cells / total_cells,
        "mapping_precision_pct": 100.0 * correct_field_maps / len(CANONICAL_FIELDS),
        "n_records": len(rows),
    }


# ----------------------------------------------------------------------
# Pipeline 3: Ecossistema de Integração Cognitiva
# (mapeamento semântico adaptativo + parsing multi-formato)
# ----------------------------------------------------------------------
def run_cognitive(rows, column_map_truth, conn):
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS cog_output")
    cur.execute("""CREATE TABLE cog_output (
        customer_id TEXT, full_name TEXT, email TEXT,
        purchase_date TEXT, amount TEXT, category TEXT, country TEXT
    )""")
    conn.commit()

    t_start = time.perf_counter()

    # --- etapa cognitiva: descoberta semântica do esquema (uma vez por lote de origem) ---
    source_columns = list(rows[0].keys())
    mapping, retries = semantic_schema_mapping(source_columns)

    correct_field_maps = sum(
        1 for f, src in mapping.items() if column_map_truth.get(src) == f
    )

    first_result_latency_ms = None
    total_cells = 0
    ok_cells = 0
    batch = []

    for i, row in enumerate(rows):
        rec = {}
        for field, src_col in mapping.items():
            total_cells += 1
            if src_col not in row:
                rec[field] = None
                continue
            val = row[src_col]
            if field == "purchase_date":
                parsed = _parse_date_adaptive(val)
            elif field == "amount":
                parsed = _parse_amount_adaptive(val)
            elif field in ("full_name", "email", "category", "country"):
                parsed = _clean_text_adaptive(val)
            else:
                parsed = val
            if parsed is not None:
                ok_cells += 1
            rec[field] = parsed
        batch.append(tuple(rec[f] for f in CANONICAL_FIELDS))

        if len(batch) >= BATCH_SIZE:
            cur.executemany("INSERT INTO cog_output VALUES (?,?,?,?,?,?,?)", batch)
            conn.commit()
            if first_result_latency_ms is None:
                first_result_latency_ms = (time.perf_counter() - t_start) * 1000
            batch = []

    if batch:
        cur.executemany("INSERT INTO cog_output VALUES (?,?,?,?,?,?,?)", batch)
        conn.commit()
        if first_result_latency_ms is None:
            first_result_latency_ms = (time.perf_counter() - t_start) * 1000

    t_end = time.perf_counter()

    return {
        "exec_time_s": t_end - t_start,
        "latency_ms": first_result_latency_ms,
        "success_rate_pct": 100.0 * ok_cells / total_cells,
        "mapping_precision_pct": 100.0 * correct_field_maps / len(CANONICAL_FIELDS),
        "n_records": len(rows),
        "agentic_retries": retries,
    }
