"""Etapa 1: ingestão dos quatro .csv.gz de raw/ no schema raw do DuckDB.

Execução:
    uv run python -m pipeline.ingestao

1. ESCOPO E NOMES
   Schema de destino: raw. Mapa arquivo -> tabela, completo e literal:
     campeonato-brasileiro-full.csv.gz               -> partidas
     campeonato-brasileiro-estatisticas-full.csv.gz  -> estatisticas
     campeonato-brasileiro-gols.csv.gz               -> gols
     campeonato-brasileiro-cartoes.csv.gz            -> cartoes
   Por quê: nomes curtos em português são o vocabulário digitado de memória
   nos JOINs das próximas etapas. raw/Legenda.txt não é ingerido, porque é
   documentação, não dado; só os quatro arquivos do mapa são lidos, pelo
   nome, e qualquer outro arquivo da pasta é ignorado.

2. PROIBIÇÕES (a regra central desta etapa)
   Nenhuma conversão de tipo, nenhuma linha descartada ou deduplicada, nenhum
   nome de coluna alterado (rodata, mandante_Placar, partida_id ficam como no
   cabeçalho, mesmo divergindo do Legenda.txt), nenhum valor corrigido,
   preenchido, aparado ou normalizado (o \\xa0 no início de arena, o "-" de
   empate em vencedor, o "90+9" em minuto, o "55%" em posse_de_bola). Data
   continua texto, nulo continua nulo.
   Por quê: a fronteira entre "o dado que chegou" e "o dado que eu decidi"
   precisa existir em algum lugar, e esse lugar é a passagem de raw para
   refined, na etapa 2. Corrigir aqui apaga a fronteira.

3. REEXECUÇÃO
   Rodar dez vezes dá o mesmo resultado que rodar uma: cada tabela é recriada
   (CREATE OR REPLACE), nunca acrescentada.
   Por quê: é o que permite errar e rodar de novo sem medo.

4. LEITURA DO ARQUIVO
   encoding declarado como utf-8, nunca adivinhado. Os .csv.gz são lidos
   direto, sem descompactar. Só o campo vazio vira nulo
   (keep_default_na=False, na_values=[""]).
   Por quê: por padrão o pandas transforma em nulo textos como "None", "NA"
   e "null". Em estatisticas, 1.550 linhas de posse_de_bola e 3.854 de
   precisao_passes trazem o texto "None", que é diferente do campo vazio; com
   o padrão do pandas esse texto viraria nulo calado e a etapa 2 nunca mais
   separaria os dois casos.

5. TIPAGEM
   Toda coluna entra como texto (dtype=str), inferência desligada.
   Por quê: a inferência decide sozinha o que não é dela. Leria data
   dd/mm/aaaa sem formato declarado, arrecadacao (inteiros e decimais
   misturados) como ponto flutuante, e minuto com "90+9" ora como número,
   ora como texto. A conversão é da etapa 2, onde vira decisão registrada.

6. SAÍDA NA TELA
   Uma linha por tabela, com nome qualificado e contagem vinda do banco (não
   do DataFrame), milhar separado por ponto, e uma linha final com o total.
   stdout reconfigurado para utf-8.
   Por quê: essa saída é o único instrumento de conferência desta etapa, e no
   Prompt de Comando do Windows acento sai embaralhado por padrão.

7. ERRO
   Antes de abrir o banco, verifica se os quatro arquivos existem. Faltando
   qualquer um, lista os que faltam, diz em que pasta procurou e encerra com
   sys.exit(1), sem ingerir nada.
   Por quê: ingerir três de quatro tabelas em silêncio produz um painel
   errado que parece certo.

Este módulo não importa ui.py: a ingestão não sobe servidor, não abre
navegador e não depende da extensão ui do DuckDB.
"""

import sys

import pandas as pd

from pipeline.db import PASTA_RAW, conectar, criar_schema, gravar

SCHEMA = "raw"

ARQUIVOS = {
    "campeonato-brasileiro-full.csv.gz": "partidas",
    "campeonato-brasileiro-estatisticas-full.csv.gz": "estatisticas",
    "campeonato-brasileiro-gols.csv.gz": "gols",
    "campeonato-brasileiro-cartoes.csv.gz": "cartoes",
}


def _milhar(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    faltando = [nome for nome in ARQUIVOS if not (PASTA_RAW / nome).is_file()]
    if faltando:
        print(f"Arquivos não encontrados em {PASTA_RAW}:")
        for nome in faltando:
            print(f"  {nome}")
        sys.exit(1)

    con = conectar()
    try:
        criar_schema(con, SCHEMA)
        contagens = {}
        for arquivo, tabela in ARQUIVOS.items():
            df = pd.read_csv(
                PASTA_RAW / arquivo,
                encoding="utf-8",
                dtype=str,
                keep_default_na=False,
                na_values=[""],
            )
            contagens[f"{SCHEMA}.{tabela}"] = gravar(con, df, SCHEMA, tabela)
    finally:
        con.close()

    largura = max(len(nome) for nome in contagens)
    for nome, n in contagens.items():
        print(f"{nome:<{largura}}  {_milhar(n):>7}")
    print(f"{'total':<{largura}}  {_milhar(sum(contagens.values())):>7}")


if __name__ == "__main__":
    main()
