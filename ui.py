"""Explorador do brasileirao.duckdb no navegador, via extensão ui do DuckDB.

Execução:
    uv run python ui.py

U1. O QUE FAZ
    Abre o brasileirao.duckdb da raiz do projeto, instala e carrega a extensão
    ui (INSTALL ui; LOAD ui;) e chama CALL start_ui(), que sobe o servidor em
    http://localhost:4213 e abre o navegador.
    Por quê: explorar as tabelas no navegador em vez de lê-las no terminal.

U2. FICA DE PÉ ATÉ CTRL+C
    A extensão só serve enquanto a conexão estiver viva. O script mantém o
    processo rodando, imprime a URL e "Ctrl+C para encerrar", e no Ctrl+C
    fecha a conexão e sai limpo, sem traceback.
    Por quê: o .duckdb aceita um único processo escrevendo. Com o ui.py de pé,
    a ingestão falha com "Could not set lock on file". Saber exatamente como
    desligar o servidor faz parte da ferramenta.

U3. NÃO CRIA BANCO
    Se brasileirao.duckdb não existir, avisa que é preciso rodar a ingestão
    antes e encerra com sys.exit(1). Por isso não usa conectar() de
    pipeline/db.py, que cria o arquivo quando ele falta.
    Por quê: um banco vazio aberto no navegador parece ingestão quebrada.

U4. SEPARAÇÃO
    Não importa pipeline/ingestao.py, e a ingestão não importa este arquivo.
    Por quê: a ingestão não pode depender de servidor, navegador ou da
    extensão ui para rodar.

U5. SAÍDA NA TELA
    stdout reconfigurado para utf-8.
    Por quê: no Prompt de Comando do Windows acento sai embaralhado por
    padrão.
"""

import sys
import time
from pathlib import Path

import duckdb

BANCO = Path(__file__).resolve().parent / "brasileirao.duckdb"
URL = "http://localhost:4213"


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    # A checagem vem antes do connect porque duckdb.connect cria o arquivo
    # quando ele não existe.
    if not BANCO.is_file():
        print(f"Banco não encontrado: {BANCO}")
        print("Rode a ingestão antes: uv run python -m pipeline.ingestao")
        sys.exit(1)

    con = duckdb.connect(BANCO)
    try:
        con.execute("INSTALL ui")
        con.execute("LOAD ui")
        con.execute("CALL start_ui()")
        print(f"DuckDB UI em {URL}")
        print("Ctrl+C para encerrar")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        con.close()


if __name__ == "__main__":
    main()
