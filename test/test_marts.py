"""Testes de pipeline/marts.py (o executor) e dos arquivos reais de sql/marts/,
rodados sobre tabelas refined inventadas em tmp_path."""

import datetime

import duckdb
import pytest

from pipeline import db, marts

# Lida antes de qualquer monkeypatch: os .sql reais podem ser lidos; o dado, não.
PASTA_SQL_REAL = marts.PASTA_MARTS

# Mesmas colunas e tipos que pipeline/transformacao.py grava em refined.
REFINED = {
    "partidas": (
        "partida_id VARCHAR, rodada INTEGER, data DATE, hora TIME, mandante VARCHAR, "
        "visitante VARCHAR, formacao_mandante VARCHAR, formacao_visitante VARCHAR, "
        "tecnico_mandante VARCHAR, tecnico_visitante VARCHAR, vencedor VARCHAR, "
        "arena VARCHAR, placar_mandante INTEGER, placar_visitante INTEGER, "
        "uf_mandante VARCHAR, uf_visitante VARCHAR, arrecadacao DECIMAL(10,2)"
    ),
    "estatisticas": (
        "partida_id VARCHAR, rodada INTEGER, clube VARCHAR, chutes INTEGER, "
        "chutes_no_alvo INTEGER, posse_pct INTEGER, passes INTEGER, "
        "precisao_passes_pct INTEGER, faltas INTEGER, cartao_amarelo INTEGER, "
        "cartao_vermelho INTEGER, impedimentos INTEGER, escanteios INTEGER"
    ),
    "gols": (
        "partida_id VARCHAR, rodada INTEGER, clube VARCHAR, atleta VARCHAR, "
        "minuto INTEGER, acrescimo INTEGER, tipo VARCHAR"
    ),
    "cartoes": (
        "partida_id VARCHAR, rodada INTEGER, clube VARCHAR, cartao VARCHAR, "
        "atleta VARCHAR, num_camisa VARCHAR, posicao VARCHAR, minuto INTEGER, "
        "acrescimo INTEGER"
    ),
}


def _criar_refined(con, sem=()):
    con.execute("CREATE SCHEMA refined")
    for tabela, colunas in REFINED.items():
        if tabela not in sem:
            con.execute(f"CREATE TABLE refined.{tabela} ({colunas})")


def _partida(
    con, partida_id, data, mandante, visitante, placar_mandante, placar_visitante
):
    con.execute(
        "INSERT INTO refined.partidas "
        "(partida_id, data, mandante, visitante, placar_mandante, placar_visitante) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [partida_id, data, mandante, visitante, placar_mandante, placar_visitante],
    )


def _gol(con, partida_id, clube, atleta, minuto, acrescimo=None, tipo=None):
    con.execute(
        "INSERT INTO refined.gols (partida_id, clube, atleta, minuto, acrescimo, tipo) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [partida_id, clube, atleta, minuto, acrescimo, tipo],
    )


# ---------------------------------------------------------------- executor


def _ambiente(tmp_path, monkeypatch, sem=()):
    banco = tmp_path / "teste.duckdb"
    pasta = tmp_path / "marts"
    pasta.mkdir()
    monkeypatch.setattr(db, "_BANCO", banco)
    monkeypatch.setattr(marts, "PASTA_MARTS", pasta)
    con = duckdb.connect(str(banco))
    _criar_refined(con, sem)
    con.close()
    return banco, pasta


def _marts_no_banco(banco):
    """{tabela: linhas} do schema marts; vazio se o schema não existir."""
    con = duckdb.connect(str(banco))
    try:
        tabelas = con.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'marts' ORDER BY 1"
        ).fetchall()
        return {
            t: con.execute(f'SELECT * FROM marts."{t}" ORDER BY ALL').fetchall()
            for (t,) in tabelas
        }
    finally:
        con.close()


def test_arquivo_vira_tabela_com_o_nome_sem_prefixo_numerico(tmp_path, monkeypatch):
    banco, pasta = _ambiente(tmp_path, monkeypatch)
    (pasta / "00_teste.sql").write_text("SELECT 1 AS x", encoding="utf-8")
    marts.main()
    assert _marts_no_banco(banco) == {"teste": [(1,)]}


def test_bom_e_ponto_e_virgula_final_nao_quebram_a_sql(tmp_path, monkeypatch):
    banco, pasta = _ambiente(tmp_path, monkeypatch)
    # BOM como o PowerShell 5.1 grava, ';' e espaços no fim.
    (pasta / "01_com_bom.sql").write_bytes(b"\xef\xbb\xbfSELECT 2 AS y;  \n")
    marts.main()
    assert _marts_no_banco(banco) == {"com_bom": [(2,)]}


def test_arquivo_apagado_faz_o_mart_sumir_na_execucao_seguinte(tmp_path, monkeypatch):
    banco, pasta = _ambiente(tmp_path, monkeypatch)
    (pasta / "00_teste.sql").write_text("SELECT 1 AS x", encoding="utf-8")
    (pasta / "01_fica.sql").write_text("SELECT 2 AS x", encoding="utf-8")
    marts.main()
    (pasta / "00_teste.sql").unlink()
    marts.main()
    assert _marts_no_banco(banco) == {"fica": [(2,)]}


def test_arquivo_sem_prefixo_para_antes_de_executar_qualquer_sql(tmp_path, monkeypatch):
    banco, pasta = _ambiente(tmp_path, monkeypatch)
    (pasta / "01_valido.sql").write_text("SELECT 1 AS x", encoding="utf-8")
    (pasta / "teste.sql").write_text("SELECT 1 AS x", encoding="utf-8")
    with pytest.raises(SystemExit) as saida:
        marts.main()
    assert saida.value.code == 1
    assert _marts_no_banco(banco) == {}


def test_dois_arquivos_com_o_mesmo_nome_de_tabela_param_antes_de_executar(
    tmp_path, monkeypatch
):
    banco, pasta = _ambiente(tmp_path, monkeypatch)
    # Maiúscula não diferencia tabela no DuckDB: os dois viram marts.gols.
    (pasta / "01_gols.sql").write_text("SELECT 1 AS x", encoding="utf-8")
    (pasta / "02_Gols.sql").write_text("SELECT 2 AS x", encoding="utf-8")
    with pytest.raises(SystemExit):
        marts.main()
    assert _marts_no_banco(banco) == {}


def test_mart_vazio_encerra_e_deixa_o_schema_marts_como_estava(tmp_path, monkeypatch):
    banco, pasta = _ambiente(tmp_path, monkeypatch)
    (pasta / "01_antigo.sql").write_text("SELECT 1 AS x", encoding="utf-8")
    marts.main()
    antes = _marts_no_banco(banco)
    # refined.partidas inventada está vazia: o mart volta com zero linhas.
    (pasta / "02_vazio.sql").write_text(
        "SELECT * FROM refined.partidas", encoding="utf-8"
    )
    with pytest.raises(SystemExit) as saida:
        marts.main()
    assert saida.value.code == 1
    assert _marts_no_banco(banco) == antes


def test_erro_de_sintaxe_encerra_e_deixa_o_schema_marts_como_estava(
    tmp_path, monkeypatch
):
    banco, pasta = _ambiente(tmp_path, monkeypatch)
    (pasta / "01_antigo.sql").write_text("SELECT 1 AS x", encoding="utf-8")
    marts.main()
    antes = _marts_no_banco(banco)
    # Um mart novo que funciona antes do quebrado: também tem que ser desfeito.
    (pasta / "00_novo.sql").write_text("SELECT 3 AS x", encoding="utf-8")
    (pasta / "02_quebrado.sql").write_text("SELEC 1", encoding="utf-8")
    with pytest.raises(SystemExit):
        marts.main()
    assert _marts_no_banco(banco) == antes


def test_pasta_sem_arquivo_sql_encerra(tmp_path, monkeypatch):
    banco, pasta = _ambiente(tmp_path, monkeypatch)
    # Arquivo que não é .sql não conta.
    (pasta / "leia-me.txt").write_text("nada", encoding="utf-8")
    with pytest.raises(SystemExit) as saida:
        marts.main()
    assert saida.value.code == 1
    assert _marts_no_banco(banco) == {}


def test_falta_de_tabela_em_refined_encerra(tmp_path, monkeypatch):
    banco, pasta = _ambiente(tmp_path, monkeypatch, sem=["gols"])
    (pasta / "00_teste.sql").write_text("SELECT 1 AS x", encoding="utf-8")
    with pytest.raises(SystemExit) as saida:
        marts.main()
    assert saida.value.code == 1
    assert _marts_no_banco(banco) == {}


# ---------------------------------------------------------------- sql/marts


def _refined_vazio(tmp_path):
    con = duckdb.connect(str(tmp_path / "teste.duckdb"))
    _criar_refined(con)
    return con


def _mart(con, arquivo):
    """Roda o .sql real de sql/marts/ e devolve uma lista de dicts."""
    sql = (PASTA_SQL_REAL / arquivo).read_text(encoding="utf-8-sig")
    resultado = con.execute(sql)
    colunas = [d[0] for d in resultado.description]
    return [dict(zip(colunas, linha)) for linha in resultado.fetchall()]


def test_01_jogo_em_fevereiro_de_2021_conta_na_temporada_2020(tmp_path):
    con = _refined_vazio(tmp_path)
    # Agosto de 2020: temporada 2020, sem dúvida.
    _partida(con, "1", datetime.date(2020, 8, 9), "Flamengo", "Atletico-MG", 0, 1)
    # Fevereiro de 2021: fim da temporada 2020, adiada pela pandemia.
    _partida(con, "2", datetime.date(2021, 2, 25), "Internacional", "Flamengo", 1, 2)
    # Junho de 2021: temporada 2021.
    _partida(con, "3", datetime.date(2021, 6, 1), "Flamengo", "Palmeiras", 1, 1)
    linhas = _mart(con, "01_gols_por_temporada.sql")
    con.close()
    assert {r["temporada"]: r["partidas"] for r in linhas} == {2020: 2, 2021: 1}
    assert {r["temporada"]: r["gols"] for r in linhas} == {2020: 4, 2021: 2}


def test_02_gol_contra_fica_fora_do_artilheiro(tmp_path):
    con = _refined_vazio(tmp_path)
    _partida(con, "1", datetime.date(2024, 6, 1), "Flamengo", "Vasco", 3, 0)
    # Gol normal: conta para Pedro.
    _gol(con, "1", "Flamengo", "Pedro", 10)
    # Gol contra creditado a Pedro: não é gol dele.
    _gol(con, "1", "Flamengo", "Pedro", 20, tipo="Gol Contra")
    # Pênalti: conta como gol e como gols_penalti.
    _gol(con, "1", "Flamengo", "Arrascaeta", 30, tipo="Penalty")
    # Atleta que só fez gol contra: não aparece.
    _gol(con, "1", "Flamengo", "Leo", 40, tipo="Gol Contra")
    linhas = _mart(con, "02_artilheiros.sql")
    con.close()
    gols = {r["atleta"]: (r["gols"], r["gols_penalti"]) for r in linhas}
    assert gols == {"Pedro": (1, 0), "Arrascaeta": (1, 1)}


def test_04_vitoria_vale_3_empate_1_derrota_0_e_o_mais_pontuado_e_o_primeiro(tmp_path):
    con = _refined_vazio(tmp_path)
    dia = datetime.date(2024, 6, 1)
    # A vence B: A 3 pontos, B 0.
    _partida(con, "1", dia, "A", "B", 2, 0)
    # A empata com C: 1 ponto para cada.
    _partida(con, "2", dia, "C", "A", 1, 1)
    # B vence C fora de casa: B 3, C 0.
    _partida(con, "3", dia, "C", "B", 0, 1)
    linhas = _mart(con, "04_classificacao.sql")
    con.close()
    tabela = {
        r["clube"]: (
            r["posicao"],
            r["pontos"],
            r["vitorias"],
            r["empates"],
            r["derrotas"],
        )
        for r in linhas
    }
    assert tabela == {
        "A": (1, 4, 1, 1, 0),
        "B": (2, 3, 1, 0, 1),
        "C": (3, 1, 0, 1, 1),
    }


def test_13_gol_aos_90_mais_3_vai_para_a_faixa_90_mais_e_nao_76_90(tmp_path):
    con = _refined_vazio(tmp_path)
    # 90+3: acréscimo do segundo tempo.
    _gol(con, "1", "Flamengo", "Pedro", 90, acrescimo=3)
    # 90 sem acréscimo: fica em 76-90.
    _gol(con, "1", "Flamengo", "Pedro", 90)
    # 80: tempo normal, 76-90.
    _gol(con, "1", "Flamengo", "Pedro", 80)
    # 45+2: acréscimo do primeiro tempo, não 31-45.
    _gol(con, "1", "Flamengo", "Pedro", 45, acrescimo=2)
    linhas = _mart(con, "13_gols_por_minuto.sql")
    con.close()
    assert {r["faixa"]: r["gols"] for r in linhas} == {"45+": 1, "76-90": 2, "90+": 1}
    assert [r["faixa"] for r in linhas] == ["45+", "76-90", "90+"]


def test_14_atleta_que_marcou_por_dois_clubes_tem_duas_linhas(tmp_path):
    con = _refined_vazio(tmp_path)
    _partida(con, "1", datetime.date(2023, 6, 1), "Fluminense", "Santos", 2, 0)
    _partida(con, "2", datetime.date(2024, 6, 1), "Atletico-MG", "Bahia", 1, 0)
    # Dois gols de Fred pelo Fluminense.
    _gol(con, "1", "Fluminense", "Fred", 10)
    _gol(con, "1", "Fluminense", "Fred", 70)
    # Um gol de Fred pelo Atlético-MG, em outra temporada.
    _gol(con, "2", "Atletico-MG", "Fred", 30)
    linhas = _mart(con, "14_artilheiros_por_clube.sql")
    con.close()
    assert {(r["clube"], r["atleta"]): r["gols"] for r in linhas} == {
        ("Atletico-MG", "Fred"): 1,
        ("Fluminense", "Fred"): 2,
    }
