import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
import os
import sys

sys.path.insert(0, "src")
from spm.config import SCENERIES_NAMES as sceneries_names, COURSE, ACTIVITY

# Configurar matplotlib para português
plt.rcParams['font.size'] = 10

# Definir a atividade


# Mapear nomes de cenários para números (como estão no CSV)
sceneries_numbers = [int(name.split('-')[0]) for name in sceneries_names]

# Ler o arquivo CSV
print("Lendo o arquivo total.csv...")
df = pd.read_csv(f'outputs/results/{COURSE}/{ACTIVITY}/total.csv', sep=';')

# Filtrar apenas os cenários especificados em sceneries_names
df = df[df['scenery'].isin(sceneries_numbers)]

# Identificar cenários após filtro
sceneries = sorted(df['scenery'].unique())
print(f"Cenários especificados em sceneries_names: {sceneries_names}")
print(f"Cenários numéricos: {sceneries_numbers}")
print(f"Cenários sendo analisados: {sceneries}")
print(f"Total de registros após filtro: {len(df)}")

# Variáveis para análise
variables = ['sequence_size', 'avg_time_span', 'i_support', 's_support', 'grade_avg', 'jaccard_distance']

# Garantir a existência das pastas para salvar as imagens
output_path = f"outputs/figures/boxplots/{COURSE}/{ACTIVITY}/"
os.makedirs(output_path, exist_ok=True)

# Configurar a figura com subplots
fig, axes = plt.subplots(2, 3, figsize=(18, 12))
# if len(sceneries_names) > 1:
#     fig.suptitle(f'Boxplots das Variáveis - Comparação entre Cenários (Atividade {ACTIVITY} Diciplina {COURSE})', fontsize=16, fontweight='bold')
# else:
#     fig.suptitle(f'Boxplots das Variáveis - Cenário {sceneries_names[0]} (Atividade {ACTIVITY} Diciplina {COURSE})', fontsize=16, fontweight='bold')

# Criar boxplots para cada variável
if len(sceneries) == 0:
    print("\nErro: Nenhum cenário encontrado após filtro. Verifique se os cenários especificados existem no CSV.")
    exit(1)

for i, var in enumerate(variables):
    row = i // 3
    col = i % 3
    ax = axes[row, col]

    # Preparar dados por cenário
    data_by_scenery = [df[df['scenery'] == s][var].dropna().values for s in sceneries]

    # Criar o boxplot comparando todos os cenários
    box_plot = ax.boxplot(data_by_scenery, patch_artist=True, tick_labels=[str(s) for s in sceneries])

    # Personalizar cores
    for b in box_plot['boxes']:
        b.set_facecolor('lightblue')
    for m in box_plot['medians']:
        m.set_color('red')
        m.set_linewidth(2)

    # Configurar título e labels
    title = var.replace('_', ' ').title()
    title = title.replace('Avg Time Span', 'Mean Time Span')
    title = title.replace('I Support', 'I-Support')
    title = title.replace('S Support', 'Support')
    title = title.replace('Grade Avg', 'Mean Grades')
    title = title.replace('Sequence Size', 'Pattern Size')
    ax.set_title(title, fontweight='bold')
    ax.set_xlabel('Scenario')
    ax.set_ylabel('Value')
    if var == 'jaccard_distance':
        ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f'{x:.0f}%'))
    ax.grid(True, alpha=0.3)

plt.tight_layout()
name = f"boxplots_{ACTIVITY}.png" if len(sceneries_names) > 1 else f"boxplot_scenary_{sceneries_names[0]}.png"
plt.savefig(f'{output_path}/{name}', dpi=300, bbox_inches='tight')
print(f"Gráfico salvo como: {name}")

# Imprimir estatísticas resumidas gerais da atividade
print(f"\nEstatísticas resumidas gerais - Atividade {ACTIVITY} Diciplina {COURSE}:")
print("=" * 60)
for var in variables:
    print(f"\n{var.replace('_', ' ').title()}:")
    stats = df[var].describe()
    print(f"  Média: {stats['mean']:.2f}")
    print(f"  Mediana: {stats['50%']:.2f}")
    print(f"  Desvio Padrão: {stats['std']:.2f}")
    print(f"  Mínimo: {stats['min']:.2f}")
    print(f"  Máximo: {stats['max']:.2f}")
    print(f"  Q1: {stats['25%']:.2f}")
    print(f"  Q3: {stats['75%']:.2f}")

# Criar boxplots individuais para cada variável
for var in variables:
    plt.figure(figsize=(10, 6))
    data_by_scenery = [df[df['scenery'] == s][var].dropna().values for s in sceneries]
    box_plot = plt.boxplot(data_by_scenery, patch_artist=True, tick_labels=[str(s) for s in sceneries])

    # Personalizar cores
    for b in box_plot['boxes']:
        b.set_facecolor('lightblue')
    for m in box_plot['medians']:
        m.set_color('red')
        m.set_linewidth(2)

    title = var.replace('_', ' ').title()
    # plt.title(f'Assignment {ACTIVITY} - Course {COURSE}', fontweight='bold')
    plt.xlabel('Scenario')
    plt.ylabel('Value')
    if var == 'jaccard_distance':
        plt.gca().yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f'{x:.0f}%'))
    plt.grid(True, alpha=0.3)

    # Adicionar estatísticas gerais
    stats = df[var].describe()
    textstr = f'Mediana: {stats["50%"]:.2f}\nMédia: {stats["mean"]:.2f}\nStd: {stats["std"]:.2f}'
    # plt.text(0.02, 0.98, textstr, transform=plt.gca().transAxes, fontsize=10, verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))

    plt.tight_layout()
    plt.savefig(f'{output_path}/boxplot_{var}_comparison_activity_{ACTIVITY}.png', dpi=300, bbox_inches='tight')
    print(f"Boxplot individual salvo: boxplot_{var}_comparison_activity_{ACTIVITY}.png")

print("\nTodos os gráficos foram gerados com sucesso!")
