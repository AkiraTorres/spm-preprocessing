"""Interface de linha de comando do pacote: comando ``spm``.

Fina camada de parsing sobre os orquestradores de :mod:`spm.pipeline`.
Subcomandos: ``simplify``, ``mine``, ``metrics`` e ``pipeline``.
"""
import argparse

from . import pipeline


def _add_common(parser):
    parser.add_argument("-co", "--course", type=int, required=True, help="Numero do curso (ex.: 2060, 2065)")
    parser.add_argument("-act", "--activity", type=int, required=True, help="Numero da atividade (inteiro)")


def build_parser():
    parser = argparse.ArgumentParser(
        prog="spm",
        description="Sequential Pattern Mining sobre logs do Moodle: pré-processamento, "
                    "mineração (PrefixSpan) e métricas por cenário.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_pipe = sub.add_parser("pipeline", help="Roda as 3 etapas em sequência")
    _add_common(p_pipe)
    p_pipe.add_argument("-id", "--assignment-id", type=int, default=None,
                        help="Assignment ID (derivado de curso/atividade se omitido)")
    p_pipe.add_argument("-ms", "--minsup", type=float, default=0.08, help="Suporte mínimo (default: 0.08)")
    p_pipe.add_argument("-ts", "--total-sequences", type=float, default=11974.0,
                        help="Total de referência p/ normalização de %% (default: 11974)")
    p_pipe.add_argument("--use-split", action="store_true", help="Usa variantes _high/_low por nota")

    p_simp = sub.add_parser("simplify", help="Pré-processa logs -> cenários (JSON)")
    _add_common(p_simp)
    p_simp.add_argument("-id", "--assignment-id", type=int, default=None,
                        help="Assignment ID (derivado de curso/atividade se omitido)")
    p_simp.add_argument("--logs", type=str, default=None, help="CSV de logs (default derivado de data/raw)")
    p_simp.add_argument("--grades", type=str, default=None, help="CSV de notas (default derivado de data/raw)")
    p_simp.add_argument("--quiz", type=str, default=None, help="CSV de quizzes (default derivado de data/raw)")
    p_simp.add_argument("--mapping", type=str, default=None, help="CSV de mapeamento de eventos (default derivado de data/raw)")
    p_simp.add_argument("--out-dir", type=str, default="outputs/sceneries", help="Raiz de saída dos cenários")
    p_simp.add_argument("--split-grade", action="store_true", help="Gera variantes _high/_low por nota")

    p_mine = sub.add_parser("mine", help="Minera padrões sequenciais (PrefixSpan)")
    _add_common(p_mine)
    p_mine.add_argument("-ms", "--minsup", type=float, default=0.08, help="Suporte mínimo (default: 0.08)")
    p_mine.add_argument("--use-split", action="store_true", help="Usa variantes _high/_low por nota")
    p_mine.add_argument("--sceneries-dir", type=str, default="outputs/sceneries", help="Raiz dos cenários de entrada")
    p_mine.add_argument("--out-dir", type=str, default="outputs/mining_results", help="Raiz de saída da mineração")

    p_met = sub.add_parser("metrics", help="Calcula métricas + relatórios consolidados")
    _add_common(p_met)
    p_met.add_argument("-ms", "--minsup", type=float, default=0.08, help="Suporte mínimo (default: 0.08)")
    p_met.add_argument("-ts", "--total-sequences", type=float, default=11974.0,
                       help="Total de referência p/ normalização de %% (default: 11974)")
    p_met.add_argument("--use-split", action="store_true", help="Usa variantes _high/_low por nota")
    p_met.add_argument("--sceneries-dir", type=str, default="outputs/sceneries", help="Raiz dos cenários")
    p_met.add_argument("--mining-dir", type=str, default="outputs/mining_results", help="Raiz dos resultados de mineração")
    p_met.add_argument("--out-dir", type=str, default="outputs/results", help="Raiz de saída das métricas")

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)

    if args.command == "pipeline":
        pipeline.run_pipeline(
            args.course, args.activity, args.assignment_id,
            minsup=args.minsup, total_sequences=args.total_sequences, use_split=args.use_split,
        )
    elif args.command == "simplify":
        pipeline.run_simplification(
            args.course, args.activity, args.assignment_id,
            logs=args.logs, grades=args.grades, quiz=args.quiz, mapping=args.mapping,
            out_dir=args.out_dir, split_grade=args.split_grade,
        )
    elif args.command == "mine":
        pipeline.run_mining(
            args.course, args.activity,
            minsup=args.minsup, use_split=args.use_split,
            sceneries_dir=args.sceneries_dir, out_dir=args.out_dir,
        )
    elif args.command == "metrics":
        pipeline.run_metrics(
            args.course, args.activity,
            minsup=args.minsup, total_sequences=args.total_sequences, use_split=args.use_split,
            sceneries_dir=args.sceneries_dir, mining_dir=args.mining_dir, out_dir=args.out_dir,
        )


if __name__ == "__main__":
    main()
