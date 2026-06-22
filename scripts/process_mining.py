import os.path
import json
import argparse
from gsppy.gsp import GSP
from prefixspan import PrefixSpan
import pandas as pd
import time
import datetime
import sys

# Matriz de cenarios (fonte unica). Os parametros de execucao vem por flags;
# os globals abaixo sao preenchidos em main() a partir dos argumentos parseados.
sys.path.insert(0, "src")
from spm.sceneries import SCENERIES_NAMES as sceneries_names

COURSE = None
activity = None
use_split = False
minsup = 0.08
sceneries_root = "outputs/sceneries"
mining_root = "outputs/mining_results"




def generate_data(data):
    """Gera DataFrame a partir dos dados JSON."""
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
    df = pd.DataFrame(rows)
    return df


def gsp_mining(sequences_list: list, minsup: float = 0.08) -> list:
    """Executa mineração usando algoritmo GSP."""
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


def format_tf_data(s) -> list:
    """Formata dados para mineração."""
    data = []
    s = pd.DataFrame(data=s).to_dict(orient="records")
    for user_sequence in s:
        events = [event["event"] for event in user_sequence["events"]]
        data.append(events)
    return data


def read_params(file: str) -> str:
    """Constrói caminho do arquivo de entrada."""
    base = f"{sceneries_root}/{COURSE}/{activity}"
    return f"{base}/split_grade/{file}.json" if use_split else f"{base}/{file}.json"


def load_data(file_path):
    """Carrega dados do arquivo JSON."""
    global use_split
    if use_split:
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                data = json.load(f)
        else:
            print(f"Warning: {file_path} not found")
            return None
    else:
        with open(file_path, "r") as f:
            data = json.load(f)
    return generate_data(data)


def remap_keys(user_sequences, seq_quantities):
    """Reformata as chaves dos resultados de mineração."""
    def process_key(key):
        modified_key = key.replace("[", "").replace("]", "").replace("'", "")
        return [part.strip() for part in modified_key.split(",")]

    return {
        f"{seq_quantities}_sequences": [{"sequence": process_key(k), "total": v} for k, v in user_sequences.items()]
    }


def save_mining_results(mining_result, scenery, output_path):
    """Salva resultados brutos da mineração."""
    result = []
    for i in range(len(mining_result)):
        result.append(remap_keys(mining_result[i], i + 1))
    
    # Criar estrutura simplificada apenas com resultados da mineração
    mining_output = {
        f"{i}_sequences": {"sequences": []}
        for i in range(1, len(result) + 1)
    }
    
    for freq in result:
        for key, sequences in freq.items():
            for seq in sequences:
                sequence_data = {
                    "sequence": seq["sequence"],
                    "total": seq["total"],
                }
                mining_output[key]["sequences"].append(sequence_data)
    
    # Criar diretório se não existir
    if not os.path.exists(output_path):
        os.makedirs(output_path)
    
    # Salvar resultado
    output_file = os.path.join(output_path, f"{scenery}_mining.json")
    with open(output_file, "w+") as f:
        json.dump(mining_output, f, indent=2)
    
    return mining_output


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Minera padroes sequenciais (PrefixSpan) por cenario.")
    parser.add_argument("-co", "--course", type=int, required=True, help="Numero do curso (ex.: 2060, 2065)")
    parser.add_argument("-act", "--activity", type=int, required=True, help="Numero da atividade (inteiro)")
    parser.add_argument("-ms", "--minsup", type=float, default=0.08, help="Suporte minimo do PrefixSpan (default: 0.08)")
    parser.add_argument("--use-split", action="store_true", help="Usa variantes _high/_low por nota")
    parser.add_argument("--sceneries-dir", type=str, default="outputs/sceneries", help="Raiz dos cenarios de entrada")
    parser.add_argument("--out-dir", type=str, default="outputs/mining_results", help="Raiz de saida da mineracao")
    return parser.parse_args(argv)


def main(args):
    """Executa a mineração de processos para todos os cenários."""
    global COURSE, activity, use_split, minsup, sceneries_names, sceneries_root, mining_root
    COURSE = args.course
    activity = args.activity
    use_split = args.use_split
    minsup = args.minsup
    sceneries_root = args.sceneries_dir
    mining_root = args.out_dir

    if use_split:
        sceneries_names = [f"{scenery}_{suffix}" for scenery in sceneries_names for suffix in ["high", "low"]]

    output_path = f"{mining_root}/{COURSE}/{activity}"
    
    print(f"Iniciando mineração de processos...")
    print(f"Curso: {COURSE}, Atividade: {activity}")
    print(f"Total de cenários: {len(sceneries_names)}")
    print(f"Resultados serão salvos em: {output_path}\n")
    
    for index, scenery in enumerate(sceneries_names, 1):
        begin = time.time()
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] [{index}/{len(sceneries_names)}] Processando {scenery}...", end=" | ")

        file_name = read_params(scenery)
        
        # Carregar dados
        all_sequences = load_data(file_name)
        if all_sequences is None:
            print("ERRO: Arquivo não encontrado")
            continue
        
        # Formatar dados
        formatted = format_tf_data(all_sequences)
        
        # Executar mineração
        mining_result = prefix_mining(formatted, minsup)
        
        # Salvar resultados
        save_mining_results(mining_result, scenery, output_path)
        
        end = time.time()
        elapsed = end - begin
        print(f"Concluído em {elapsed:.2f}s")
    
    print(f"\nMineração concluída! Resultados salvos em: {output_path}")


if __name__ == "__main__":
    main(parse_args())
