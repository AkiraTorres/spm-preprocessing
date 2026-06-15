# Uso básico
# python3 scenario_metrics.py ./outputs/sceneries/2060/1/

# Salvar resultados em CSV
# python3 scenario_metrics.py ./outputs/sceneries/2060/1/ --output-csv metricas.csv

# Salvar resultados em JSON
# python3 scenario_metrics.py ./outputs/sceneries/2060/1/ --output-json metricas.json

# Ambos formatos
# python3 scenario_metrics.py ./outputs/sceneries/2060/1/ --output-csv metricas.csv --output-json metricas.json

import json
import os
import statistics
from pathlib import Path
from typing import Dict, List, Any


def load_scenario(file_path: str) -> List[Dict[str, Any]]:
    """Carrega um arquivo de cenário JSON."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_sequence_lengths(scenario_data: List[Dict[str, Any]]) -> List[int]:
    """
    Extrai os tamanhos das sequências de um cenário.
    
    Cada entrada no cenário tem uma lista 'events' que contém sublistas de eventos.
    O tamanho da sequência é o número de eventos em cada sublista.
    """
    lengths = []
    for entry in scenario_data:
        if 'events' in entry:
            for sequence in entry['events']:
                lengths.append(len(sequence))
    return lengths


def calculate_metrics(sequence_lengths: List[int]) -> Dict[str, Any]:
    """
    Calcula as métricas para uma lista de tamanhos de sequências.
    
    Returns:
        Dict com as métricas calculadas
    """
    if not sequence_lengths:
        return {
            'num_sequences': 0,
            'min_length': None,
            'max_length': None,
            'mean_length': None,
            'std_length': None
        }
    
    num_sequences = len(sequence_lengths)
    min_length = min(sequence_lengths)
    max_length = max(sequence_lengths)
    mean_length = statistics.mean(sequence_lengths)
    
    # Desvio padrão (populacional se apenas 1 sequência, amostral caso contrário)
    if num_sequences > 1:
        std_length = statistics.stdev(sequence_lengths)
    else:
        std_length = 0.0
    
    return {
        'num_sequences': num_sequences,
        'min_length': min_length,
        'max_length': max_length,
        'mean_length': round(mean_length, 4),
        'std_length': round(std_length, 4)
    }


def process_directory(directory_path: str, file_extension: str = '.json', activity_only: bool = False) -> Dict[str, Dict[str, Any]]:
    """
    Processa todos os arquivos de cenário em um diretório.
    
    Args:
        directory_path: Caminho do diretório contendo os cenários
        file_extension: Extensão dos arquivos a processar (padrão: .json)
        activity_only: Se True, processa apenas o arquivo 0-zero.json
    
    Returns:
        Dict mapeando nome do arquivo para suas métricas
    """
    results = {}
    directory = Path(directory_path)
    
    if not directory.exists():
        raise FileNotFoundError(f"Diretório não encontrado: {directory_path}")
    
    if activity_only:
        # Processa apenas o arquivo 0-zero.json
        zero_file = directory / '0-zero.json'
        if zero_file.exists():
            try:
                scenario_data = load_scenario(str(zero_file))
                sequence_lengths = get_sequence_lengths(scenario_data)
                metrics = calculate_metrics(sequence_lengths)
                results['0-zero.json'] = metrics
                print(f"Processado: 0-zero.json")
            except Exception as e:
                print(f"Erro ao processar 0-zero.json: {e}")
                results['0-zero.json'] = {'error': str(e)}
        else:
            print(f"Arquivo 0-zero.json não encontrado em {directory_path}")
        return results
    
    # Lista arquivos com a extensão especificada e ordena numericamente
    scenario_files = sorted(
        directory.glob(f'*{file_extension}'),
        key=lambda x: int(x.name.split('-')[0]) if x.name.split('-')[0].isdigit() else float('inf')
    )
    
    if not scenario_files:
        print(f"Nenhum arquivo {file_extension} encontrado em {directory_path}")
        return results
    
    for file_path in scenario_files:
        try:
            scenario_data = load_scenario(str(file_path))
            sequence_lengths = get_sequence_lengths(scenario_data)
            metrics = calculate_metrics(sequence_lengths)
            results[file_path.name] = metrics
            print(f"Processado: {file_path.name}")
        except Exception as e:
            print(f"Erro ao processar {file_path.name}: {e}")
            results[file_path.name] = {'error': str(e)}
    
    return results


def print_metrics_report(results: Dict[str, Dict[str, Any]], activity_only: bool = False) -> None:
    """Imprime um relatório formatado das métricas."""
    if activity_only:
        print("\n" + "=" * 80)
        print("RELATÓRIO DE MÉTRICAS DA ATIVIDADE")
        print("=" * 80)
        
        # Busca apenas o arquivo 0-zero.json
        metrics = results.get('0-zero.json')
        if metrics is None:
            print("\n❌ Arquivo 0-zero.json não encontrado no diretório.")
        elif 'error' in metrics:
            print(f"\n❌ Erro: {metrics['error']}")
        else:
            print(f"\n📊 Métricas da Atividade")
            print("-" * 40)
            print(f"  • Número de sequências:         {metrics['num_sequences']}")
            print(f"  • Tamanho da menor sequência:   {metrics['min_length']}")
            print(f"  • Tamanho da maior sequência:   {metrics['max_length']}")
            print(f"  • Média de tamanho:             {metrics['mean_length']}")
            print(f"  • Desvio padrão:                {metrics['std_length']}")
    else:
        print("\n" + "=" * 80)
        print("RELATÓRIO DE MÉTRICAS DOS CENÁRIOS")
        print("=" * 80)
        
        for filename, metrics in results.items():
            print(f"\n📁 Arquivo: {filename}")
            print("-" * 40)
            
            if 'error' in metrics:
                print(f"  ❌ Erro: {metrics['error']}")
            else:
                print(f"  • Número de sequências:         {metrics['num_sequences']}")
                print(f"  • Tamanho da menor sequência:   {metrics['min_length']}")
                print(f"  • Tamanho da maior sequência:   {metrics['max_length']}")
                print(f"  • Média de tamanho:             {metrics['mean_length']}")
                print(f"  • Desvio padrão:                {metrics['std_length']}")
    
    print("\n" + "=" * 80)


def save_metrics_to_csv(results: Dict[str, Dict[str, Any]], output_path: str) -> None:
    """Salva as métricas em um arquivo CSV."""
    import csv
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'arquivo',
            'num_sequences',
            'min_length',
            'max_length',
            'mean_length',
            'std_length'
        ])
        
        for filename, metrics in results.items():
            if 'error' not in metrics:
                writer.writerow([
                    filename,
                    metrics['num_sequences'],
                    metrics['min_length'],
                    metrics['max_length'],
                    metrics['mean_length'],
                    metrics['std_length']
                ])
    
    print(f"\n💾 Métricas salvas em: {output_path}")


def save_metrics_to_json(results: Dict[str, Dict[str, Any]], output_path: str) -> None:
    """Salva as métricas em um arquivo JSON."""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"💾 Métricas salvas em: {output_path}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Calcula métricas de cenários de sequências de eventos.'
    )
    parser.add_argument(
        'directory',
        type=str,
        help='Diretório contendo os arquivos de cenário (ex: ./outputs/sceneries/2060/1/)'
    )
    parser.add_argument(
        '--output-csv',
        type=str,
        default=None,
        help='Caminho para salvar as métricas em CSV'
    )
    parser.add_argument(
        '--output-json',
        type=str,
        default=None,
        help='Caminho para salvar as métricas em JSON'
    )
    parser.add_argument(
        '--activity-only',
        action='store_true',
        help='Retorna apenas as métricas do arquivo 0-zero.json como dados da atividade'
    )
    
    args = parser.parse_args()
    
    # Processa o diretório
    if args.activity_only:
        print(f"\n🔍 Processando atividade em: {args.directory}\n")
    else:
        print(f"\n🔍 Processando cenários em: {args.directory}\n")
    results = process_directory(args.directory, activity_only=args.activity_only)
    
    # Imprime relatório
    print_metrics_report(results, activity_only=args.activity_only)
    
    # Salva resultados se especificado
    if args.activity_only:
        # Filtra apenas 0-zero.json para salvar
        activity_results = {'atividade': results.get('0-zero.json', {'error': 'Arquivo não encontrado'})}
        if args.output_csv:
            save_metrics_to_csv(activity_results, args.output_csv)
        if args.output_json:
            save_metrics_to_json(activity_results, args.output_json)
    else:
        if args.output_csv:
            save_metrics_to_csv(results, args.output_csv)
        if args.output_json:
            save_metrics_to_json(results, args.output_json)
    
    return results


if __name__ == '__main__':
    main()
