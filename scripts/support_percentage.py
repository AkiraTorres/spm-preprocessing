import argparse
import os
import sys
import pandas as pd
import numpy as np


def parse_mean_std(text: str):
    """Parseia strings no formato "<mean> (+- <std>)" e retorna (mean, std).

    Retorna (nan, nan) se não conseguir parsear.
    """
    try:
        if pd.isna(text):
            return np.nan, np.nan
        text = str(text)
        mean_part, rest = text.split(" (+- ")
        std_part = rest.rstrip(")")
        return float(mean_part), float(std_part)
    except Exception:
        return np.nan, np.nan


def main():
    parser = argparse.ArgumentParser(description="Calcula porcentagens para s_support considerando um total de referência.")
    parser.add_argument(
        "--input",
        required=True,
        help="Caminho para o arquivo general_info.csv de entrada",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Caminho para o arquivo de saída (se omitido, sobrescreve o arquivo de entrada)",
    )
    parser.add_argument(
        "--total",
        type=float,
        default=2085.0,
        help="Valor que representa 100% (default: 2085)",
    )
    args = parser.parse_args()

    input_path = args.input
    output_path = args.output or input_path

    if not os.path.exists(input_path):
        print(f"Arquivo não encontrado: {input_path}")
        sys.exit(1)

    df = pd.read_csv(input_path, sep=";")

    if "s_support" not in df.columns:
        print("Coluna 's_support' não encontrada no CSV.")
        sys.exit(1)

    parsed = df["s_support"].apply(parse_mean_std)
    df["s_support_percentage"] = parsed.apply(
        lambda t: round((t[0] / args.total) * 100, 4) if pd.notna(t[0]) else np.nan
    )
    df["s_support_std_percentage"] = parsed.apply(
        lambda t: round((t[1] / args.total) * 100, 4) if pd.notna(t[1]) else np.nan
    )

    df.to_csv(output_path, sep=";", index=False)
    print(f"Arquivo atualizado: {output_path}")


if __name__ == "__main__":
    main()


