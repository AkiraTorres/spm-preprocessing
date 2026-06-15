import pandas as pd

# Carregar o arquivo CSV
df = pd.read_csv("./outputs/results/4/top_k.csv", sep=";")

# Definir o valor máximo como base para 100%
valor_maximo = 11974


# Função para extrair média e desvio padrão, calcular a porcentagem e retornar ambos
def calcular_percentual(support):
    if type(support) is not str:
        return f"{(support / valor_maximo * 100):.2f}%"

    # Extrair média e desvio padrão a partir da string
    media_str, desvio_str = support.split(" (+- ")
    media = float(media_str)
    desvio = float(desvio_str.replace(")", ""))

    # Calcular porcentagens
    media_percent = (media / valor_maximo) * 100
    desvio_percent = (desvio / valor_maximo) * 100

    return f"{media_percent:.2f}% (+- {desvio_percent:.2f}%)"


# Aplicar a função para calcular a porcentagem na coluna 's_support'
df["s_support_percent"] = df["s_support"].apply(calcular_percentual)

# Exibir o resultado
# print(df[["s_support", "s_support_percent"]])
df.to_csv("./outputs/results/4/top_k_percentages.csv", sep=";", index=False)
