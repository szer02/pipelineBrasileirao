"""Etapa 3: um mart por arquivo de sql/marts/, do schema refined no schema marts.

Execução:
    uv run python -m pipeline.marts

1. ESCOPO
   Lê de refined, escreve no schema marts, nunca escreve em raw nem em
   refined. O schema marts é apagado e recriado a cada execução
   (DROP SCHEMA IF EXISTS marts CASCADE).
   Por quê: um mart cujo arquivo foi apagado não pode continuar existindo no
   banco.

2. UM ARQUIVO, UMA TABELA
   Lê todos os sql/marts/*.sql em ordem alfabética, com encoding utf-8-sig.
   Por quê do utf-8-sig: o PowerShell 5.1 grava BOM com -Encoding utf8, e o
   BOM no início do arquivo quebraria a SQL.
   Nome da tabela = nome do arquivo sem a extensão e sem o prefixo numérico:
       sql/marts/01_gols_por_temporada.sql -> marts.gols_por_temporada
   Executa: CREATE TABLE marts.<nome> AS <conteúdo do arquivo>
   Tira espaços e um ponto e vírgula do final do conteúdo, e nada mais. O
   Python não altera, não monta e não completa a SQL.
   Por quê: a regra de negócio mora inteira no arquivo .sql.

3. SAÍDA NA TELA
   Uma linha por mart, com a contagem vinda do banco, milhar com ponto:
       ✓ marts.gols_por_temporada        23 linhas
   Linha final com o número de marts e o total de linhas. stdout
   reconfigurado para utf-8.
   Por quê: é o instrumento de conferência desta etapa; a contagem tem que
   ser a do que foi gravado, não a do que se esperava gravar.

4. ERRO
   Antes de tudo: faltando qualquer uma das quatro tabelas em refined
   (partidas, estatisticas, gols, cartoes), lista quais, manda rodar
   "uv run python -m pipeline.transformacao" e encerra com sys.exit(1).
   Por quê: os marts leem de refined; sem ele, todo mart falharia, e a
   mensagem do DuckDB não diria qual etapa rodar.
   Se sql/marts/ não tiver nenhum arquivo: avisa e sys.exit(1).
   Por quê: zero marts apagaria o schema inteiro e deixaria o painel vazio.
   Antes de executar qualquer SQL: arquivo sem prefixo NN_ ou dois arquivos
   que dão o mesmo nome de tabela -> lista quais e sys.exit(1).
   Por quê: sem prefixo não há nome de tabela definido; com nome repetido,
   um mart sobrescreveria o outro sem aviso.
   Se um .sql falhar: mostra o nome do arquivo e a mensagem do DuckDB, não
   executa os seguintes, sys.exit(1).
   Se um mart voltar com zero linhas: mostra o nome e encerra com
   sys.exit(1).
   Por quê: mart vazio é quase sempre um JOIN que não casou, e um painel
   vazio parece um campeonato sem jogos.
   Tudo roda numa transação só: se qualquer passo falhar (inclusive o mart
   vazio), o schema marts volta a ser o da última execução que deu certo.
   Por quê: um schema pela metade quebra o painel sem avisar.

Convenção do DuckDB 2.0 neste projeto: todo resultado é consumido
(.fetchall() ou .complete()) antes do próximo comando na mesma conexão.
"""

import re
import sys
from pathlib import Path

import duckdb

from pipeline.db import conectar, criar_schema

ORIGEM = "refined"
DESTINO = "marts"
TABELAS_ORIGEM = ["partidas", "estatisticas", "gols", "cartoes"]

# Resolvida a partir deste arquivo, não do diretório corrente, pelo mesmo
# motivo de db.py (D1).
PASTA_MARTS = Path(__file__).resolve().parent.parent / "sql" / "marts"

PREFIXO = re.compile(r"[0-9]{2}_(.+)")


def _milhar(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _sql(arquivo: Path) -> str:
    texto = arquivo.read_text(encoding="utf-8-sig").rstrip()
    return texto.removesuffix(";")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")

    con = conectar()
    try:
        existentes = {
            nome
            for (nome,) in con.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = ?",
                [ORIGEM],
            ).fetchall()
        }
        faltando = [t for t in TABELAS_ORIGEM if t not in existentes]
        if faltando:
            print(f"Tabelas não encontradas no schema {ORIGEM}:")
            for t in faltando:
                print(f"  {ORIGEM}.{t}")
            print("Rode antes: uv run python -m pipeline.transformacao")
            sys.exit(1)

        arquivos = sorted(PASTA_MARTS.glob("*.sql"), key=lambda p: p.name)
        if not arquivos:
            print(f"Nenhum arquivo .sql em {PASTA_MARTS}; nada foi executado.")
            sys.exit(1)

        sem_prefixo = []
        por_nome: dict[str, list[Path]] = {}
        for arquivo in arquivos:
            casou = PREFIXO.fullmatch(arquivo.stem)
            if casou is None:
                sem_prefixo.append(arquivo)
            else:
                # O DuckDB não diferencia maiúsculas em nome de tabela:
                # 01_Gols e 02_gols seriam a mesma tabela.
                por_nome.setdefault(casou.group(1).lower(), []).append(arquivo)
        repetidos = {nome: lista for nome, lista in por_nome.items() if len(lista) > 1}
        if sem_prefixo or repetidos:
            if sem_prefixo:
                print("Arquivos sem o prefixo NN_:")
                for arquivo in sem_prefixo:
                    print(f"  {arquivo.name}")
            if repetidos:
                print("Arquivos que dão o mesmo nome de tabela:")
                for nome, lista in repetidos.items():
                    print(f"  {DESTINO}.{nome}: {', '.join(a.name for a in lista)}")
            print("Nenhum SQL foi executado.")
            sys.exit(1)

        marts = [(a, PREFIXO.fullmatch(a.stem).group(1)) for a in arquivos]

        contagens = []
        con.execute("BEGIN TRANSACTION").complete()
        try:
            con.execute(f'DROP SCHEMA IF EXISTS "{DESTINO}" CASCADE').complete()
            criar_schema(con, DESTINO)
            for arquivo, nome in marts:
                destino = f'"{DESTINO}"."{nome}"'
                try:
                    con.execute(f"CREATE TABLE {destino} AS {_sql(arquivo)}").complete()
                except duckdb.Error as erro:
                    print(f"Falhou: {arquivo.name}")
                    print(erro)
                    print(f"O schema {DESTINO} ficou como estava antes desta execução.")
                    sys.exit(1)
                [(n,)] = con.execute(f"SELECT count(*) FROM {destino}").fetchall()
                if n == 0:
                    print(
                        f"Mart vazio: {arquivo.name} -> {DESTINO}.{nome} com 0 linhas"
                    )
                    print(f"O schema {DESTINO} ficou como estava antes desta execução.")
                    sys.exit(1)
                contagens.append((f"{DESTINO}.{nome}", n))
            con.execute("COMMIT").complete()
        except BaseException:
            con.execute("ROLLBACK").complete()
            raise

        # Impresso só depois do COMMIT: um ✓ antes dele poderia ser desfeito
        # pelo ROLLBACK de um mart seguinte.
        largura_nome = max(len(nome) for nome, _ in contagens)
        largura_n = max(len(_milhar(n)) for _, n in contagens)
        for nome, n in contagens:
            print(f"✓ {nome:<{largura_nome}}  {_milhar(n):>{largura_n}} linhas")
        total = sum(n for _, n in contagens)
        print(f"total {len(contagens)} marts, {_milhar(total)} linhas")
    finally:
        con.close()


if __name__ == "__main__":
    main()
