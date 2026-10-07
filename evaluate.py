"""Evalúa el recuperador híbrido con Precision@k y Recall@k."""

import json
from pathlib import Path

from config import GOLDEN_SET_PATH, configure_logging, load_settings
from metrics import precision_at_k, recall_at_k
from retriever import RAGSystem


def load_golden_set(path: Path = GOLDEN_SET_PATH) -> list[dict[str, str]]:
    cases = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(cases, list) or len(cases) < 5:
        raise ValueError("El golden set tiene que tener al menos 5 preguntas.")
    for index, case in enumerate(cases, start=1):
        if "pregunta" not in case or "documento_id_esperado" not in case:
            raise ValueError(
                f"La pregunta {index} necesita 'pregunta' y 'documento_id_esperado'."
            )
    return cases


def evaluate_cases(system: RAGSystem, cases: list[dict[str, str]], k: int) -> list[dict]:
    rows: list[dict] = []
    for case in cases:
        expected = case["documento_id_esperado"]
        documents = system.retrieve(case["pregunta"])
        rows.append(
            {
                "pregunta": case["pregunta"],
                "documento_id_esperado": expected,
                "recuperados": [document.metadata.get("document_id", "?") for document in documents],
                "precision": precision_at_k(documents, expected, k),
                "recall": recall_at_k(documents, expected, k),
            }
        )
    return rows


def format_report(rows: list[dict], k: int) -> str:
    lines = [f"=== Evaluación híbrida (k={k}) ===", ""]
    for index, row in enumerate(rows, start=1):
        retrieved = ", ".join(row["recuperados"]) or "(sin resultados)"
        lines.append(f"[{index}] {row['pregunta']}")
        lines.append(f"    esperado: {row['documento_id_esperado']}")
        lines.append(f"    recuperados: {retrieved}")
        lines.append(
            f"    Recall@{k}: {row['recall']:.2f} "
            f"({'está' if row['recall'] == 1 else 'no está'} en el top-{k})"
        )
        lines.append(
            f"    Precision@{k}: {row['precision']:.2f} "
            f"({row['precision'] * 100:.0f}% de los {k} provienen del documento esperado)"
        )
        lines.append("")

    count = len(rows)
    mean_recall = sum(row["recall"] for row in rows) / count
    mean_precision = sum(row["precision"] for row in rows) / count
    hits = sum(1 for row in rows if row["recall"] == 1.0)
    lines.append("--- Resumen ---")
    lines.append(f"Preguntas: {count}")
    lines.append(f"Recall@{k} promedio: {mean_recall:.2f}")
    lines.append(f"Precision@{k} promedio: {mean_precision:.2f} ({mean_precision * 100:.0f}%)")
    lines.append(f"Aciertos (documento esperado en el top-{k}): {hits}/{count}")
    return "\n".join(lines)


def main() -> None:
    configure_logging()
    settings = load_settings(require_embeddings=True)
    cases = load_golden_set()
    system = RAGSystem.from_settings(settings)
    rows = evaluate_cases(system, cases, settings.top_k)
    print(format_report(rows, settings.top_k))


if __name__ == "__main__":
    main()
