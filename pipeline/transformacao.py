"""Etapa 2: transformação do schema raw no schema refined do DuckDB.

Execução:
    uv run python -m pipeline.transformacao

1. ESCOPO
   Lê de raw, escreve em refined, nunca escreve em raw. Entram as quatro
   tabelas (partidas, estatisticas, gols, cartoes); nenhuma fica de fora.
   Por quê: raw é a prova do que chegou. Se esta etapa escrevesse lá, não
   haveria mais contra o que conferir refined.

2. NOMES
   Colunas em português, snake_case, pelo mapa MAPA abaixo, completo e
   literal: nenhuma coluna fora dele, nenhuma descartada. A única coluna nova
   é acrescimo, que sai da divisão de minuto (item 3). A ordem das colunas em
   refined é a do mapa, com acrescimo logo depois de minuto.
   Por quê: é o vocabulário digitado de memória nos JOINs da etapa 3. O raw
   traz um erro de digitação (rodata) e maiúsculas soltas (mandante_Placar)
   que não devem ser carregados adiante.

3. TIPOS
   data   DATE, formato declarado '%d/%m/%Y'.
          Por quê: dia/mês/ano em 100% das linhas; sem formato declarado a
          leitura pode trocar dia por mês em silêncio (03/04 vira 4 de março).
   hora   TIME, formato declarado '%H:%M'. data e hora ficam separadas, como
          chegaram.
   arrecadacao  DECIMAL(10,2).
          Por quê: é dinheiro, e DOUBLE não representa centavos com exatidão.
          Em raw há no máximo 2 casas e 7 dígitos inteiros.
   posse_pct, precisao_passes_pct  INTEGER, sem o '%' do fim ('55%' -> 55);
          o texto 'None' vira NULL (item 6).
          Por quê: percentual é medida, entra em média; com '%' é texto.
   minuto (gols e cartoes)  duas colunas INTEGER: '90+9' -> minuto 90,
          acrescimo 9; '31' -> minuto 31, acrescimo NULL.
          Por quê: '90+9' não cabe em um número sem perder informação, e 99
          seria um minuto que não existe. NULL em acrescimo quer dizer "fora
          dos acréscimos", sem ambiguidade.
   Contagens e medidas  INTEGER: rodada, placares, chutes, chutes_no_alvo,
          passes, faltas, cartao_amarelo, cartao_vermelho, impedimentos,
          escanteios, minuto, acrescimo.
   Todo o resto continua VARCHAR, inclusive partida_id e num_camisa.
          Por quê: são rótulos (existe camisa 123 e 700), nunca entram em
          conta.
   A conversão é feita em SQL pelo DuckDB (strptime, CAST), disparada daqui.
   Por quê: o dado já está no banco; trazê-lo para a memória só para
   converter tipo não acrescenta nada.

4. CONVERSÃO QUE FALHA PARA TUDO
   Só strptime e CAST, que estouram; nunca try_strptime, TRY_CAST ou
   errors="coerce". Antes de converter, cada coluna convertida passa por uma
   checagem de formato por regex (inteiro: só dígitos; percentual: dígitos +
   '%'; minuto: N ou N+N; arrecadacao: dígitos com ponto e até 2 casas;
   data: dd/mm/aaaa; hora: HH:MM). Valor fora do formato para tudo do mesmo
   jeito que conversão que falha: diz tabela, coluna e um exemplo do valor,
   e encerra com sys.exit(1).
   Por quê: um nulo fabricado pela conversão fica indistinguível, para
   sempre, de um nulo verdadeiro do dado. E o DuckDB 2.0 arredonda em
   silêncio (CAST('1.5' AS INTEGER) dá 2): a regex é o que transforma esse
   arredondamento em erro.

5. DUPLICATAS
   Chaves: partidas (partida_id); estatisticas (partida_id, clube), uma
   linha por clube em cada partida. Nessas duas, linha inteira repetida
   mantém uma e conta quantas saíram; chave repetida com conteúdo diferente
   para, mostra a chave e as linhas conflitantes e encerra com sys.exit(1).
   Por quê: escolher uma das versões em silêncio é decidir sem dizer que
   decidiu.
   gols e cartoes não têm chave: a unidade é o evento, e dois eventos iguais
   podem existir de verdade (o mesmo atleta marcando duas vezes no mesmo
   minuto). Linha inteira repetida é contada e mostrada na tela, mas fica.
   Por quê: apagar um gol repetido quebraria a igualdade, hoje exata, entre
   o arquivo de gols e o placar das partidas.

6. NULOS
   Nenhuma linha é apagada por ter nulo; nenhum nulo é preenchido. Única
   conversão para nulo: o texto exato 'None' em posse_pct e
   precisao_passes_pct, contado à parte na tela.
   Por quê: 'None' é o marcador de ausência do arquivo de origem, igual ao
   campo vazio na prática, mas não cabe em INTEGER; contá-lo à parte impede
   que a decisão suma. Fora isso, nulo aqui é informação: formação e técnico
   só existem de 2014 em diante, arrecadação só em 2025, tipo de gol nulo é
   gol normal. Preencher qualquer um deles inventa dado.
   Anomalias de negócio ficam como chegaram, porque refined não corrige
   fato; quem decide o que fazer com elas é a pergunta que o mart responde:
     - 10.750 linhas de estatisticas inteiramente zeradas (zero = "não
       coletado");
     - cartões de estatisticas que não batem com o arquivo cartoes;
     - 268 gols contra com crédito de clube ambíguo;
     - vencedor '-' para empate (2.421 partidas), mantido como texto;
     - 'Zagueira' (22) ao lado de 'Zagueiro' em posicao;
     - arena com \\xa0 no início em 5.077 partidas;
     - 1 partida em que a posse dos dois clubes não soma 100;
     - 1 partida de 2007 às 00:00;
     - jogos da temporada 2020 com data em 2021 (temporada é decisão de
       mart, não coluna de refined).

7. SAÍDA NA TELA
   Uma linha por tabela:
       refined.partidas 9.165 -> 9.165 linhas (0 duplicatas)
   em gols e cartoes "(N repetidas mantidas)" no lugar de duplicatas.
   Abaixo, indentado, "nulos mantidos:" com as colunas que têm nulo e a
   contagem. Nessa linha entram só os nulos que já eram nulos em raw: em
   posse_pct e precisao_passes_pct ficam de fora os vindos de 'None', e
   acrescimo não aparece (o nulo dele é criado pela divisão de minuto, não
   mantido). Em estatisticas, uma linha a mais com os nulos vindos de
   'None'. Linha final:
       total 59.268 -> 59.268 linhas (0 duplicatas removidas)
   Contagens lidas do banco, milhar separado por ponto.
   Saída pelo logging de pipeline/log.py, só com o texto da mensagem: o
   relatório em INFO, no stdout; as mensagens de erro (itens 4, 5 e 9) em
   ERROR, no stderr. stdout e stderr em utf-8.
   Por quê: é o instrumento de conferência desta etapa; "nulos depois =
   nulos antes" tem que dar para ver sem abrir o banco. O logging separa
   erro de relatório, coisa que o print não fazia.

8. REEXECUÇÃO E GRAVAÇÃO
   CREATE OR REPLACE TABLE, nunca acrescenta: rodar dez vezes = rodar uma.
   Toda checagem (formato, conversão, chaves) roda antes de gravar qualquer
   tabela, e as quatro tabelas são gravadas numa transação só.
   Por quê: um refined pela metade, com tabelas de execuções diferentes,
   produz JOIN que não fecha sem erro nenhum.

9. ERRO
   Antes de transformar, verifica se as quatro tabelas existem em raw.
   Faltando qualquer uma, lista quais, manda rodar
   "uv run python -m pipeline.ingestao" e encerra com sys.exit(1).
   Por quê: transformar três de quatro tabelas deixa um refined que parece
   completo e não é.

10. ORGANIZAÇÃO
   main() só encadeia as etapas, uma função para cada: conferir as tabelas
   de entrada (9), validar formato (4), validar conversão (4), validar
   chaves (5), gravar (8) e relatar (7), nesta ordem.
   Por quê: cada etapa lida, testada e alterada sem atravessar as outras.

Convenção do DuckDB 2.0 neste projeto: todo resultado é consumido
(.fetchall() ou .complete()) antes do próximo comando na mesma conexão.
"""

import logging
import sys
from itertools import groupby

import duckdb

from pipeline.db import conectar, criar_schema
from pipeline.log import configurar_log

log = logging.getLogger("pipeline.transformacao")

ORIGEM = "raw"
DESTINO = "refined"

TEXTO = "texto"
INTEIRO = "inteiro"
PERCENTUAL = "percentual"
MINUTO = "minuto"
DINHEIRO = "dinheiro"
DATA = "data"
HORA = "hora"

# (coluna em raw, coluna em refined, tipo). A ordem aqui é a ordem em refined.
MAPA = {
    "partidas": [
        ("ID", "partida_id", TEXTO),
        ("rodata", "rodada", INTEIRO),
        ("data", "data", DATA),
        ("hora", "hora", HORA),
        ("mandante", "mandante", TEXTO),
        ("visitante", "visitante", TEXTO),
        ("formacao_mandante", "formacao_mandante", TEXTO),
        ("formacao_visitante", "formacao_visitante", TEXTO),
        ("tecnico_mandante", "tecnico_mandante", TEXTO),
        ("tecnico_visitante", "tecnico_visitante", TEXTO),
        ("vencedor", "vencedor", TEXTO),
        ("arena", "arena", TEXTO),
        ("mandante_Placar", "placar_mandante", INTEIRO),
        ("visitante_Placar", "placar_visitante", INTEIRO),
        ("mandante_Estado", "uf_mandante", TEXTO),
        ("visitante_Estado", "uf_visitante", TEXTO),
        ("arrecadacao", "arrecadacao", DINHEIRO),
    ],
    "estatisticas": [
        ("partida_id", "partida_id", TEXTO),
        ("rodata", "rodada", INTEIRO),
        ("clube", "clube", TEXTO),
        ("chutes", "chutes", INTEIRO),
        ("chutes_no_alvo", "chutes_no_alvo", INTEIRO),
        ("posse_de_bola", "posse_pct", PERCENTUAL),
        ("passes", "passes", INTEIRO),
        ("precisao_passes", "precisao_passes_pct", PERCENTUAL),
        ("faltas", "faltas", INTEIRO),
        ("cartao_amarelo", "cartao_amarelo", INTEIRO),
        ("cartao_vermelho", "cartao_vermelho", INTEIRO),
        ("impedimentos", "impedimentos", INTEIRO),
        ("escanteios", "escanteios", INTEIRO),
    ],
    "gols": [
        ("partida_id", "partida_id", TEXTO),
        ("rodata", "rodada", INTEIRO),
        ("clube", "clube", TEXTO),
        ("atleta", "atleta", TEXTO),
        ("minuto", "minuto", MINUTO),
        ("tipo_de_gol", "tipo", TEXTO),
    ],
    "cartoes": [
        ("partida_id", "partida_id", TEXTO),
        ("rodata", "rodada", INTEIRO),
        ("clube", "clube", TEXTO),
        ("cartao", "cartao", TEXTO),
        ("atleta", "atleta", TEXTO),
        ("num_camisa", "num_camisa", TEXTO),
        ("posicao", "posicao", TEXTO),
        ("minuto", "minuto", MINUTO),
    ],
}

# Chaves em nomes de raw, porque a checagem roda sobre o dado como chegou.
CHAVES = {
    "partidas": ["ID"],
    "estatisticas": ["partida_id", "clube"],
}

REGEX = {
    INTEIRO: r"[0-9]+",
    PERCENTUAL: r"[0-9]+%",
    MINUTO: r"[0-9]+(\+[0-9]+)?",
    DINHEIRO: r"[0-9]+(\.[0-9]{1,2})?",
    DATA: r"[0-9]{2}/[0-9]{2}/[0-9]{4}",
    HORA: r"[0-9]{2}:[0-9]{2}",
}


def _q(nome: str) -> str:
    return f'"{nome}"'


def _milhar(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def _expressoes(origem: str, destino: str, tipo: str) -> list[tuple[str, str]]:
    """Colunas de refined geradas por uma coluna de raw: [(nome, expressão SQL)]."""
    c = _q(origem)
    if tipo == TEXTO:
        return [(destino, c)]
    if tipo == INTEIRO:
        return [(destino, f"CAST({c} AS INTEGER)")]
    if tipo == PERCENTUAL:
        return [
            (
                destino,
                f"CASE WHEN {c} = 'None' THEN NULL "
                f"ELSE CAST(rtrim({c}, '%') AS INTEGER) END",
            )
        ]
    if tipo == MINUTO:
        return [
            (destino, f"CAST(split_part({c}, '+', 1) AS INTEGER)"),
            (
                "acrescimo",
                f"CASE WHEN {c} LIKE '%+%' "
                f"THEN CAST(split_part({c}, '+', 2) AS INTEGER) END",
            ),
        ]
    if tipo == DINHEIRO:
        return [(destino, f"CAST({c} AS DECIMAL(10,2))")]
    if tipo == DATA:
        return [(destino, f"CAST(strptime({c}, '%d/%m/%Y') AS DATE)")]
    if tipo == HORA:
        return [(destino, f"CAST(strptime({c}, '%H:%M') AS TIME)")]
    raise ValueError(tipo)


def _selecao(tabela: str) -> str:
    return ", ".join(
        f"{expr} AS {_q(nome)}"
        for origem, destino, tipo in MAPA[tabela]
        for nome, expr in _expressoes(origem, destino, tipo)
    )


def _fora_do_formato(con, tabela: str, origem: str, tipo: str) -> str | None:
    c = _q(origem)
    condicao = f"{c} IS NOT NULL AND NOT regexp_full_match({c}, ?)"
    if tipo == PERCENTUAL:
        condicao += f" AND {c} <> 'None'"
    # ORDER BY para o exemplo ser sempre o mesmo entre execuções.
    linhas = con.execute(
        f"SELECT {c} FROM {ORIGEM}.{tabela} WHERE {condicao} ORDER BY 1 LIMIT 1",
        [REGEX[tipo]],
    ).fetchall()
    return linhas[0][0] if linhas else None


def _falha_de_conversao(con, tabela: str, origem: str, expr: str) -> str | None:
    try:
        con.execute(f"SELECT min({expr}) FROM {ORIGEM}.{tabela}").fetchall()
        return None
    except duckdb.Error as erro:
        original = erro
    # A mensagem do DuckDB nem sempre traz o valor como ele estava em raw
    # ('31/02/2020' vira "2020-2-31"), então o exemplo é isolado convertendo
    # valor a valor. Só roda no caminho de erro.
    c = _q(origem)
    valores = con.execute(
        f"SELECT DISTINCT {c} FROM {ORIGEM}.{tabela} WHERE {c} IS NOT NULL ORDER BY 1"
    ).fetchall()
    for (valor,) in valores:
        try:
            con.execute(
                f"SELECT {expr} FROM (SELECT ?::VARCHAR AS {c})", [valor]
            ).fetchall()
        except duckdb.Error:
            return valor
    raise original


def _duplicatas(con, tabela: str) -> int:
    t = f"{ORIGEM}.{tabela}"
    [(n,)] = con.execute(
        f"SELECT (SELECT count(*) FROM {t}) - (SELECT count(*) FROM (SELECT DISTINCT * FROM {t}))"
    ).fetchall()
    return n


def _conflitos(con, tabela: str) -> list[str]:
    chave = CHAVES[tabela]
    colunas = [origem for origem, _, _ in MAPA[tabela]]
    k = ", ".join(_q(c) for c in chave)
    todas = ", ".join(_q(c) for c in colunas)
    linhas = con.execute(
        f"SELECT {todas} FROM (SELECT DISTINCT * FROM {ORIGEM}.{tabela}) "
        f"QUALIFY count(*) OVER (PARTITION BY {k}) > 1 ORDER BY {k}, {todas}"
    ).fetchall()
    posicoes = [colunas.index(c) for c in chave]
    saida = []
    for valor_chave, grupo in groupby(
        linhas, key=lambda r: tuple(r[i] for i in posicoes)
    ):
        saida.append(f"  {ORIGEM}.{tabela} {dict(zip(chave, valor_chave))}:")
        saida.extend(f"    {dict(zip(colunas, linha))}" for linha in grupo)
    return saida


def _contar(con, sql: str) -> int:
    [(n,)] = con.execute(sql).fetchall()
    return n


def _abortar(titulo: str, linhas: list[str]) -> None:
    log.error("%s", titulo)
    for linha in linhas:
        log.error("%s", linha)
    sys.exit(1)


def _exigir_origem(con) -> None:
    existentes = {
        nome
        for (nome,) in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = ?",
            [ORIGEM],
        ).fetchall()
    }
    faltando = [t for t in MAPA if t not in existentes]
    if faltando:
        _abortar(
            f"Tabelas não encontradas no schema {ORIGEM}:",
            [f"  {ORIGEM}.{t}" for t in faltando]
            + ["Rode antes: uv run python -m pipeline.ingestao"],
        )


def _validar_formato(con) -> None:
    falhas = []
    for tabela, colunas in MAPA.items():
        for origem, _, tipo in colunas:
            if tipo == TEXTO:
                continue
            valor = _fora_do_formato(con, tabela, origem, tipo)
            if valor is not None:
                falhas.append(f"  {ORIGEM}.{tabela}.{origem} ({tipo}): {valor!r}")
    if falhas:
        _abortar("Valor fora do formato esperado; nada foi gravado:", falhas)


def _validar_conversao(con) -> None:
    falhas = []
    for tabela, colunas in MAPA.items():
        for origem, destino, tipo in colunas:
            if tipo == TEXTO:
                continue
            for nome, expr in _expressoes(origem, destino, tipo):
                valor = _falha_de_conversao(con, tabela, origem, expr)
                if valor is not None:
                    falhas.append(f"  {ORIGEM}.{tabela}.{origem} -> {nome}: {valor!r}")
    if falhas:
        _abortar("Valor que não converteu; nada foi gravado:", falhas)


def _validar_chaves(con) -> None:
    conflitos = [linha for tabela in CHAVES for linha in _conflitos(con, tabela)]
    if conflitos:
        _abortar("Chave repetida com conteúdo diferente; nada foi gravado:", conflitos)


def _gravar_refined(con) -> None:
    con.execute("BEGIN TRANSACTION").complete()
    try:
        criar_schema(con, DESTINO)
        for tabela in MAPA:
            distinct = "DISTINCT " if tabela in CHAVES else ""
            con.execute(
                f"CREATE OR REPLACE TABLE {DESTINO}.{tabela} AS "
                f"SELECT {distinct}{_selecao(tabela)} FROM {ORIGEM}.{tabela}"
            ).complete()
        con.execute("COMMIT").complete()
    except BaseException:
        con.execute("ROLLBACK").complete()
        raise


def _nulos(con, tabela: str, colunas: list) -> tuple[list[str], dict[str, int]]:
    """Nulos mantidos de uma tabela de refined, já sem os vindos de 'None', e estes à parte."""
    # acrescimo fica de fora: seu nulo nasce da divisão de minuto.
    nomes = [destino for _, destino, _ in colunas]
    nulos = con.execute(
        "SELECT "
        + ", ".join(f"count(*) - count({_q(n)})" for n in nomes)
        + f" FROM {DESTINO}.{tabela}"
    ).fetchall()[0]
    percentuais = [(o, d) for o, d, t in colunas if t == PERCENTUAL]
    vindos_de_none = {}
    if percentuais:
        contagens = con.execute(
            "SELECT "
            + ", ".join(
                f"count(*) FILTER (WHERE {_q(o)} = 'None')" for o, _ in percentuais
            )
            + f" FROM {ORIGEM}.{tabela}"
        ).fetchall()[0]
        vindos_de_none = {d: n for (_, d), n in zip(percentuais, contagens)}

    mantidos = [
        f"{nome} {_milhar(n - vindos_de_none.get(nome, 0))}"
        for nome, n in zip(nomes, nulos)
        if n - vindos_de_none.get(nome, 0) > 0
    ]
    return mantidos, vindos_de_none


def _relatar(con, entrada: dict[str, int], repetidas: dict[str, int]) -> None:
    total_entrada = total_saida = total_removidas = 0
    for tabela, colunas in MAPA.items():
        saida = _contar(con, f"SELECT count(*) FROM {DESTINO}.{tabela}")
        if tabela in CHAVES:
            sufixo = f"{_milhar(repetidas[tabela])} duplicatas"
            total_removidas += repetidas[tabela]
        else:
            sufixo = f"{_milhar(repetidas[tabela])} repetidas mantidas"
        log.info(
            "%s.%s %s -> %s linhas (%s)",
            DESTINO,
            tabela,
            _milhar(entrada[tabela]),
            _milhar(saida),
            sufixo,
        )
        total_entrada += entrada[tabela]
        total_saida += saida

        mantidos, vindos_de_none = _nulos(con, tabela, colunas)
        log.info("    nulos mantidos: %s", ", ".join(mantidos) or "nenhum")
        if vindos_de_none:
            log.info(
                "    'None' -> NULL: %s",
                ", ".join(f"{d} {_milhar(n)}" for d, n in vindos_de_none.items()),
            )

    log.info(
        "total %s -> %s linhas (%s duplicatas removidas)",
        _milhar(total_entrada),
        _milhar(total_saida),
        _milhar(total_removidas),
    )


def main() -> None:
    configurar_log()

    con = conectar()
    try:
        _exigir_origem(con)
        _validar_formato(con)
        _validar_conversao(con)
        _validar_chaves(con)
        entrada = {t: _contar(con, f"SELECT count(*) FROM {ORIGEM}.{t}") for t in MAPA}
        repetidas = {t: _duplicatas(con, t) for t in MAPA}
        _gravar_refined(con)
        _relatar(con, entrada, repetidas)
    finally:
        con.close()


if __name__ == "__main__":
    main()
