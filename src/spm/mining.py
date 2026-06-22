"""Núcleo de mineração de padrões sequenciais.

Recebe sequências de eventos (em memória) e devolve os padrões frequentes,
usando PrefixSpan por padrão. A função de alto nível é :func:`mine`. A leitura
dos cenários e a escrita dos resultados em disco ficam em :mod:`spm.io` /
:mod:`spm.pipeline`.
"""
import pandas as pd
from prefixspan import PrefixSpan


def generate_data(data):
    """Gera DataFrame (uma linha por sessão de usuário) a partir do JSON de cenário."""
    rows = []
    for item in data:
        for i in item["events"]:
            rows.append(
                {
                    "key": item["key"],
                    "temporal_folding": item["temporal_folding"],
                    "grade": item["grade"],
                    "max_grade": item["max_grade"],
                    "events": i,
                }
            )
    return pd.DataFrame(rows)


def format_tf_data(s) -> list:
    """Formata os dados para mineração: lista de listas de nomes de evento."""
    data = []
    s = pd.DataFrame(data=s).to_dict(orient="records")
    for user_sequence in s:
        events = [event["event"] for event in user_sequence["events"]]
        data.append(events)
    return data


def gsp_mining(sequences_list: list, minsup: float = 0.08) -> list:
    """Executa mineração usando algoritmo GSP (dependência opcional ``gsppy``)."""
    from gsppy.gsp import GSP

    return GSP(sequences_list).search(minsup)


def prefix_mining(sequences_list: list, minsup: float = 0.08) -> list:
    """Executa mineração usando algoritmo PrefixSpan."""
    ps = PrefixSpan(sequences_list)
    ps.minlen = 2
    min_support = len(sequences_list) * minsup
    res = ps.frequent(min_support)

    max_seq_len = 0
    for index in res:
        if len(index[1]) > max_seq_len:
            max_seq_len = len(index[1])

    n_sequences = [{} for _ in range(max_seq_len)]

    for index in res:
        n_sequences[len(index[1]) - 1][f"{index[1]}"] = index[0]

    return n_sequences


def remap_keys(user_sequences, seq_quantities):
    """Reformata as chaves dos resultados de mineração."""
    def process_key(key):
        modified_key = key.replace("[", "").replace("]", "").replace("'", "")
        return [part.strip() for part in modified_key.split(",")]

    return {
        f"{seq_quantities}_sequences": [{"sequence": process_key(k), "total": v} for k, v in user_sequences.items()]
    }


def build_mining_output(mining_result) -> dict:
    """Constrói o dicionário de resultados a partir da saída bruta do PrefixSpan."""
    result = []
    for i in range(len(mining_result)):
        result.append(remap_keys(mining_result[i], i + 1))

    mining_output = {
        f"{i}_sequences": {"sequences": []}
        for i in range(1, len(result) + 1)
    }

    for freq in result:
        for key, sequences in freq.items():
            for seq in sequences:
                mining_output[key]["sequences"].append(
                    {"sequence": seq["sequence"], "total": seq["total"]}
                )

    return mining_output


def mine(sequences, minsup: float = 0.08) -> dict:
    """Minera padrões frequentes (PrefixSpan) a partir das sequências por usuário
    (``events_by_user``), devolvendo ``{"1_sequences": {"sequences": [...]}, ...}``."""
    formatted = format_tf_data(generate_data(sequences))
    return build_mining_output(prefix_mining(formatted, minsup))
