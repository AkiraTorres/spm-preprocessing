#!/usr/bin/env python3
"""Driver de teste do pipeline SPM.

Roda as 3 etapas do pipeline em sequencia para um (curso, atividade),
passando TODOS os parametros por flags, e valida a saida de cada etapa antes de
seguir para a proxima. Para no primeiro erro (fail-fast).

Etapas:
    1. scripts/simplification.py       -> outputs/sceneries/{course}/{activity}/
    2. scripts/process_mining.py       -> outputs/mining_results/{course}/{activity}/
    3. scripts/metrics_calculation.py  -> outputs/results/{course}/{activity}/

Uso:
    python scripts/run_pipeline.py --course 2060 --activity 2
    python scripts/run_pipeline.py --course 2065 --activity 1 --minsup 0.1
    python scripts/run_pipeline.py --python .venv/bin/python   # interpretador especifico

Rodar a partir da RAIZ do repositorio.
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from spm.sceneries import SCENERIES_NAMES

# assignment_id de cada atividade, por curso (posicao = numero da atividade).
# Antes estava hardcoded dentro de simplification.ready_main; agora vive aqui,
# no driver, e e repassado por flag para os scripts.
ASSIGNMENT_IDS = {
    2060: [12841, 12842, 12843, 12844],
    2065: [12874, 12875, 12876],
}


def run_step(title, cmd) -> bool:
    print("\n" + "=" * 72)
    print(f"[ETAPA] {title}")
    print("  $ " + " ".join(cmd))
    print("=" * 72, flush=True)
    begin = time.time()
    result = subprocess.run(cmd, cwd=ROOT)
    elapsed = time.time() - begin
    ok = result.returncode == 0
    print(f"[{'OK' if ok else f'FALHOU (exit {result.returncode})'}] {title} — {elapsed:.1f}s", flush=True)
    return ok


def check(detail, condition) -> bool:
    print(f"  [check {'OK' if condition else 'FALHOU'}] {detail}")
    return condition


def finish(ok):
    print("\n" + "=" * 72)
    print("RESULTADO FINAL:", "PIPELINE OK" if ok else "PIPELINE FALHOU")
    print("=" * 72)
    sys.exit(0 if ok else 1)


def main():
    parser = argparse.ArgumentParser(description="Roda e valida o pipeline SPM etapa por etapa.")
    parser.add_argument("-co", "--course", type=int, default=2060, help="Numero do curso (default: 2060)")
    parser.add_argument("-act", "--activity", type=int, default=2, help="Numero da atividade (default: 2)")
    parser.add_argument("-ms", "--minsup", type=float, default=0.08, help="Suporte minimo (default: 0.08)")
    parser.add_argument("-ts", "--total-sequences", type=float, default=11974.0,
                        help="Total de referencia p/ normalizacao de %% (default: 11974)")
    parser.add_argument("--use-split", action="store_true", help="Usa variantes _high/_low por nota")
    parser.add_argument("--assignment-id", type=int, default=None,
                        help="Sobrescreve o assignment_id derivado de curso/atividade")
    parser.add_argument("--python", type=str, default=sys.executable,
                        help="Interpretador Python a usar (default: o atual)")
    args = parser.parse_args()

    course, activity = args.course, args.activity

    if args.assignment_id is not None:
        assignment_id = args.assignment_id
    else:
        ids = ASSIGNMENT_IDS.get(course)
        if not ids:
            sys.exit(f"ERRO: curso {course} sem mapa de assignment_ids; passe --assignment-id.")
        if not (1 <= activity <= len(ids)):
            sys.exit(f"ERRO: atividade {activity} fora de 1..{len(ids)} do curso {course}; passe --assignment-id.")
        assignment_id = ids[activity - 1]

    py = args.python
    split = ["--use-split"] if args.use_split else []
    expected = len(SCENERIES_NAMES) * (2 if args.use_split else 1)

    sceneries_dir = ROOT / f"outputs/sceneries/{course}/{activity}"
    mining_dir = ROOT / f"outputs/mining_results/{course}/{activity}"
    results_dir = ROOT / f"outputs/results/{course}/{activity}"

    print(f"Pipeline | curso={course} atividade={activity} assignment_id={assignment_id} "
          f"minsup={args.minsup} total_sequences={args.total_sequences} split={args.use_split}")
    print(f"Interpretador: {py} | cenarios esperados por etapa: {expected}")

    # ---- Etapa 1: simplification ----
    ok = run_step(
        "1/3 simplification (pre-processamento -> sceneries)",
        [py, "scripts/simplification.py", "--course", str(course),
         "--activity", str(activity), "--assignment-id", str(assignment_id)] + split,
    )
    if ok:
        scan = (sceneries_dir / "split_grade") if args.use_split else sceneries_dir
        n = len(list(scan.glob("*.json"))) if scan.exists() else 0
        ok = check(f"{n} JSON(s) de cenario em {scan.relative_to(ROOT)} (esperado >= {expected})", n >= expected)
    if not ok:
        finish(False)

    # ---- Etapa 2: process_mining ----
    ok = run_step(
        "2/3 process_mining (mineracao PrefixSpan)",
        [py, "scripts/process_mining.py", "--course", str(course),
         "--activity", str(activity), "--minsup", str(args.minsup)] + split,
    )
    if ok:
        n = len(list(mining_dir.glob("*_mining.json"))) if mining_dir.exists() else 0
        ok = check(f"{n} arquivo(s) *_mining.json em {mining_dir.relative_to(ROOT)} (esperado >= {expected})", n >= expected)
    if not ok:
        finish(False)

    # ---- Etapa 3: metrics_calculation ----
    ok = run_step(
        "3/3 metrics_calculation (metricas + relatorios consolidados)",
        [py, "scripts/metrics_calculation.py", "--course", str(course),
         "--activity", str(activity), "--minsup", str(args.minsup),
         "--total-sequences", str(args.total_sequences)] + split,
    )
    if ok:
        gi = results_dir / "general_info.csv"
        n_csv = len(list((results_dir / "csv").glob("*.csv"))) if (results_dir / "csv").exists() else 0
        ok = check(
            f"general_info.csv {'existe' if gi.exists() else 'AUSENTE'} e {n_csv} CSV(s) por cenario em "
            f"{(results_dir / 'csv').relative_to(ROOT)}",
            gi.exists() and n_csv > 0,
        )
    finish(ok)


if __name__ == "__main__":
    main()
