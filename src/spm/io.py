"""Camada de entrada/saída do pacote: isola todo o acesso a disco.

Carrega cenários e resultados de mineração, grava resultados de métricas (JSON e
CSV) e gera os relatórios consolidados. As funções de cálculo puro vivem em
:mod:`spm.metrics`; a orquestração por curso/atividade em :mod:`spm.pipeline`.
"""
import json
import os

import numpy as np
import pandas as pd

from .metrics import calculate_support_statistics, parse_mean_std


# =============================================================================
# CENÁRIOS E RESULTADOS DE MINERAÇÃO
# =============================================================================

def load_sceneries(file_path):
    """Carrega um JSON de cenário (lista de sequências por usuário); None se ausente."""
    if not os.path.exists(file_path):
        print(f"Warning: {file_path} not found")
        return None
    with open(file_path, "r") as f:
        return json.load(f)


def save_mining(mining_output, scenery, output_path):
    """Grava o dicionário de mineração em ``{output_path}/{scenery}_mining.json``."""
    os.makedirs(output_path, exist_ok=True)
    output_file = os.path.join(output_path, f"{scenery}_mining.json")
    with open(output_file, "w+") as f:
        json.dump(mining_output, f, indent=2)


def load_mining(scenery, mining_path):
    """Carrega o dicionário de mineração de um cenário."""
    mining_file = os.path.join(mining_path, f"{scenery}_mining.json")
    with open(mining_file, "r") as f:
        return json.load(f)


# =============================================================================
# RESULTADOS DE MÉTRICAS (JSON + CSV por cenário)
# =============================================================================

def write_result(data, file_name, path, save_csv=False):
    """Grava o detalhamento de um cenário em ``{path}/json/{file_name}.json``."""
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
    """Converte o JSON do cenário em CSV (``{path}/csv/{file_name}.csv``)."""
    with open(f"./{path}/json/{file_name}.json") as json_file:
        json_data = json.load(json_file)

    csv_path = f"./{path}/csv"
    os.makedirs(csv_path, exist_ok=True)

    all_sequences = []
    for key in json_data.keys():
        for seq in json_data[key]["sequences"]:
            seq_copy = seq.copy()
            seq_copy["ids"] = len(seq_copy["ids"])
            seq_copy["sequence"] = ">".join(seq_copy["sequence"])
            if "jaccard_distance" not in seq_copy:
                seq_copy["jaccard_distance"] = 0.0
            all_sequences.append(seq_copy)

    if all_sequences:
        df = pd.DataFrame(all_sequences)
        ordered_cols = [
            "sequence_size", "sequence", "total", "total_time_span", "avg_time_span",
            "i_support", "s_support", "ids", "grade_avg", "grade_avg_deviation",
            "grade_median", "grade_mode", "max_grade", "jaccard_distance"
        ]
        existing_cols = [col for col in ordered_cols if col in df.columns]
        df = df[existing_cols]
        df.to_csv(f"{csv_path}/{file_name}.csv", sep=";", index=False)


# =============================================================================
# general_info.csv
# =============================================================================

def initialize_general_info(results_path):
    """Carrega o general_info.csv existente ou cria um DataFrame vazio com o schema."""
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
    return pd.DataFrame(general_info_columns)


def update_general_info(general_info, new_lines):
    """Atualiza/insere linhas no general_info, ordena por cenário e arredonda."""
    if not new_lines:
        return general_info

    new_lines_df = pd.DataFrame(new_lines)

    if not general_info.empty:
        general_info["scenery"] = general_info["scenery"].astype(str)
    new_lines_df["scenery"] = new_lines_df["scenery"].astype(str)

    for _, row in new_lines_df.iterrows():
        if row["scenery"] in general_info["scenery"].values:
            idx = general_info[general_info["scenery"] == row["scenery"]].index[0]
            for col in row.index:
                general_info.loc[idx, col] = row[col]
        else:
            general_info = pd.concat([general_info, pd.DataFrame([row])], ignore_index=True)

    general_info["scenery"] = general_info["scenery"].astype(str)

    try:
        general_info["_scenery_sort"] = general_info["scenery"].astype(int)
        general_info = general_info.sort_values(by="_scenery_sort", ascending=True).reset_index(drop=True)
        general_info = general_info.drop(columns=["_scenery_sort"])
    except Exception:
        general_info = general_info.sort_values(by="scenery", ascending=True).reset_index(drop=True)

    numeric_cols = general_info.select_dtypes(include=[np.number]).columns
    general_info[numeric_cols] = general_info[numeric_cols].round(2)

    return general_info


# =============================================================================
# RELATÓRIOS CONSOLIDADOS
# =============================================================================

def generate_total_csv(results_path, sceneries_names):
    """Gera ``total.csv`` consolidando todos os cenários."""
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


def get_top_k(results_path, sceneries_names, k=5):
    """Gera ``top_k.csv`` com os K padrões mais frequentes por cenário."""
    dfs = []
    for scenery in sceneries_names:
        csv_file = f"{results_path}/csv/{scenery}.csv"
        if os.path.exists(csv_file):
            df = pd.read_csv(csv_file, sep=";")
            df = df[df["sequence_size"] > 1]
            if not df.empty:
                df = df.nlargest(k, "total")  # type: ignore
                df["scenery"] = scenery.split("-")[0]
                dfs.append(df)

    if dfs:
        total = pd.concat(dfs, ignore_index=True)
        cols = ["scenery"] + [c for c in total.columns if c != "scenery"]
        total = total[cols].sort_values(by=["scenery", "total"], ascending=[True, False])
        total.to_csv(f"{results_path}/top_k.csv", sep=";", index=False)


def get_supports_by_scenery(results_path, sceneries_names):
    """Calcula suportes médios por cenário e os mescla no general_info.csv."""
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

    support_stats = [calculate_support_statistics(scenery, data) for scenery, data in datas]
    supports_df = pd.DataFrame(support_stats)
    supports_df["scenery"] = supports_df["scenery"].astype(str)

    general_info = pd.read_csv(f"{results_path}/general_info.csv", sep=";")
    general_info["scenery"] = general_info["scenery"].astype(str)

    general_info = pd.merge(general_info, supports_df, on="scenery", how="left", suffixes=("_old", ""))

    cols_to_drop = [col for col in general_info.columns if col.endswith("_old")]
    if cols_to_drop:
        general_info = general_info.drop(columns=cols_to_drop)

    numeric_cols = general_info.select_dtypes(include=[np.number]).columns
    general_info[numeric_cols] = general_info[numeric_cols].round(2)

    general_info.to_csv(f"{results_path}/general_info.csv", sep=";", index=False)


def alter_support_to_percentage(results_path, total_sequences):
    """Adiciona as colunas de porcentagem de s_support ao general_info.csv."""
    gen_info = pd.read_csv(f"{results_path}/general_info.csv", sep=";")

    parsed = gen_info["s_support"].apply(parse_mean_std)
    gen_info["s_support_percentage"] = parsed.apply(
        lambda t: round((t[0] / total_sequences) * 100, 4) if pd.notna(t[0]) else np.nan
    )
    gen_info["s_support_std_percentage"] = parsed.apply(
        lambda t: round((t[1] / total_sequences) * 100, 4) if pd.notna(t[1]) else np.nan
    )

    gen_info.to_csv(f"{results_path}/general_info.csv", sep=";", index=False)


def generate_consolidated_reports(results_path, sceneries_names, total_sequences):
    """Gera todos os relatórios consolidados, na ordem correta."""
    print("\nGerando relatórios consolidados...")
    try:
        print("  - Calculando suportes por cenário...")
        get_supports_by_scenery(results_path, sceneries_names)

        print("  - Gerando total.csv...")
        generate_total_csv(results_path, sceneries_names)

        print("  - Gerando top_k.csv...")
        get_top_k(results_path, sceneries_names)

        print("  - Calculando porcentagens de suporte...")
        alter_support_to_percentage(results_path, total_sequences)

        print("✓ Relatórios consolidados gerados com sucesso!")
    except Exception as e:
        print(f"ERRO ao gerar relatórios: {str(e)}")
        import traceback
        traceback.print_exc()
