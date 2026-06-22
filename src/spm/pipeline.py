"""Orquestradores de alto nível do pipeline (baseados em arquivos).

Cada função executa uma etapa para um ``(curso, atividade)``, lendo de
``data/raw`` e escrevendo em ``outputs/``, iterando os 24 cenários da matriz.
Reproduzem o comportamento dos antigos ``scripts/*.py``; a CLI (:mod:`spm.cli`)
é uma fina camada sobre estas funções.

Para uso programático em memória, prefira as funções de núcleo
(:func:`spm.simplification.simplify`, :func:`spm.mining.mine`,
:func:`spm.metrics.metrics`).
"""
import datetime
import json
import os
import time

import pandas as pd

from . import io
from .metrics import metrics as compute_metrics
from .mining import mine
from .sceneries import SCENERY_DEFINITIONS, SCENERIES_NAMES
from .simplification import get_dates, simplify

# Mapa (curso -> assignment_id por atividade; posição = nº da atividade).
# Permite derivar o assignment_id a partir de (curso, atividade); pode ser
# sobrescrito explicitamente nas chamadas/flags.
ASSIGNMENT_IDS = {
    2060: [12841, 12842, 12843, 12844],
    2065: [12874, 12875, 12876],
}


def resolve_assignment_id(course, activity, assignment_id=None):
    """Resolve o assignment_id a partir de (curso, atividade) se não for dado."""
    if assignment_id is not None:
        return assignment_id
    ids = ASSIGNMENT_IDS.get(course)
    if not ids:
        raise ValueError(f"Curso {course} sem mapa de assignment_ids; passe assignment_id explicitamente.")
    if not (1 <= activity <= len(ids)):
        raise ValueError(f"Atividade {activity} fora de 1..{len(ids)} do curso {course}; passe assignment_id.")
    return ids[activity - 1]


def _expand_sceneries(use_split):
    """Lista de nomes de cenário, com sufixos _high/_low quando split por nota."""
    if use_split:
        return [f"{s}_{suffix}" for s in SCENERIES_NAMES for suffix in ["high", "low"]]
    return list(SCENERIES_NAMES)


def _scenery_path(sceneries_dir, course, activity, scenery, use_split):
    base = f"{sceneries_dir}/{course}/{activity}"
    return f"{base}/split_grade/{scenery}.json" if use_split else f"{base}/{scenery}.json"


# =============================================================================
# ETAPA 1 — SIMPLIFICAÇÃO
# =============================================================================

def run_simplification(course, activity, assignment_id=None, *, logs=None, grades=None,
                       quiz=None, mapping=None, out_dir="outputs/sceneries", split_grade=False):
    """Pré-processa os logs gerando um JSON por cenário em ``out_dir/{course}/{activity}``."""
    assignment_id = resolve_assignment_id(course, activity, assignment_id)

    base = f"data/raw/{course}"
    logs = logs or f"{base}/see_course{course}_logs_filtered.csv"
    grades = grades or f"{base}/see_course{course}_quiz_grades.csv"
    quiz = quiz or f"{base}/see_course{course}_quiz_list.csv"
    mapping = mapping or f"{base}/event_mapping.csv"

    logs_df = pd.read_csv(logs, index_col="id").sort_values("t")
    mapping_df = pd.read_csv(mapping)
    quiz_df = pd.read_csv(quiz)
    grades_df = pd.read_csv(grades) if grades else None

    initial_date, final_date = get_dates(quiz_df, assignment_id)

    scenery_dir = f"{out_dir}/{course}/{activity}"
    os.makedirs(scenery_dir, exist_ok=True)
    if split_grade:
        os.makedirs(f"{scenery_dir}/split_grade", exist_ok=True)

    print(f"Simplificacao | curso {course} atividade {activity} assignment {assignment_id}")
    print(f"  datas (do quiz CSV): {initial_date} -> {final_date}")
    print(f"  cenarios: {len(SCENERY_DEFINITIONS)} -> {scenery_dir}\n")

    for scenery in SCENERY_DEFINITIONS:
        start = time.time()
        result = simplify(
            logs_df, mapping_df, scenery,
            assignment_id=assignment_id, initial_date=initial_date, final_date=final_date,
            grades_df=grades_df, split_grade=split_grade,
        )

        if split_grade:
            high_grade, low_grade = result
            prefix = f"{scenery_dir}/split_grade/{scenery['path']}"
            with open(prefix + "_high.json", "w+") as file:
                json.dump(high_grade, file, indent=2, default=lambda o: str(o))
            with open(prefix + "_low.json", "w+") as file:
                json.dump(low_grade, file, indent=2, default=lambda o: str(o))
            out = prefix + "_{high,low}.json"
        else:
            out = f"{scenery_dir}/{scenery['path']}.json"
            with open(out, "w+") as file:
                json.dump(result, file, indent=2, default=lambda o: str(o))
        print(f"  {scenery['path']}: {(time.time() - start):.2f}s -> {out}")


# =============================================================================
# ETAPA 2 — MINERAÇÃO
# =============================================================================

def run_mining(course, activity, *, minsup=0.08, use_split=False,
               sceneries_dir="outputs/sceneries", out_dir="outputs/mining_results"):
    """Minera padrões para cada cenário, salvando em ``out_dir/{course}/{activity}``."""
    sceneries = _expand_sceneries(use_split)
    output_path = f"{out_dir}/{course}/{activity}"

    print("Iniciando mineração de processos...")
    print(f"Curso: {course}, Atividade: {activity}")
    print(f"Total de cenários: {len(sceneries)}")
    print(f"Resultados serão salvos em: {output_path}\n")

    for index, scenery in enumerate(sceneries, 1):
        begin = time.time()
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] [{index}/{len(sceneries)}] Processando {scenery}...", end=" | ")

        file_name = _scenery_path(sceneries_dir, course, activity, scenery, use_split)
        sequences = io.load_sceneries(file_name)
        if sequences is None:
            print("ERRO: Arquivo não encontrado")
            continue

        mining_output = mine(sequences, minsup)
        io.save_mining(mining_output, scenery, output_path)

        print(f"Concluído em {time.time() - begin:.2f}s")

    print(f"\nMineração concluída! Resultados salvos em: {output_path}")


# =============================================================================
# ETAPA 3 — MÉTRICAS
# =============================================================================

def run_metrics(course, activity, *, minsup=0.08, total_sequences=11974.0, use_split=False,
                sceneries_dir="outputs/sceneries", mining_dir="outputs/mining_results",
                out_dir="outputs/results"):
    """Calcula métricas por cenário e gera os relatórios consolidados."""
    sceneries = _expand_sceneries(use_split)
    mining_path = f"{mining_dir}/{course}/{activity}"
    results_path = f"{out_dir}/{course}/{activity}"

    if not os.path.exists(mining_path):
        print(f"ERRO: Diretório de resultados de mineração não encontrado: {mining_path}")
        print("Execute primeiro a etapa de mineração (spm mine).")
        return

    print("Iniciando cálculo de métricas...")
    print(f"Curso: {course}, Atividade: {activity}")
    print(f"Total de cenários: {len(sceneries)}")
    print(f"Resultados serão salvos em: {results_path}\n")

    os.makedirs(results_path, exist_ok=True)
    general_info = io.initialize_general_info(results_path)
    new_lines = []

    for index, scenery in enumerate(sceneries, 1):
        begin = time.time()
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] [{index}/{len(sceneries)}] Processando {scenery}...", end=" | ")

        try:
            mining_results = io.load_mining(scenery, mining_path)
            sequences = io.load_sceneries(_scenery_path(sceneries_dir, course, activity, scenery, use_split))
            if sequences is None:
                print("ERRO: Cenário não encontrado")
                continue

            final_result, scenery_info = compute_metrics(
                mining_results, sequences, scenery=scenery, minsup=minsup
            )

            if final_result is None or scenery_info is None:
                print("ERRO: Dados não encontrados")
                continue

            elapsed = time.time() - begin
            scenery_info["elapsed_time"] = elapsed
            new_lines.append(scenery_info)
            io.write_result(final_result, scenery, results_path, True)
            print(f"Concluído em {elapsed:.2f}s")
        except Exception as e:
            print(f"ERRO: {str(e)}")
            import traceback
            traceback.print_exc()

    general_info = io.update_general_info(general_info, new_lines)

    # general_info.csv precisa existir ANTES dos relatórios (get_supports_by_scenery o lê).
    general_info.to_csv(f"{results_path}/general_info.csv", sep=";", index=False)
    print(f"\n✓ general_info.csv salvo com {len(general_info)} cenários")

    io.generate_consolidated_reports(results_path, sceneries, total_sequences)

    print(f"\nCálculo de métricas concluído! Resultados salvos em: {results_path}")


# =============================================================================
# PIPELINE COMPLETO
# =============================================================================

def run_pipeline(course, activity, assignment_id=None, *, minsup=0.08, total_sequences=11974.0,
                 use_split=False):
    """Roda as três etapas em sequência para um ``(curso, atividade)``."""
    assignment_id = resolve_assignment_id(course, activity, assignment_id)
    run_simplification(course, activity, assignment_id, split_grade=use_split)
    run_mining(course, activity, minsup=minsup, use_split=use_split)
    run_metrics(course, activity, minsup=minsup, total_sequences=total_sequences, use_split=use_split)
