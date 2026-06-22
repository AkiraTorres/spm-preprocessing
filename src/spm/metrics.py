"""Núcleo de cálculo de métricas dos padrões minerados.

Recebe os padrões minerados e as sequências (em memória) e calcula suportes,
notas, time spans e diversidade de Jaccard. A função de alto nível é
:func:`metrics`. Toda persistência (JSON/CSV, relatórios consolidados) fica em
:mod:`spm.io`; a orquestração por curso/atividade em :mod:`spm.pipeline`.

Sem estado global: o cache de suporte é criado por chamada e passado adiante.
"""
import datetime
import statistics

import numpy as np
import pandas as pd


# =============================================================================
# CARREGAMENTO E FORMATAÇÃO DE DADOS (em memória)
# =============================================================================

def generate_data(data):
    """Gera DataFrame (uma linha por sessão) a partir do JSON de cenário."""
    rows = [
        {
            "key": item["key"],
            "temporal_folding": item["temporal_folding"],
            "grade": item["grade"],
            "max_grade": item["max_grade"],
            "events": event,
        }
        for item in data
        for event in item["events"]
    ]
    return pd.DataFrame(rows)


def format_tf_data(s) -> list:
    """Formata dados para cálculo de suporte: lista de listas de nomes de evento."""
    return [[event["event"] for event in user_sequence["events"]]
            for user_sequence in s.to_dict(orient="records")]


def extract_events(event_list):
    """Extrai os nomes de evento de uma lista de dicionários."""
    return [event_dict["event"] for event_dict in event_list]


def extract_events_vectorized(events_series):
    """Extrai nomes de evento de forma vetorizada."""
    return events_series.apply(lambda x: [event_dict["event"] for event_dict in x])


# =============================================================================
# CÁLCULO DE MÉTRICAS BÁSICAS
# =============================================================================

def is_subsequence(subseq, sequence):
    """Verifica se ``subseq`` é subsequência de ``sequence``."""
    if not subseq:
        return True
    if len(subseq) > len(sequence):
        return False

    sub_idx = 0
    sub_len = len(subseq)

    for elem in sequence:
        if elem == subseq[sub_idx]:
            sub_idx += 1
            if sub_idx == sub_len:
                return True
    return False


def count_subsequence_occurrences(pattern, sequence):
    """Conta quantas vezes ``pattern`` aparece como subsequência em ``sequence``."""
    if not pattern or not sequence:
        return 0

    count = 0
    seq_len = len(sequence)
    pattern_len = len(pattern)

    for start in range(seq_len - pattern_len + 1):
        pattern_idx = 0
        for i in range(start, seq_len):
            if sequence[i] == pattern[pattern_idx]:
                pattern_idx += 1
                if pattern_idx == pattern_len:
                    count += 1
                    break

    return count


def get_supports(formatted, minsup, sequence_list, cache=None):
    """Calcula I-support de uma sequência (todas as ocorrências). Usa cache opcional."""
    seq_key = tuple(sequence_list)

    if cache is not None and seq_key in cache:
        return cache[seq_key]

    total_matches = sum(count_subsequence_occurrences(sequence_list, seq) for seq in formatted)

    if cache is not None:
        cache[seq_key] = total_matches
    return total_matches


def get_sequence_ids(target, data):
    """Retorna IDs das sequências que contêm o padrão ``target``."""
    mask = data["events"].apply(lambda x: is_subsequence(target, x))
    return data.loc[mask, "key"].tolist()


def get_sequence_grade(ids, data):
    """Calcula estatísticas de notas (média, desvio, mediana, moda)."""
    if not ids:
        return 0, 0, 0, 0

    grades = data.loc[data["key"].isin(ids), "grade"]

    if grades.empty:
        return 0, 0, 0, 0

    mode_val = grades.mode()
    return (
        grades.mean(),
        grades.std(ddof=0),
        grades.median(),
        mode_val.iloc[0] if not mode_val.empty else 0
    )


def get_time_span(ids, data):
    """Calcula estatísticas temporais (total, médio, início, fim)."""
    if not ids:
        return [0, 0, 0, 0]

    filtered = data.loc[data["key"].isin(ids), "events"]

    if filtered.empty:
        return [0, 0, 0, 0]

    start_times = filtered.apply(lambda x: x[0]["time"])
    end_times = filtered.apply(lambda x: x[-1]["time"])

    total_time = end_times.max() - start_times.min()
    avg_time = (end_times - start_times).mean()

    return [total_time, avg_time, start_times.min(), end_times.max()]


def get_sequences_length(data):
    """Calcula estatísticas de comprimento das sequências."""
    lengths = data["events"].apply(len).values
    return int(lengths.min()), int(lengths.max()), float(lengths.mean()), float(lengths.std(ddof=1))


# =============================================================================
# JACCARD (SIMILARIDADE / DISTÂNCIA)
# =============================================================================

def jaccard_similarity(seq1, seq2):
    """Coeficiente de Jaccard entre duas sequências."""
    set1 = set(seq1)
    set2 = set(seq2)

    if not set1 and not set2:
        return 1.0

    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))

    return intersection / union if union > 0 else 0.0


def jaccard_distance(seq1, seq2):
    """Distância de Jaccard (1 - similaridade) em porcentagem."""
    return (1 - jaccard_similarity(seq1, seq2)) * 100


def calculate_pattern_jaccard_distance(pattern, all_patterns_same_size):
    """Distância média de Jaccard de um padrão frente aos demais do mesmo tamanho."""
    if len(all_patterns_same_size) <= 1:
        return 100.0

    distances = []
    for other_pattern in all_patterns_same_size:
        if pattern != other_pattern:
            distances.append(jaccard_distance(pattern, other_pattern))

    return statistics.mean(distances) if distances else 100.0


def calculate_scenery_jaccard_diversity(all_patterns):
    """Diversidade geral do cenário (média das distâncias entre todos os pares)."""
    if len(all_patterns) <= 1:
        return 0.0

    distances = []
    for i, pattern1 in enumerate(all_patterns):
        for pattern2 in all_patterns[i + 1:]:
            distances.append(jaccard_distance(pattern1, pattern2))

    return statistics.mean(distances) if distances else 0.0


# =============================================================================
# FORMATAÇÃO DE ESTATÍSTICAS (usadas também por relatórios consolidados)
# =============================================================================

def format_stat_with_std(values, decimals=2):
    """Formata como ``"média (+- desvio)"``."""
    if hasattr(values, 'tolist'):
        values = values.tolist()

    if not values or len(values) == 0:
        return "0.00 (+- 0)"

    try:
        mean_val = statistics.mean(values)
        std_val = statistics.stdev(values)
        return f"{mean_val:.{decimals}f} (+- {std_val:.{decimals}f})"
    except statistics.StatisticsError:
        mean_val = statistics.mean(values)
        return f"{mean_val:.{decimals}f} (+- 0)"
    except Exception:
        return "0.00 (+- 0)"


def parse_mean_std(text: str):
    """Extrai ``(mean, std)`` de string ``"média (+- desvio)"``; ``(nan, nan)`` se inválido."""
    try:
        mean_part, rest = text.split(" (+- ")
        std_part = rest.rstrip(")")
        return float(mean_part), float(std_part)
    except Exception:
        return np.nan, np.nan


def calculate_support_statistics(scenery, data):
    """Estatísticas de suporte (i_support e s_support) de um cenário."""
    return {
        "scenery": scenery.split("-")[0],
        "i_support": format_stat_with_std(data['i_support']),
        "s_support": format_stat_with_std(data['ids']),
    }


# =============================================================================
# PROCESSAMENTO DE PADRÕES E CENÁRIOS
# =============================================================================

def compute_pattern_metrics(seq, formatted, all_sequences, original_seq, max_grade, minsup, cache=None):
    """Calcula todas as métricas de um único padrão."""
    sequence_list = seq["sequence"]
    i_support = get_supports(formatted, minsup, sequence_list, cache)
    ids = get_sequence_ids(sequence_list, all_sequences)
    avg, dev, median, mode = get_sequence_grade(ids, all_sequences)
    total_time, avg_time, initial_time, final_time = get_time_span(ids, original_seq)

    return {
        "sequence_size": len(sequence_list),
        "sequence": sequence_list,
        "total": seq["total"],
        "total_time_span": total_time,
        "avg_time_span": avg_time,
        "i_support": i_support,
        "s_support": len(ids),
        "ids": ids,
        "grade_avg": avg,
        "grade_avg_deviation": dev,
        "grade_median": median,
        "grade_mode": mode,
        "max_grade": max_grade,
        "jaccard_distance": 0.0,
        "initial_time": initial_time,
        "final_time": final_time,
    }


def find_extreme_patterns(sequences):
    """Encontra os padrões mais e menos repetidos."""
    most_repeated = {"total": 0}
    least_repeated = {"total": float('inf')}

    for sequence in sequences:
        if sequence["total"] > most_repeated["total"]:
            most_repeated = sequence.copy()
        if 1 < sequence["total"] < least_repeated["total"]:
            least_repeated = sequence.copy()

    return most_repeated, least_repeated


def collect_statistics(sequences):
    """Coleta comprimentos e timestamps dos padrões."""
    lengths = []
    times = []

    for sequence in sequences:
        lengths.append(sequence["sequence_size"])
        if sequence.get("initial_time", 0) > 0:
            times.extend([sequence["initial_time"], sequence["final_time"]])

    return lengths, times


def group_patterns_by_size(final_result):
    """Agrupa padrões por tamanho para cálculo eficiente de Jaccard."""
    patterns_by_size = {}
    all_patterns = []

    for key, data in final_result.items():
        for sequence in data["sequences"]:
            pattern = sequence["sequence"]
            size = len(pattern)

            if size not in patterns_by_size:
                patterns_by_size[size] = []

            patterns_by_size[size].append(pattern)
            all_patterns.append(pattern)

    return patterns_by_size, all_patterns


def apply_jaccard_distances(final_result, patterns_by_size):
    """Aplica a distância de Jaccard a todos os padrões."""
    for key, data in final_result.items():
        for sequence in data["sequences"]:
            pattern_size = sequence["sequence_size"]
            patterns_same_size = patterns_by_size.get(pattern_size, [])
            sequence["jaccard_distance"] = calculate_pattern_jaccard_distance(
                sequence["sequence"],
                patterns_same_size
            )


def calculate_general_statistics(lengths, times, original_seq, total_sequences,
                                 scenery_diversity, all_jaccard_distances,
                                 scenery, max_grade, minsup):
    """Calcula as estatísticas gerais (linha do general_info) de um cenário."""
    lengths.sort()
    times = [t for t in times if t > 0]
    times.sort()

    min_len, max_len, avg_len, dev_len = get_sequences_length(original_seq)

    try:
        avg_pattern_length = f"{statistics.mean(lengths):.2f} (+- {statistics.stdev(lengths):.2f})"
    except Exception:
        avg_pattern_length = f"{statistics.mean(lengths):.2f} (+- 0)"

    try:
        avg_jaccard = f"{statistics.mean(all_jaccard_distances):.2f} (+- {statistics.stdev(all_jaccard_distances):.2f})"
    except Exception:
        avg_jaccard = f"{statistics.mean(all_jaccard_distances):.2f} (+- 0)" if all_jaccard_distances else "0.00 (+- 0)"

    return {
        "scenery": scenery.split("-")[0],
        "minsup": minsup,
        "max_grade": max_grade,
        "total_sequences": total_sequences,
        "time_span_in_days": (
            datetime.datetime.fromtimestamp(times[-1]) - datetime.datetime.fromtimestamp(times[0])
        ).days if times else 0,
        "longest_pattern_length": lengths[-1] if lengths else 0,
        "shortest_pattern_length": lengths[0] if lengths else 0,
        "average_pattern_length": avg_pattern_length,
        "longest_sequence_length": max_len,
        "shortest_sequence_length": min_len,
        "average_sequence_length": f"{avg_len:.2f} (+- {dev_len:.2f})",
        "jaccard_diversity": f"{scenery_diversity:.2f}",
        "avg_jaccard_distance": avg_jaccard,
        "i_support": "",
        "s_support": "",
    }


def metrics(mining_results, sequences, *, scenery="0", minsup=0.08):
    """Calcula todas as métricas de um cenário, em memória.

    Args:
        mining_results: dicionário de padrões minerados (saída de
            :func:`spm.mining.mine`).
        sequences: lista de sequências por usuário (``events_by_user``), saída de
            :func:`spm.simplification.simplify`.
        scenery: rótulo do cenário (usado na coluna ``scenery`` do general_info).
        minsup: suporte mínimo usado na mineração.

    Returns:
        Tupla ``(final_result, general_info)`` — o detalhamento por padrão e a
        linha de estatísticas gerais do cenário; ``(None, None)`` se sem dados.
    """
    all_sequences = generate_data(sequences)
    if all_sequences.empty:
        return None, None

    support_cache = {}

    original_seq = all_sequences.copy()
    max_grade = int(all_sequences["max_grade"].iloc[0])
    formatted = format_tf_data(all_sequences)
    all_sequences["events"] = extract_events_vectorized(all_sequences["events"])

    # Inicializar estruturas
    final_result = {
        f"{i}_sequences": {"sequences": [], "most_repeated": {}, "least_repeated": {}}
        for i in range(1, len(mining_results) + 1)
    }

    # Primeira passagem: métricas básicas por padrão
    for key, data in mining_results.items():
        for seq in data["sequences"]:
            pattern_metrics = compute_pattern_metrics(
                seq, formatted, all_sequences, original_seq, max_grade, minsup, support_cache
            )
            final_result[key]["sequences"].append(pattern_metrics)

        most, least = find_extreme_patterns(final_result[key]["sequences"])
        final_result[key]["most_repeated"] = most
        final_result[key]["least_repeated"] = least

    # Agrupar padrões e calcular Jaccard
    patterns_by_size, all_patterns = group_patterns_by_size(final_result)
    apply_jaccard_distances(final_result, patterns_by_size)

    # Coletar estatísticas
    all_lengths = []
    all_times = []
    all_jaccard_distances = []

    for key, data in final_result.items():
        lengths, times = collect_statistics(data["sequences"])
        all_lengths.extend(lengths)
        all_times.extend(times)

        for sequence in data["sequences"]:
            all_jaccard_distances.append(sequence["jaccard_distance"])

    # Métricas gerais
    scenery_diversity = calculate_scenery_jaccard_diversity(all_patterns)
    total_patterns = sum(len(data["sequences"]) for data in mining_results.values())

    general_info = calculate_general_statistics(
        all_lengths, all_times, original_seq, total_patterns,
        scenery_diversity, all_jaccard_distances,
        scenery, max_grade, minsup
    )

    return final_result, general_info
