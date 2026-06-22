import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import os

# Reproduz dados aproximados a partir das estatísticas (média, desvio, min, max, n).
def gerar_dados(n, mean, std, min_val, max_val):
    np.random.seed(42)
    data = np.random.normal(loc=mean, scale=std, size=n)
    data = np.clip(data, min_val, max_val)
    return data

sns.set_theme(style="whitegrid")
os.makedirs("outputs/figures", exist_ok=True)

print("Gerando e salvando o gráfico (a)...")

# Criamos uma lista para armazenar os DataFrames de cada assignment separadamente.
df_jobs_list = []

# Coletamos os dados (usando os valores reais das tabelas originais)
df_jobs_list.append(pd.DataFrame({'Sequence Length': gerar_dados(2085, 11.34, 12.02, 3, 127), 'Assignment': 'Assignment 1'}))
df_jobs_list.append(pd.DataFrame({'Sequence Length': gerar_dados(2188, 15.10, 13.73, 1, 134), 'Assignment': 'Assignment 2'}))
df_jobs_list.append(pd.DataFrame({'Sequence Length': gerar_dados(2100, 15.00, 13.43, 1, 171), 'Assignment': 'Assignment 3'}))
df_jobs_list.append(pd.DataFrame({'Sequence Length': gerar_dados(2025, 16.24, 13.55, 1, 242), 'Assignment': 'Assignment 4'}))

# Concatenamos em um único DataFrame
df_jobs = pd.concat(df_jobs_list)

# Criamos a figura para o primeiro gráfico
plt.figure(figsize=(8, 6))

# Geramos o boxplot
sns.boxplot(
    data=df_jobs,
    x='Sequence Length',
    y='Assignment',
    color='#4c72b0',  # Um azul sóbrio
    fliersize=4,      # Tamanho dos pontos dos outliers
    width=0.3
)

# Configuramos títulos e labels
# plt.title('Jobs and Salaries Course - Sequence Length Distribution')
plt.xlabel('Sequence Length')
plt.ylabel('')  # Remove o label do eixo Y para limpar o visual

# SALVAMOS A IMAGEM (a)
# O arquivo será salvo como 'outputs/figures/boxplot_jobs.png' na mesma pasta do script.
plt.savefig('outputs/figures/boxplot_jobs.png', dpi=300, bbox_inches='tight')

# FECHAMOS A FIGURA ATUAL (Crucial para não sobrepor os gráficos)
plt.close()


print("Gerando e salvando o gráfico (b)...")

# Processo idêntico para o curso de Database
df_db_list = []

# Coletamos os dados
df_db_list.append(pd.DataFrame({'Sequence Length': gerar_dados(1776, 11.02, 13.84, 3, 399), 'Assignment': 'Assignment 1'}))
df_db_list.append(pd.DataFrame({'Sequence Length': gerar_dados(1864, 13.11, 11.00, 2, 143), 'Assignment': 'Assignment 2'}))
df_db_list.append(pd.DataFrame({'Sequence Length': gerar_dados(1732, 16.71, 14.13, 1, 160), 'Assignment': 'Assignment 3'}))

# Concatenamos
df_db = pd.concat(df_db_list)

# Criamos uma NOVA figura
plt.figure(figsize=(8, 6))

# Geramos o boxplot
sns.boxplot(
    data=df_db,
    x='Sequence Length',
    y='Assignment',
    color='#dd8452',  # Um laranja/creme sóbrio
    fliersize=4,
    width=0.3
)

# Configuramos títulos e labels
# plt.title('Database Course - Sequence Length Distribution')
plt.xlabel('Sequence Length')
plt.ylabel('')

# SALVAMOS A IMAGEM (b)
# O arquivo será salvo como 'outputs/figures/boxplot_db.png'.
plt.savefig('outputs/figures/boxplot_db.png', dpi=300, bbox_inches='tight')

# FECHAMOS A FIGURA
plt.close()

print(f"\nPronto! As imagens foram salvas na pasta: {os.getcwd()}")
print("Arquivos gerados: 'outputs/figures/boxplot_jobs.png' e 'outputs/figures/boxplot_db.png'")