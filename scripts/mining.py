import os.path
import json
from gsppy.gsp import GSP
from prefixspan import PrefixSpan
import pandas as pd
import csv
import time
import statistics
import datetime
import sys
import numpy as np

# Config centralizada (antes duplicada no topo de cada script).
# Os scripts rodam a partir da raiz do repo (como os caminhos relativos abaixo).
sys.path.insert(0, "src")
from spm.config import (
    SCENERIES_NAMES as sceneries_names,
    COURSE,
    ACTIVITY as activity,
    USE_SPLIT as use_split,
    MINSUP as minsup,
)




def generate_data(data):
    # pd.read_json(file_name)
    # Criar uma lista de dicionários diretamente do JSON
    rows = []
    for item in data:
        for i in item["events"]:
            rows.append(
                {
                    "key": item["key"],
                    "temporal_folding": item["temporal_folding"],
                    "grade": item["grade"],
                    "max_grade": item["max_grade"],
                    "events": i,  # Armazenar toda a lista de eventos
                }
            )

    # Criar o DataFrame
    df = pd.DataFrame(rows)
    df.to_csv("test.csv", sep=";", index=False)
    return df


def gsp_mining(sequences_list: list, minsup: float = 0.08) -> list:
    return GSP(sequences_list).search(minsup)


def prefix_mining(sequences_list: list, minsup: float = 0.08, subsequence=None) -> list:
    ps = PrefixSpan(sequences_list)
    ps.minlen = 2
    min_support = len(sequences_list) * minsup

    if subsequence:
        res = ps.frequent(min_support, filter=lambda patt, matches: is_subsequence(subsequence, patt) and len(patt) > 1)
        return res

    res = ps.frequent(min_support)

    max_seq_len = 0
    for index in res:
        if len(index[1]) > max_seq_len:
            max_seq_len = len(index[1])

    n_sequences = [{} for _ in range(max_seq_len)]

    for index in res:
        n_sequences[len(index[1]) - 1][f"{index[1]}"] = index[0]

    return n_sequences


def format_tf_data(s) -> list:
    data = []
    s = pd.DataFrame(data=s).to_dict(orient="records")
    for user_sequence in s:
        tf = user_sequence["temporal_folding"]
        # if tf:
        #     sessions = [session for session in user_sequence["events"]]
        #     for session in sessions:
        #         events = [event["event"] for event in session]
        #         data.append(events)
        # else:
        events = [event["event"] for event in user_sequence["events"]]
        data.append(events)

    return data


def read_params(file: str) -> str:
    global use_split
    return f"./outputs/sceneries/{COURSE}/{activity}/split_grade/{file}.json" if use_split else f"./outputs/sceneries/{COURSE}/{activity}/{file}.json"


def write_result(data, file_name, path=f"outputs/results/{COURSE}/{activity}", save_csv=False):
    # Convert data to native Python types for JSON serialization
    def convert_to_python_types(obj):
        if isinstance(obj, dict):
            return {k: convert_to_python_types(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_to_python_types(i) for i in obj]
        elif isinstance(obj, (np.integer, np.int64)):  # type: ignore # Handle numpy integer types
            return int(obj)
        elif isinstance(obj, (np.floating, np.float64)):  # type: ignore # Handle numpy float types
            return float(obj)
        elif isinstance(obj, np.ndarray):  # Handle numpy arrays
            return obj.tolist()
        return obj

    data = convert_to_python_types(data)  # Apply conversion

    # Create directories if they don't exist
    if not os.path.exists(f"./{path}/json"):
        os.makedirs(f"./{path}/json")

    # Write JSON file
    with open(f"./{path}/json/{file_name}.json", "w+") as _file:
        json.dump(data, _file)

    # Optionally save as CSV
    if save_csv:
        write_csv(file_name, path)


def write_csv(file_name, path=f"outputs/results/{COURSE}/{activity}"):
    json_file = open(f"./{path}/json/{file_name}.json")
    json_data = json.load(json_file)

    # Create directories if they don't exist
    if not os.path.exists(f"./{path}/csv"):
        os.makedirs(f"./{path}/csv")

    with open(f"./{path}/csv/{file_name}.csv", "w+", newline="\n") as f:
        writer = csv.DictWriter(f, delimiter=";", fieldnames=json_data["2_sequences"]["sequences"][0])
        writer.writeheader()

        for key in json_data.keys():
            for seq in json_data[key]["sequences"]:
                # seq["grade"] = seq["grade"]["avg"]
                # seq["grave_median"] = seq["grade"]["median"]
                # seq["grave_mode"] = seq["grade"]["mode"]
                # del seq["grade"]
                seq["ids"] = len(seq["ids"])
                seq["sequence"] = ">".join(seq["sequence"])
            # json_data[key]["sequences"]["sequence"] = json_data[key]["sequences"]["sequence"].join('>')
            # print(json_data[key]["sequences"], end="\n\n")
            # writer.writerows(json_data[key]["sequences"])
            writer.writerows(json_data[key]["sequences"])
    json_file.close()


def remap_keys(user_sequences, seq_quantities):
    def process_key(key):
        modified_key = key.replace("[", "").replace("]", "").replace("'", "")
        return [part.strip() for part in modified_key.split(",")]

    return {
        f"{seq_quantities}_sequences": [{"sequence": process_key(k), "total": v} for k, v in user_sequences.items()]
    }


def is_subsequence(subseq, sequence):
    i = 0
    for elem in sequence:
        if i < len(subseq) and elem == subseq[i]:
            i += 1
        if i == len(subseq):
            return True
    return False


def is_sublist_with_gap(sub_list, main_list, gap=20):
    main_len, sub_len = len(main_list), len(sub_list)
    if sub_len == 0:
        return True

    start = 0
    for sub_elem in sub_list:
        found = False
        while start < main_len and (start - (sub_len - 1)) <= gap:
            if main_list[start] == sub_elem:
                found = True
                break
            start += 1
        if not found:
            return False
        start += 1
    return True


def extract_events(event_list):
    data = [event_dict["event"] for event_dict in event_list]
    return data


def get_supports(formatted, minsup, sequence_list):
    res = prefix_mining(formatted, minsup, sequence_list)
    f, i = len(res), 0
    for matches, patt in res:
        i += matches
    return i


def get_i_support_fast(sequence_list, formatted):
    """Calculate i_support by counting occurrences directly without re-mining"""
    count = 0
    for user_seq in formatted:
        if is_subsequence(sequence_list, user_seq):
            count += 1
    return count


def get_sequence_ids(target, data):
    return [row["key"] for _, row in data.iterrows() if is_subsequence(target, row["events"])]


def get_sequence_grade(ids, data):
    filtered_data = data[data["key"].isin(ids)]
    if filtered_data.empty:
        return 0, 0, 0, 0

    grades = filtered_data["grade"].sort_values()
    return grades.mean(), grades.std(ddof=0), grades.median(), grades.mode().iloc[0]


def get_time_span(ids, data):
    filtered_data = data[data["key"].isin(ids)]
    if filtered_data.empty:
        return [0, 0, 0, 0]

    start_times = filtered_data["events"].apply(lambda x: x[0]["time"])
    end_times = filtered_data["events"].apply(lambda x: x[-1]["time"])

    total_time = end_times.max() - start_times.min()
    avg_time = (end_times - start_times).mean()
    return [total_time, avg_time, start_times.min(), end_times.max()]


def get_sequences_length(data):
    lengths = []
    for index, row in data.iterrows():
        lengths.append(len(row["events"]))
    min_len = min(lengths)
    max_len = max(lengths)
    avg_len = statistics.mean(lengths)
    dev_len = statistics.stdev(lengths)
    return min_len, max_len, avg_len, dev_len


def generate_total_csv(processed_sceneries=None):
    # Read all existing CSV files from the directory
    csv_dir = f"outputs/results/{COURSE}/{activity}/csv"
    if not os.path.exists(csv_dir):
        return
    
    # If we have existing total.csv and only processing specific sceneries, update incrementally
    total_csv_path = f"outputs/results/{COURSE}/{activity}/total.csv"
    if processed_sceneries and os.path.exists(total_csv_path):
        # Load existing total.csv
        total = pd.read_csv(total_csv_path, sep=";")
        # Remove old data for processed sceneries
        processed_ids = [s.split("-")[0] for s in processed_sceneries]
        total = total[~total["scenery"].astype(str).isin(processed_ids)]
        
        # Add new data for processed sceneries
        new_datas = [pd.read_csv(f"{csv_dir}/{scenery}.csv", sep=";") for scenery in processed_sceneries]
        new_datas = [df.assign(scenery=scenery.split("-")[0]) for scenery, df in zip(processed_sceneries, new_datas)]
        new_total = pd.concat(new_datas, ignore_index=True)
        
        total = pd.concat([total, new_total], ignore_index=True)
    else:
        # Full regeneration (fallback)
        csv_files = [f.replace(".csv", "") for f in os.listdir(csv_dir) if f.endswith(".csv")]
        if not csv_files:
            return
        datas = [pd.read_csv(f"{csv_dir}/{scenery}.csv", sep=";") for scenery in csv_files]
        datas = [df.assign(scenery=scenery.split("-")[0]) for scenery, df in zip(csv_files, datas)]
        total = pd.concat(datas, ignore_index=True)
    
    cols = total.columns.tolist()
    cols.insert(0, cols.pop(cols.index("scenery")))
    total = total.reindex(columns=cols)
    total = total.round(2)
    total.to_csv(f"outputs/results/{COURSE}/{activity}/total.csv", sep=";", index=False)


def get_top_k(k=5, processed_sceneries=None):
    # Read all existing CSV files from the directory
    csv_dir = f"outputs/results/{COURSE}/{activity}/csv"
    if not os.path.exists(csv_dir):
        return
    
    # If we have existing top_k.csv and only processing specific sceneries, update incrementally
    top_k_csv_path = f"outputs/results/{COURSE}/{activity}/top_k.csv"
    if processed_sceneries and os.path.exists(top_k_csv_path):
        # Load existing top_k.csv
        total = pd.read_csv(top_k_csv_path, sep=";")
        # Remove old data for processed sceneries
        processed_ids = [s.split("-")[0] for s in processed_sceneries]
        total = total[~total["scenery"].astype(str).isin(processed_ids)]
        
        # Add new data for processed sceneries
        new_datas = [pd.read_csv(f"{csv_dir}/{scenery}.csv", sep=";") for scenery in processed_sceneries]
        new_datas = [df.assign(scenery=scenery.split("-")[0]) for scenery, df in zip(processed_sceneries, new_datas)]
        new_datas = [df[df["sequence_size"] > 1] for df in new_datas]
        new_datas = [df.nlargest(k, "total") for df in new_datas]
        new_total = pd.concat(new_datas, ignore_index=True)
        
        total = pd.concat([total, new_total], ignore_index=True)
    else:
        # Full regeneration (fallback)
        csv_files = [f.replace(".csv", "") for f in os.listdir(csv_dir) if f.endswith(".csv")]
        if not csv_files:
            return
        datas = [pd.read_csv(f"{csv_dir}/{scenery}.csv", sep=";") for scenery in csv_files]
        datas = [df.assign(scenery=scenery.split("-")[0]) for scenery, df in zip(csv_files, datas)]
        datas = [df[df["sequence_size"] > 1] for df in datas]
        datas = [df.nlargest(k, "total") for df in datas]
        total = pd.concat(datas, ignore_index=True)
    
    cols = total.columns.tolist()
    cols.insert(0, cols.pop(cols.index("scenery")))
    total = total.reindex(columns=cols)
    total = total.sort_values(by=["scenery", "total"], ascending=False)
    total.to_csv(f"outputs/results/{COURSE}/{activity}/top_k.csv", sep=";", index=False)


def get_supports_by_scenery(processed_sceneries=None):
    # Read only processed sceneries or all if not specified
    csv_dir = f"outputs/results/{COURSE}/{activity}/csv"
    if not os.path.exists(csv_dir):
        return
    
    # Use only processed sceneries if specified, otherwise read all
    if processed_sceneries:
        csv_files = processed_sceneries
    else:
        csv_files = [f.replace(".csv", "") for f in os.listdir(csv_dir) if f.endswith(".csv")]
    
    if not csv_files:
        return
    
    datas = [pd.read_csv(f"{csv_dir}/{scenery}.csv", sep=";") for scenery in csv_files]
    datas = [df.assign(scenery=scenery.split("-")[0]) for scenery, df in zip(csv_files, datas)]
    info = {
        "scenery": [],
        "i_support": [],
        "s_support": [],
    }
    for scenery, data in zip(csv_files, datas):
        try:
            i_support = f"{statistics.mean(data['i_support']):.2f} (+- {statistics.stdev(data['i_support']):.2f})"
        except Exception:
            i_support = f"{statistics.mean(data['i_support']):.2f} (+- 0)"

        try:
            s_support = f"{statistics.mean(data['ids']):.2f} (+- {statistics.stdev(data['ids']):.2f})"
        except Exception:
            s_support = f"{statistics.mean(data['ids']):.2f} (+- 0)"

        info["scenery"].append(eval(scenery.split("-")[0]))
        info["i_support"].append(i_support)
        info["s_support"].append(s_support)

    supports_df = pd.DataFrame(info)
    general_info = pd.read_csv(f"outputs/results/{COURSE}/{activity}/general_info.csv", sep=";")
    general_info = general_info.round(2)
    
    # Remove old data for sceneries that are being reprocessed
    sceneries_to_update = supports_df["scenery"].unique()
    general_info = general_info[~general_info["scenery"].isin(sceneries_to_update)]
    
    # Merge with new data
    general_info = pd.merge(general_info, supports_df, on="scenery", how="outer", suffixes=("", "_new"))
    
    # Clean up duplicate columns if they exist
    if "i_support_new" in general_info.columns:
        general_info = general_info.drop(columns=["i_support", "s_support"])
        general_info = general_info.rename(columns={"i_support_new": "i_support", "s_support_new": "s_support"})

    general_info = general_info.sort_values(by="scenery", ascending=True).reset_index(drop=True)
    general_info.to_csv(f"outputs/results/{COURSE}/{activity}/general_info.csv", sep=";", index=False)


def alter_support_to_percentage(total_reference: float = 2085.0):
    # Calcula porcentagens de s_support (média e desvio) considerando 100% = total_reference
    gen_info = pd.read_csv(f"outputs/results/{COURSE}/{activity}/general_info.csv", sep=";")

    def parse_mean_std(text: str):
        try:
            mean_part, rest = text.split(" (+- ")
            std_part = rest.rstrip(")")
            return float(mean_part), float(std_part)
        except Exception:
            return np.nan, np.nan

    parsed = gen_info["s_support"].apply(parse_mean_std)
    gen_info["s_support_percentage"] = parsed.apply(
        lambda t: round((t[0] / total_reference) * 100, 4) if pd.notna(t[0]) else np.nan
    )
    gen_info["s_support_std_percentage"] = parsed.apply(
        lambda t: round((t[1] / total_reference) * 100, 4) if pd.notna(t[1]) else np.nan
    )

    gen_info.to_csv(f"outputs/results/{COURSE}/{activity}/general_info.csv", sep=";", index=False)


def load_data(file_path):
    global use_split
    if use_split:
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                data = json.load(f)
        else:
            print(f"Warning: {file_path} not found")

        return generate_data(data)  # Cria e retorna o dataframe combinado
    else:
        with open(file_path, "r") as f:
            data = json.load(f)
        return generate_data(data)


# noinspection PyTypedDict
def main():
    global use_split, sceneries_names
    sceneries = {}
    g = {
        "scenery": [],
        "minsup": [],
        "max_grade": [],
        "total_sequences": [],
        "time_span_in_days": [],
        "longest_pattern_length": [],
        "shortest_pattern_length": [],
        "" "average_pattern_length": [],
        "longest_sequence_length": [],
        "shortest_sequence_length": [],
        "average_sequence_length": [],
        "elapsed_time": [],
        "i_support": [],
        "s_support": [],
    }
    if not os.path.exists(f"outputs/results/{COURSE}/{activity}"):
        os.makedirs(f"outputs/results/{COURSE}/{activity}")
    if os.path.exists(f"outputs/results/{COURSE}/{activity}/general_info.csv"):
        general_info = pd.read_csv(f"outputs/results/{COURSE}/{activity}/general_info.csv", sep=";")
    else:
        general_info = pd.DataFrame(g)
    general_info["scenery"] = general_info["scenery"].astype(str)
    general_info["average_pattern_length"] = general_info["average_pattern_length"].astype(str)
    general_info["average_sequence_length"] = general_info["average_sequence_length"].astype(str)
    general_info = general_info.round(2)
    general_info.to_csv(f"outputs/results/{COURSE}/{activity}/general_info.csv", sep=";", index=False)

    if use_split:
        sceneries_names = [f"{scenery}_{suffix}" for scenery in sceneries_names for suffix in ["high", "low"]]

    new_lines = []
    for index, scenery in enumerate(sceneries_names):
        begin = time.time()
        print(f"[{datetime.datetime.now().strftime("%H:%M:%S")}] Processing {scenery}", end=" | ")
        minsup = 0.08
        file_name = read_params(scenery)
        all_sequences = load_data(file_name)
        original_seq = all_sequences.copy()
        max_grade = int(all_sequences["max_grade"].iloc[0])
        get_sequences_length(original_seq)
        formatted = format_tf_data(all_sequences)
        all_sequences["events"] = all_sequences["events"].apply(extract_events)

        # mining_result_gsp = gsp_mining(formatted)
        mining_result_prefix = prefix_mining(formatted, minsup)

        total_sequences = 0
        for sequences in mining_result_prefix:
            total_sequences += len(sequences)

        result = []
        for i in range(len(mining_result_prefix)):
            result.append(remap_keys(mining_result_prefix[i], i + 1))

        # get I-support, F-support, most and least repeated sequences by sequence size
        final_result = {
            f"{i}_sequences": {"sequences": [], "most_repeated": {}, "least_repeated": {}}
            for i in range(1, len(result) + 1)
        }
        lengths = []
        times = []
        for freq in result:
            for key, sequences in freq.items():
                most_repeated = {"total": 0, "sequence": {}}
                least_repeated = {"total": 9999999, "sequence": {}}
                for seq in sequences:
                    sequence_list = seq["sequence"]
                    i_support = get_i_support_fast(sequence_list, formatted)
                    ids = get_sequence_ids(sequence_list, all_sequences)
                    avg, dev, median, mode = get_sequence_grade(ids, all_sequences)
                    total_time, avg_time, initial_time, final_time = get_time_span(ids, original_seq)
                    sequence = {
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
                    }
                    final_result[key]["sequences"].append(sequence)
                    if sequence["total"] > most_repeated["total"]:
                        most_repeated = sequence
                    if least_repeated["total"] > sequence["total"] > 1:
                        least_repeated = sequence
                    lengths.append(sequence["sequence_size"])
                    times.append(initial_time)
                    times.append(final_time)
                final_result[key]["most_repeated"] = most_repeated
                final_result[key]["least_repeated"] = least_repeated

        lengths.sort()
        times.sort()
        min_len, max_len, avg_len, dev_len = get_sequences_length(original_seq)

        try:
            avg_pattern_length = f"{statistics.mean(lengths)} (+- {statistics.stdev(lengths)})"
        except Exception:
            avg_pattern_length = f"{statistics.mean(lengths)} (+- 0)"

        new_lines.append(
            {
                "scenery": scenery.split("-")[0],
                "minsup": minsup,
                "max_grade": max_grade,
                "total_sequences": total_sequences,
                "time_span_in_days": (
                    datetime.datetime.fromtimestamp(times[-1]) - datetime.datetime.fromtimestamp(times[0])
                ).days,
                "longest_pattern_length": lengths[-1],
                "shortest_pattern_length": lengths[0],
                "average_pattern_length": avg_pattern_length,
                "longest_sequence_length": max_len,
                "shortest_sequence_length": min_len,
                "average_sequence_length": f"{avg_len:.2f} (+- {dev_len:.2f})",
                "elapsed_time": time.time() - begin,
                "i_support": "",
                "s_support": "",
            }
        )

        sceneries[scenery] = final_result
        write_result(final_result, scenery, f"outputs/results/{COURSE}/{activity}", True)
        # break
        end = time.time()
        print(f"Elapsed time: {(end - begin):.2f}")
        # general_info.loc[index, "elapsed_time"] = end - begin

    new_lines_df = pd.DataFrame(new_lines)

    # Remove old data for sceneries that are being reprocessed
    sceneries_being_processed = new_lines_df["scenery"].unique()
    general_info = general_info[~general_info["scenery"].isin(sceneries_being_processed)]
    
    # Add new data
    general_info = pd.concat([general_info, new_lines_df], ignore_index=True)

    general_info = general_info.sort_values(by="scenery", ascending=True).reset_index(drop=True)
    general_info = general_info.round(2)
    # print(general_info["scenery"].drop_duplicates())
    general_info.to_csv(f"./outputs/results/{COURSE}/{activity}/general_info.csv", sep=";", index=False)
    
    # Pass the list of processed sceneries to optimization functions
    processed_list = list(new_lines_df["scenery"].apply(lambda x: f"{x}-" + [s for s in sceneries_names if s.startswith(str(x))][0].split("-")[1] if any(s.startswith(str(x)) for s in sceneries_names) else "unknown"))
    get_supports_by_scenery(sceneries_names)  # Pass only processed sceneries
    generate_total_csv(sceneries_names)
    get_top_k(processed_sceneries=sceneries_names)
    alter_support_to_percentage(2085.0)
    # alter_support_to_percentage()


if __name__ == "__main__":
    main()
    # [write_csv(data) for data in sceneries_names]
    # generate_gen_info()
    # get_supports_by_scenery()
    # generate_total_csv()
    # get_top_k()
    # alter_support_to_percentage()
