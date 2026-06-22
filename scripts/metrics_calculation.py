import os.path
import json
import argparse
import pandas as pd
import csv
import time
import statistics
import datetime
import numpy as np
from prefixspan import PrefixSpan
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
import sys

# Matriz de cenarios (fonte unica). Os parametros de execucao vem por flags;
# os globals abaixo sao preenchidos em main() a partir dos argumentos parseados.
sys.path.insert(0, "src")
from spm.sceneries import SCENERIES_NAMES as sceneries_names

# =============================================================================
# CONFIGURAÇÃO GLOBAL (preenchida por flags em main())
# =============================================================================

COURSE = None
activity = None
use_split = False
minsup = 0.08
sceneries_root = "outputs/sceneries"
mining_root = "outputs/mining_results"
results_root = "outputs/results"

# Total de referencia para normalizacao de % (s_support); preenchido por flag.
total_sequences = 11974.0

# Cache global para evitar recálculos
_SUPPORT_CACHE = {}


# =============================================================================
# FUNÇÕES DE CARREGAMENTO E FORMATAÇÃO DE DADOS
# =============================================================================


def generate_data(data):
    """Gera DataFrame a partir dos dados JSON - otimizado com list comprehension."""
    rows = [
        {
            "key": item["key"],
            "temporal_folding": item["temporal_folding"],
            "grade": item["grade"],
            "max_grade": item["max_grade"],
            "events": event
        }
        for item in data
        for event in item["events"]
    ]
    return pd.DataFrame(rows)


def format_tf_data(s) -> list:
    """Formata dados para cálculos - otimizado."""
    return [[event["event"] for event in user_sequence["events"]] 
            for user_sequence in s.to_dict(orient="records")]


def read_params(file: str) -> str:
    """Constrói caminho do arquivo de entrada."""
    base = f"{sceneries_root}/{COURSE}/{activity}"
    return f"{base}/split_grade/{file}.json" if use_split else f"{base}/{file}.json"


def load_data(file_path):
    """Carrega dados do arquivo JSON - otimizado."""
    if not os.path.exists(file_path):
        print(f"Warning: {file_path} not found")
        return None
    
    with open(file_path, "r") as f:
        data = json.load(f)
    return generate_data(data)


def load_mining_results(scenery, mining_path):
    """Carrega resultados da mineração."""
    mining_file = os.path.join(mining_path, f"{scenery}_mining.json")
    with open(mining_file, "r") as f:
        return json.load(f)


# =============================================================================
# FUNÇÕES DE VERIFICAÇÃO E EXTRAÇÃO
# =============================================================================

def is_subsequence(subseq, sequence):
    """Verifica se subseq é subsequência de sequence - otimizado."""
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


def extract_events(event_list):
    """Extrai eventos de uma lista de dicionários."""
    return [event_dict["event"] for event_dict in event_list]


def extract_events_vectorized(events_series):
    """Extrai eventos de forma vetorizada para performance."""
    return events_series.apply(lambda x: [event_dict["event"] for event_dict in x])


# =============================================================================
# FUNÇÕES DE CÁLCULO DE MÉTRICAS BÁSICAS
# =============================================================================

def count_subsequence_occurrences(pattern, sequence):
    """Conta quantas vezes o padrão aparece como subsequência na sequência."""
    if not pattern or not sequence:
        return 0
    
    count = 0
    seq_len = len(sequence)
    pattern_len = len(pattern)
    
    # Para cada posição inicial possível
    for start in range(seq_len - pattern_len + 1):
        # Tentar casar o padrão começando desta posição
        pattern_idx = 0
        for i in range(start, seq_len):
            if sequence[i] == pattern[pattern_idx]:
                pattern_idx += 1
                if pattern_idx == pattern_len:
                    count += 1
                    break
    
    return count


def get_supports(formatted, minsup, sequence_list):
    """Calcula I-support para uma sequência - conta todas as ocorrências."""
    seq_key = tuple(sequence_list)
    
    if seq_key in _SUPPORT_CACHE:
        return _SUPPORT_CACHE[seq_key]
    
    # Contar todas as ocorrências do padrão em todas as sequências
    total_matches = sum(count_subsequence_occurrences(sequence_list, seq) for seq in formatted)
    
    _SUPPORT_CACHE[seq_key] = total_matches
    return total_matches


def get_sequence_ids(target, data):
    """Retorna IDs das sequências que contêm o padrão target - vetorizado."""
    mask = data["events"].apply(lambda x: is_subsequence(target, x))
    return data.loc[mask, "key"].tolist()


def get_sequence_grade(ids, data):
    """Calcula estatísticas de notas para as sequências - otimizado."""
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
    """Calcula estatísticas temporais para as sequências - otimizado."""
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
    """Calcula estatísticas de comprimento das sequências - vetorizado."""
    lengths = data["events"].apply(len).values
    return int(lengths.min()), int(lengths.max()), float(lengths.mean()), float(lengths.std(ddof=1))


# =============================================================================
# FUNÇÕES DE CÁLCULO DE JACCARD (SIMILARIDADE/DISTÂNCIA)
# =============================================================================

def jaccard_similarity(seq1, seq2):
    """Calcula coeficiente de Jaccard entre duas sequências."""
    set1 = set(seq1)
    set2 = set(seq2)
    
    if not set1 and not set2:
        return 1.0
    
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    
    return intersection / union if union > 0 else 0.0


def jaccard_distance(seq1, seq2):
    """Calcula distância de Jaccard (1 - similaridade) em porcentagem."""
    return (1 - jaccard_similarity(seq1, seq2)) * 100


def calculate_pattern_jaccard_distance(pattern, all_patterns_same_size):
    """
    Calcula a distância média de Jaccard de um padrão em relação aos outros padrões do mesmo tamanho.
    Retorna porcentagem média de diferença (0% = idêntico, 100% = totalmente diferente).
    """
    if len(all_patterns_same_size) <= 1:
        return 100.0  # Se é o único padrão, é 100% diferente dos outros (não há outros)
    
    distances = []
    for other_pattern in all_patterns_same_size:
        if pattern != other_pattern:  # Não comparar com si mesmo
            distances.append(jaccard_distance(pattern, other_pattern))
    
    return statistics.mean(distances) if distances else 100.0


def calculate_scenery_jaccard_diversity(all_patterns):
    """
    Calcula a diversidade geral do cenário usando distância de Jaccard.
    Compara todos os pares de padrões e retorna a média.
    Retorna porcentagem de diversidade (0% = todos iguais, 100% = todos diferentes).
    """
    if len(all_patterns) <= 1:
        return 0.0
    
    distances = []
    for i, pattern1 in enumerate(all_patterns):
        for pattern2 in all_patterns[i+1:]:
            distances.append(jaccard_distance(pattern1, pattern2))
    
    return statistics.mean(distances) if distances else 0.0


# =============================================================================
# FUNÇÕES DE ESCRITA E PERSISTÊNCIA DE DADOS
# =============================================================================

def write_result(data, file_name, path, save_csv=False):
    """Salva resultados com métricas calculadas - otimizado."""
    def convert_to_python_types(obj):
        if isinstance(obj, dict):
            return {k: convert_to_python_types(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_to_python_types(i) for i in obj]
        elif isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        return obj

    data = convert_to_python_types(data)
    
    json_path = f"./{path}/json"
    os.makedirs(json_path, exist_ok=True)

    with open(f"{json_path}/{file_name}.json", "w") as _file:
        json.dump(data, _file, indent=2)

    if save_csv:
        write_csv(file_name, path)


def write_csv(file_name, path):
    """Converte JSON para CSV - otimizado e com todas as métricas."""
    with open(f"./{path}/json/{file_name}.json") as json_file:
        json_data = json.load(json_file)

    csv_path = f"./{path}/csv"
    os.makedirs(csv_path, exist_ok=True)
    
    # Coletar todas as sequências de uma vez
    all_sequences = []
    for key in json_data.keys():
        for seq in json_data[key]["sequences"]:
            seq_copy = seq.copy()
            # Converter lista de IDs para contagem
            seq_copy["ids"] = len(seq_copy["ids"])
            # Converter sequência para string com separador
            seq_copy["sequence"] = ">".join(seq_copy["sequence"])
            # Garantir que jaccard_distance está presente
            if "jaccard_distance" not in seq_copy:
                seq_copy["jaccard_distance"] = 0.0
            all_sequences.append(seq_copy)
    
    if all_sequences:
        df = pd.DataFrame(all_sequences)
        # Garantir ordem consistente das colunas
        ordered_cols = [
            "sequence_size", "sequence", "total", "total_time_span", "avg_time_span",
            "i_support", "s_support", "ids", "grade_avg", "grade_avg_deviation",
            "grade_median", "grade_mode", "max_grade", "jaccard_distance"
        ]
        # Usar apenas colunas que existem
        existing_cols = [col for col in ordered_cols if col in df.columns]
        df = df[existing_cols]
        df.to_csv(f"{csv_path}/{file_name}.csv", sep=";", index=False)


# =============================================================================
# FUNÇÕES DE GERAÇÃO DE RELATÓRIOS CONSOLIDADOS
# =============================================================================

def generate_total_csv(results_path):
    """Gera CSV consolidado com todos os cenários - otimizado."""
    dfs = []
    for scenery in sceneries_names:
        csv_file = f"{results_path}/csv/{scenery}.csv"
        if os.path.exists(csv_file):
            df = pd.read_csv(csv_file, sep=";")
            df["scenery"] = scenery.split("-")[0]
            dfs.append(df)
    
    if dfs:
        total = pd.concat(dfs, ignore_index=True)
        cols = ["scenery"] + [c for c in total.columns if c != "scenery"]
        total = total[cols].round(2)
        total.to_csv(f"{results_path}/total.csv", sep=";", index=False)


def get_top_k(results_path, k=5):
    """Gera CSV com top K padrões mais frequentes por cenário - otimizado."""
    dfs = []
    for scenery in sceneries_names:
        csv_file = f"{results_path}/csv/{scenery}.csv"
        if os.path.exists(csv_file):
            df = pd.read_csv(csv_file, sep=";")
            df = df[df["sequence_size"] > 1]
            if not df.empty:
                df = df.nlargest(k, "total") # type: ignore
                df["scenery"] = scenery.split("-")[0]
                dfs.append(df)
    
    if dfs:
        total = pd.concat(dfs, ignore_index=True)
        cols = ["scenery"] + [c for c in total.columns if c != "scenery"]
        total = total[cols].sort_values(by=["scenery", "total"], ascending=[True, False])
        total.to_csv(f"{results_path}/top_k.csv", sep=";", index=False)


def format_stat_with_std(values, decimals=2):
    """
    Formata estatística com média e desvio padrão.
    
    Args:
        values: Lista de valores ou pandas Series
        decimals: Número de casas decimais
    
    Returns:
        String formatada como "média (+- desvio)"
    """
    # Converter para lista se for pandas Series
    if hasattr(values, 'tolist'):
        values = values.tolist()
    
    # Verificar se está vazio
    if not values or len(values) == 0:
        return "0.00 (+- 0)"
    
    try:
        mean_val = statistics.mean(values)
        std_val = statistics.stdev(values)
        return f"{mean_val:.{decimals}f} (+- {std_val:.{decimals}f})"
    except statistics.StatisticsError:
        # Apenas 1 valor, sem desvio padrão
        mean_val = statistics.mean(values)
        return f"{mean_val:.{decimals}f} (+- 0)"
    except:
        return "0.00 (+- 0)"


def calculate_support_statistics(scenery, data):
    """
    Calcula estatísticas de suporte para um cenário.
    
    Args:
        scenery: Nome do cenário
        data: DataFrame com dados do cenário
    
    Returns:
        Dicionário com estatísticas de suporte
    """
    i_support = format_stat_with_std(data['i_support'])
    s_support = format_stat_with_std(data['ids'])
    
    return {
        "scenery": scenery.split("-")[0],  # Manter como string
        "i_support": i_support,
        "s_support": s_support
    }


def get_supports_by_scenery(results_path):
    """Calcula suportes médios por cenário - modularizado."""
    # Carregar todos os CSVs
    datas = []
    for scenery in sceneries_names:
        csv_file = f"{results_path}/csv/{scenery}.csv"
        if os.path.exists(csv_file):
            df = pd.read_csv(csv_file, sep=";")
            df["scenery"] = scenery.split("-")[0]
            datas.append((scenery, df))
    
    if not datas:
        print("Aviso: Nenhum arquivo CSV encontrado para calcular suportes")
        return
    
    # Calcular estatísticas de suporte
    support_stats = [calculate_support_statistics(scenery, data) for scenery, data in datas]
    supports_df = pd.DataFrame(support_stats)
    
    # Garantir que scenery seja string em ambos os DataFrames
    supports_df["scenery"] = supports_df["scenery"].astype(str)
    
    # Atualizar general_info
    general_info = pd.read_csv(f"{results_path}/general_info.csv", sep=";")
    general_info["scenery"] = general_info["scenery"].astype(str)
    
    # Fazer merge mantendo todas as colunas do general_info
    general_info = pd.merge(general_info, supports_df, on="scenery", how="left", suffixes=("_old", ""))
    
    # Remover colunas antigas se existirem
    cols_to_drop = [col for col in general_info.columns if col.endswith("_old")]
    if cols_to_drop:
        general_info = general_info.drop(columns=cols_to_drop)
    
    # Arredondar apenas colunas numéricas (preserva strings como "média (+- desvio)")
    numeric_cols = general_info.select_dtypes(include=[np.number]).columns
    general_info[numeric_cols] = general_info[numeric_cols].round(2)
    
    general_info.to_csv(f"{results_path}/general_info.csv", sep=";", index=False)


def parse_mean_std(text: str):
    """
    Extrai média e desvio padrão de string formatada.
    
    Args:
        text: String no formato "média (+- desvio)"
    
    Returns:
        Tupla (mean, std) ou (nan, nan) se inválido
    """
    try:
        mean_part, rest = text.split(" (+- ")
        std_part = rest.rstrip(")")
        return float(mean_part), float(std_part)
    except:
        return np.nan, np.nan


def alter_support_to_percentage(results_path):
    """
    Calcula porcentagens de suporte - modularizado.
    
    Args:
        results_path: Caminho dos resultados
        total_reference: Valor de referência para 100%
    """
    gen_info = pd.read_csv(f"{results_path}/general_info.csv", sep=";")
    
    parsed = gen_info["s_support"].apply(parse_mean_std)
    gen_info["s_support_percentage"] = parsed.apply(
        lambda t: round((t[0] / total_sequences) * 100, 4) if pd.notna(t[0]) else np.nan
    )
    gen_info["s_support_std_percentage"] = parsed.apply(
        lambda t: round((t[1] / total_sequences) * 100, 4) if pd.notna(t[1]) else np.nan
    )
    
    gen_info.to_csv(f"{results_path}/general_info.csv", sep=";", index=False)


# =============================================================================
# FUNÇÕES DE PROCESSAMENTO DE PADRÕES E CENÁRIOS
# =============================================================================

def compute_pattern_metrics(seq, formatted, all_sequences, original_seq, max_grade, minsup):
    """
    Calcula todas as métricas para um único padrão.
    
    Args:
        seq: Dicionário com informações do padrão da mineração
        formatted: Sequências formatadas para cálculo de suporte
        all_sequences: DataFrame com todas as sequências
        original_seq: DataFrame original com dados temporais
        max_grade: Nota máxima possível
        minsup: Suporte mínimo
    
    Returns:
        Dicionário com todas as métricas do padrão
    """
    sequence_list = seq["sequence"]
    i_support = get_supports(formatted, minsup, sequence_list)
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
    """
    Encontra os padrões mais e menos repetidos.
    
    Args:
        sequences: Lista de dicionários com métricas dos padrões
    
    Returns:
        Tupla (most_repeated, least_repeated)
    """
    most_repeated = {"total": 0}
    least_repeated = {"total": float('inf')}
    
    for sequence in sequences:
        if sequence["total"] > most_repeated["total"]:
            most_repeated = sequence.copy()
        if 1 < sequence["total"] < least_repeated["total"]:
            least_repeated = sequence.copy()
    
    return most_repeated, least_repeated


def collect_statistics(sequences):
    """
    Coleta estatísticas de comprimentos e tempos dos padrões.
    
    Args:
        sequences: Lista de dicionários com métricas dos padrões
    
    Returns:
        Tupla (lengths, times)
    """
    lengths = []
    times = []
    
    for sequence in sequences:
        lengths.append(sequence["sequence_size"])
        if sequence.get("initial_time", 0) > 0:
            times.extend([sequence["initial_time"], sequence["final_time"]])
    
    return lengths, times


def group_patterns_by_size(final_result):
    """
    Agrupa padrões por tamanho para cálculo eficiente de Jaccard.
    
    Args:
        final_result: Dicionário com resultados organizados por tamanho
    
    Returns:
        Tupla (patterns_by_size, all_patterns)
    """
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
    """
    Aplica cálculo de distância Jaccard para todos os padrões.
    
    Args:
        final_result: Dicionário com resultados
        patterns_by_size: Dicionário de padrões agrupados por tamanho
    """
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
    """
    Calcula estatísticas gerais do cenário.
    
    Args:
        lengths: Lista de comprimentos dos padrões
        times: Lista de timestamps
        original_seq: DataFrame original
        total_sequences: Total de sequências encontradas
        scenery_diversity: Diversidade Jaccard do cenário
        all_jaccard_distances: Lista de distâncias Jaccard
        scenery: Nome do cenário
        max_grade: Nota máxima
        minsup: Suporte mínimo
    
    Returns:
        Dicionário com informações gerais do cenário
    """
    lengths.sort()
    times = [t for t in times if t > 0]
    times.sort()
    
    min_len, max_len, avg_len, dev_len = get_sequences_length(original_seq)
    
    try:
        avg_pattern_length = f"{statistics.mean(lengths):.2f} (+- {statistics.stdev(lengths):.2f})"
    except:
        avg_pattern_length = f"{statistics.mean(lengths):.2f} (+- 0)"
    
    try:
        avg_jaccard = f"{statistics.mean(all_jaccard_distances):.2f} (+- {statistics.stdev(all_jaccard_distances):.2f})"
    except:
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


def calculate_metrics_for_scenery(scenery, mining_path, original_data_path, minsup=0.08):
    """Calcula todas as métricas para um cenário específico - otimizado e modularizado."""
    global _SUPPORT_CACHE
    _SUPPORT_CACHE.clear()
    
    # 1. Carregar e preparar dados
    mining_results = load_mining_results(scenery, mining_path)
    file_name = read_params(scenery)
    all_sequences = load_data(file_name)
    
    if all_sequences is None:
        return None, None
    
    original_seq = all_sequences.copy()
    max_grade = int(all_sequences["max_grade"].iloc[0])
    formatted = format_tf_data(all_sequences)
    all_sequences["events"] = extract_events_vectorized(all_sequences["events"])
    
    # 2. Inicializar estruturas
    final_result = {
        f"{i}_sequences": {"sequences": [], "most_repeated": {}, "least_repeated": {}}
        for i in range(1, len(mining_results) + 1)
    }
    
    # 3. Primeira passagem: calcular métricas básicas para cada padrão
    for key, data in mining_results.items():
        for seq in data["sequences"]:
            pattern_metrics = compute_pattern_metrics(
                seq, formatted, all_sequences, original_seq, max_grade, minsup
            )
            final_result[key]["sequences"].append(pattern_metrics)
        
        # Encontrar extremos
        most, least = find_extreme_patterns(final_result[key]["sequences"])
        final_result[key]["most_repeated"] = most
        final_result[key]["least_repeated"] = least
    
    # 4. Agrupar padrões e calcular Jaccard
    patterns_by_size, all_patterns = group_patterns_by_size(final_result)
    apply_jaccard_distances(final_result, patterns_by_size)
    
    # 5. Coletar estatísticas
    all_lengths = []
    all_times = []
    all_jaccard_distances = []
    
    for key, data in final_result.items():
        lengths, times = collect_statistics(data["sequences"])
        all_lengths.extend(lengths)
        all_times.extend(times)
        
        for sequence in data["sequences"]:
            all_jaccard_distances.append(sequence["jaccard_distance"])
    
    # 6. Calcular métricas gerais
    scenery_diversity = calculate_scenery_jaccard_diversity(all_patterns)
    total_sequences = sum(len(data["sequences"]) for data in mining_results.values())
    
    general_info = calculate_general_statistics(
        all_lengths, all_times, original_seq, total_sequences,
        scenery_diversity, all_jaccard_distances,
        scenery, max_grade, minsup
    )
    
    return final_result, general_info


def initialize_general_info(results_path):
    """
    Inicializa ou carrega DataFrame de informações gerais.
    
    Args:
        results_path: Caminho dos resultados
    
    Returns:
        DataFrame de informações gerais
    """
    general_info_columns = {
        "scenery": [], "minsup": [], "max_grade": [], "total_sequences": [],
        "time_span_in_days": [], "longest_pattern_length": [], "shortest_pattern_length": [],
        "average_pattern_length": [], "longest_sequence_length": [], "shortest_sequence_length": [],
        "average_sequence_length": [], "jaccard_diversity": [], "avg_jaccard_distance": [],
        "elapsed_time": [], "i_support": [], "s_support": [],
    }
    
    general_info_path = f"{results_path}/general_info.csv"
    if os.path.exists(general_info_path):
        return pd.read_csv(general_info_path, sep=";")
    else:
        return pd.DataFrame(general_info_columns)


def process_single_scenery(scenery, index, total, mining_path):
    """
    Processa um único cenário e retorna seus resultados.
    
    Args:
        scenery: Nome do cenário
        index: Índice atual (para logging)
        total: Total de cenários
        mining_path: Caminho dos resultados de mineração
    
    Returns:
        Tupla (final_result, scenery_info, elapsed_time) ou (None, None, 0) em caso de erro
    """
    begin = time.time()
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] [{index}/{total}] Processando {scenery}...", end=" | ")
    
    try:
        final_result, scenery_info = calculate_metrics_for_scenery(
            scenery, mining_path, read_params(scenery), minsup=minsup
        )
        
        if final_result is None or scenery_info is None:
            print("ERRO: Dados não encontrados")
            return None, None, 0
        
        elapsed = time.time() - begin
        scenery_info["elapsed_time"] = elapsed
        
        print(f"Concluído em {elapsed:.2f}s")
        return final_result, scenery_info, elapsed
        
    except Exception as e:
        print(f"ERRO: {str(e)}")
        import traceback
        traceback.print_exc()
        return None, None, 0


def update_general_info(general_info, new_lines):
    """
    Atualiza DataFrame de informações gerais com novos dados.
    
    Args:
        general_info: DataFrame existente
        new_lines: Lista de dicionários com novos dados
    
    Returns:
        DataFrame atualizado
    """
    if not new_lines:
        return general_info
    
    new_lines_df = pd.DataFrame(new_lines)
    
    # Garantir que a coluna scenery seja string em ambos os DataFrames
    if not general_info.empty:
        general_info["scenery"] = general_info["scenery"].astype(str)
    new_lines_df["scenery"] = new_lines_df["scenery"].astype(str)
    
    # Atualizar ou adicionar linhas preservando colunas existentes
    for _, row in new_lines_df.iterrows():
        if row["scenery"] in general_info["scenery"].values:
            idx = general_info[general_info["scenery"] == row["scenery"]].index[0]
            # Atualizar apenas as colunas presentes em row (preserva outras colunas)
            for col in row.index:
                general_info.loc[idx, col] = row[col]
        else:
            general_info = pd.concat([general_info, pd.DataFrame([row])], ignore_index=True)
    
    # Garantir tipo string antes de ordenar
    general_info["scenery"] = general_info["scenery"].astype(str)
    
    # Ordenar convertendo para inteiro temporariamente para ordem numérica correta
    try:
        general_info["_scenery_sort"] = general_info["scenery"].astype(int)
        general_info = general_info.sort_values(by="_scenery_sort", ascending=True).reset_index(drop=True)
        general_info = general_info.drop(columns=["_scenery_sort"])
    except:
        # Se não conseguir converter para int, ordenar como string mesmo
        general_info = general_info.sort_values(by="scenery", ascending=True).reset_index(drop=True)
    
    # Arredondar apenas colunas numéricas (preserva strings como "média (+- desvio)")
    numeric_cols = general_info.select_dtypes(include=[np.number]).columns
    general_info[numeric_cols] = general_info[numeric_cols].round(2)
    
    return general_info


def generate_consolidated_reports(results_path):
    """
    Gera todos os relatórios consolidados.
    
    Args:
        results_path: Caminho dos resultados
    """
    print("\nGerando relatórios consolidados...")
    try:
        print("  - Calculando suportes por cenário...")
        get_supports_by_scenery(results_path)
        
        print("  - Gerando total.csv...")
        generate_total_csv(results_path)
        
        print("  - Gerando top_k.csv...")
        get_top_k(results_path)
        
        print("  - Calculando porcentagens de suporte...")
        alter_support_to_percentage(results_path)
        
        print("✓ Relatórios consolidados gerados com sucesso!")
    except Exception as e:
        print(f"ERRO ao gerar relatórios: {str(e)}")
        import traceback
        traceback.print_exc()


# =============================================================================
# FUNÇÃO PRINCIPAL
# =============================================================================

def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Calcula metricas (Jaccard, suportes, notas) por cenario.")
    parser.add_argument("-co", "--course", type=int, required=True, help="Numero do curso (ex.: 2060, 2065)")
    parser.add_argument("-act", "--activity", type=int, required=True, help="Numero da atividade (inteiro)")
    parser.add_argument("-ms", "--minsup", type=float, default=0.08, help="Suporte minimo usado na mineracao (default: 0.08)")
    parser.add_argument(
        "-ts", "--total-sequences", type=float, default=11974.0,
        help="Total de referencia para normalizacao de s_support em %% (default: 11974)",
    )
    parser.add_argument("--use-split", action="store_true", help="Usa variantes _high/_low por nota")
    parser.add_argument("--sceneries-dir", type=str, default="outputs/sceneries", help="Raiz dos cenarios de entrada")
    parser.add_argument("--mining-dir", type=str, default="outputs/mining_results", help="Raiz dos resultados de mineracao")
    parser.add_argument("--out-dir", type=str, default="outputs/results", help="Raiz de saida das metricas")
    return parser.parse_args(argv)


def main(args):
    """Calcula métricas para todos os cenários - modularizado e otimizado."""
    global COURSE, activity, use_split, minsup, total_sequences
    global sceneries_names, sceneries_root, mining_root, results_root
    COURSE = args.course
    activity = args.activity
    use_split = args.use_split
    minsup = args.minsup
    total_sequences = args.total_sequences
    sceneries_root = args.sceneries_dir
    mining_root = args.mining_dir
    results_root = args.out_dir

    mining_path = f"{mining_root}/{COURSE}/{activity}"
    results_path = f"{results_root}/{COURSE}/{activity}"
    
    # Validação inicial
    if not os.path.exists(mining_path):
        print(f"ERRO: Diretório de resultados de mineração não encontrado: {mining_path}")
        print("Execute primeiro o script process_mining.py")
        return
    
    # Configuração
    if use_split:
        sceneries_names = [f"{scenery}_{suffix}" for scenery in sceneries_names for suffix in ["high", "low"]]
    
    print(f"Iniciando cálculo de métricas...")
    print(f"Curso: {COURSE}, Atividade: {activity}")
    print(f"Total de cenários: {len(sceneries_names)}")
    print(f"Resultados serão salvos em: {results_path}\n")
    
    os.makedirs(results_path, exist_ok=True)
    
    # Inicializar informações gerais
    general_info = initialize_general_info(results_path)
    new_lines = []
    
    # Processar cada cenário
    for index, scenery in enumerate(sceneries_names, 1):
        final_result, scenery_info, elapsed = process_single_scenery(
            scenery, index, len(sceneries_names), mining_path
        )
        
        if final_result is not None and scenery_info is not None:
            new_lines.append(scenery_info)
            write_result(final_result, scenery, results_path, True)
    
    # Atualizar e salvar informações gerais
    general_info = update_general_info(general_info, new_lines)
    
    # IMPORTANTE: Salvar general_info.csv ANTES dos relatórios consolidados
    # porque get_supports_by_scenery() precisa ler este arquivo
    general_info.to_csv(f"{results_path}/general_info.csv", sep=";", index=False)
    print(f"\n✓ general_info.csv salvo com {len(general_info)} cenários")
    
    # Gerar relatórios consolidados (usa general_info.csv salvo acima)
    generate_consolidated_reports(results_path)
    
    print(f"\nCálculo de métricas concluído! Resultados salvos em: {results_path}")


if __name__ == "__main__":
    main(parse_args())
