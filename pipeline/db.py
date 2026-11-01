"""Conexão com o banco, compartilhada por todas as etapas do pipeline.

Expõe exatamente:
    PASTA_RAW                          Path da pasta raw/ com os quatro .csv.gz
    conectar()                         abre o brasileirao.duckdb, criando se faltar
    criar_schema(con, nome)            CREATE SCHEMA IF NOT EXISTS
    gravar(con, df, schema, tabela)    grava e devolve a contagem lida do banco

D1. CAMINHOS
    PASTA_RAW e o brasileirao.duckdb são resolvidos a partir da localização
    deste arquivo (a pasta acima de pipeline/), nunca do diretório corrente.
    Por quê: rodar o script de outra pasta criaria um brasileirao.duckdb vazio
    no lugar errado, e um banco vazio parece ingestão quebrada.

D2. TRÊS FUNÇÕES E UMA CONSTANTE, NADA MAIS
    Este módulo não lê CSV, não conhece nome de tabela, não imprime nada e não
    converte tipo. Quem decide isso é cada etapa.
    Por quê: todas as etapas importam este arquivo. Uma regra de negócio
    escondida aqui passaria a valer para todas elas sem aparecer em nenhuma
    spec.

D3. gravar
    Recria a tabela (CREATE OR REPLACE TABLE schema.tabela) com as colunas e os
    tipos do DataFrame, sem alterar nada: coluna str vira VARCHAR, nulo
    continua NULL. Não deixa view nem tabela temporária para trás. Devolve o
    SELECT count(*) da tabela recém-gravada, lido do banco.
    Por quê: a contagem que aparece na tela tem que ser a do que foi gravado,
    não a do que estava na memória. Recriar em vez de acrescentar é o que
    torna a reexecução segura.

D4. CONEXÃO
    conectar() devolve a conexão aberta; quem chama é quem fecha. Não há
    conexão global.
    Por quê: o .duckdb aceita um único processo escrevendo. Uma conexão
    esquecida aberta num módulo importado seguraria o lock sem que ninguém
    soubesse de onde ele vem.

Importar este módulo não abre banco nem cria arquivo: só resolve caminhos.
"""

from pathlib import Path

import duckdb
import pandas as pd

_RAIZ = Path(__file__).resolve().parent.parent
_BANCO = _RAIZ / "brasileirao.duckdb"

PASTA_RAW = _RAIZ / "raw"


def conectar() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(_BANCO)


def criar_schema(con: duckdb.DuckDBPyConnection, nome: str) -> None:
    con.execute(f'CREATE SCHEMA IF NOT EXISTS "{nome}"')


def gravar(
    con: duckdb.DuckDBPyConnection, df: pd.DataFrame, schema: str, tabela: str
) -> int:
    destino = f'"{schema}"."{tabela}"'
    # O DataFrame entra por uma view registrada só durante o CREATE e removida
    # no finally, para não sobrar nada na conexão de quem chamou.
    con.register("_gravar_df", df)
    try:
        con.execute(f"CREATE OR REPLACE TABLE {destino} AS SELECT * FROM _gravar_df")
    finally:
        con.unregister("_gravar_df")
    # fetchall, e não fetchone: no DuckDB 2.0 um fetchone deixa o resultado
    # pendente e a próxima operação na mesma conexão falha com Resource In Use.
    [(n,)] = con.execute(f"SELECT count(*) FROM {destino}").fetchall()
    return n
