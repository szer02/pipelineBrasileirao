"""Testes de pipeline/transformacao.py, sobre um raw inventado em tmp_path."""

import datetime
from decimal import Decimal

import duckdb
import pytest

from pipeline import db, transformacao


def _partida(**valores):
    linha = dict.fromkeys(o for o, _, _ in transformacao.MAPA["partidas"])
    linha.update(valores)
    return linha


def _linhas_validas():
    """Uma linha por motivo; colunas não citadas ficam NULL, que não é
    checado nem convertido."""
    flamengo_x_palmeiras = _partida(
        ID="1",
        rodata="1",
        data="30/03/2025",
        hora="16:00",
        mandante="Flamengo",
        visitante="Palmeiras",
        vencedor="Flamengo",
        # \xa0 no início: refined não corrige fato.
        arena="\xa0Maracana",
        mandante_Placar="2",
        visitante_Placar="1",
        # Dinheiro com centavos: DOUBLE não guardaria exato.
        arrecadacao="1234567.89",
    )
    return {
        "partidas": [
            flamengo_x_palmeiras,
            # Duplicata exata da partida 1: tem que sair.
            dict(flamengo_x_palmeiras),
            # Empate sem arrecadação: NULL continua NULL.
            _partida(
                ID="2",
                rodata="2",
                data="06/04/2025",
                mandante="Santos",
                visitante="Bahia",
                vencedor="-",
                mandante_Placar="0",
                visitante_Placar="0",
            ),
        ],
        "estatisticas": [
            # Posse com '%': vira 58.
            {
                "partida_id": "1",
                "rodata": "1",
                "clube": "Flamengo",
                "posse_de_bola": "58%",
            },
            # 'None' é o marcador de ausência: vira NULL, não erro.
            {
                "partida_id": "1",
                "rodata": "1",
                "clube": "Palmeiras",
                "posse_de_bola": "None",
            },
        ],
        "gols": [
            # Gol nos acréscimos: minuto 90, acrescimo 5.
            {
                "partida_id": "1",
                "rodata": "1",
                "clube": "Flamengo",
                "atleta": "Pedro",
                "minuto": "90+5",
            },
            # Gol no tempo normal: acrescimo NULL.
            {
                "partida_id": "1",
                "rodata": "1",
                "clube": "Flamengo",
                "atleta": "Pedro",
                "minuto": "81",
            },
            # Repetição exata do gol aos 81: evento, não duplicata; fica.
            {
                "partida_id": "1",
                "rodata": "1",
                "clube": "Flamengo",
                "atleta": "Pedro",
                "minuto": "81",
            },
        ],
        "cartoes": [
            {
                "partida_id": "1",
                "rodata": "1",
                "clube": "Palmeiras",
                "cartao": "Amarelo",
                "minuto": "45+2",
            },
        ],
    }


def _ambiente(tmp_path, monkeypatch, linhas=None, sem=()):
    banco = tmp_path / "teste.duckdb"
    monkeypatch.setattr(db, "_BANCO", banco)
    linhas = _linhas_validas() if linhas is None else linhas
    con = duckdb.connect(str(banco))
    con.execute("CREATE SCHEMA raw")
    for tabela, mapa in transformacao.MAPA.items():
        if tabela in sem:
            continue
        colunas = [o for o, _, _ in mapa]
        con.execute(
            f"CREATE TABLE raw.{tabela} ("
            + ", ".join(f'"{c}" VARCHAR' for c in colunas)
            + ")"
        )
        for linha in linhas.get(tabela, []):
            valores = [linha.get(c) for c in colunas]
            con.execute(
                f"INSERT INTO raw.{tabela} VALUES ("
                + ", ".join("?" for _ in colunas)
                + ")",
                valores,
            )
    con.close()
    return banco


def _consulta(banco, sql):
    con = duckdb.connect(str(banco))
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def _tabelas(banco, schema):
    return _consulta(
        banco,
        f"SELECT table_name FROM information_schema.tables WHERE table_schema = '{schema}'",
    )


def _foto(banco, schema):
    return {
        t: _consulta(banco, f"SELECT * FROM {schema}.{t} ORDER BY ALL")
        for (t,) in _tabelas(banco, schema)
    }


def test_rodata_vira_rodada_e_id_vira_partida_id(tmp_path, monkeypatch):
    banco = _ambiente(tmp_path, monkeypatch)
    transformacao.main()
    colunas = [
        c
        for (c,) in _consulta(
            banco,
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'refined' AND table_name = 'partidas' ORDER BY ordinal_position",
        )
    ]
    assert colunas[:2] == ["partida_id", "rodada"]
    assert "ID" not in colunas
    assert "rodata" not in colunas
    assert "placar_mandante" in colunas


def test_acrescimo_vem_logo_depois_de_minuto(tmp_path, monkeypatch):
    banco = _ambiente(tmp_path, monkeypatch)
    transformacao.main()
    colunas = [
        c
        for (c,) in _consulta(
            banco,
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'refined' AND table_name = 'gols' ORDER BY ordinal_position",
        )
    ]
    assert colunas == [
        "partida_id",
        "rodada",
        "clube",
        "atleta",
        "minuto",
        "acrescimo",
        "tipo",
    ]


def test_posse_com_percentual_vira_inteiro_e_none_vira_nulo(tmp_path, monkeypatch):
    banco = _ambiente(tmp_path, monkeypatch)
    transformacao.main()
    posse = _consulta(
        banco, "SELECT clube, posse_pct FROM refined.estatisticas ORDER BY clube"
    )
    assert posse == [("Flamengo", 58), ("Palmeiras", None)]


def test_minuto_com_acrescimo_vira_duas_colunas_e_sem_acrescimo_fica_nulo(
    tmp_path, monkeypatch
):
    banco = _ambiente(tmp_path, monkeypatch)
    transformacao.main()
    gols = _consulta(
        banco, "SELECT DISTINCT minuto, acrescimo FROM refined.gols ORDER BY minuto"
    )
    assert gols == [(81, None), (90, 5)]


def test_data_vira_date_e_hora_vira_time(tmp_path, monkeypatch):
    banco = _ambiente(tmp_path, monkeypatch)
    transformacao.main()
    tipos = dict(
        _consulta(
            banco,
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_schema = 'refined' AND table_name = 'partidas'",
        )
    )
    linha = _consulta(
        banco, "SELECT data, hora FROM refined.partidas WHERE partida_id = '1'"
    )
    assert tipos["data"] == "DATE"
    assert tipos["hora"] == "TIME"
    # 30/03 só existe como dia/mês: a leitura mês/dia daria erro.
    assert linha == [(datetime.date(2025, 3, 30), datetime.time(16, 0))]


def test_arrecadacao_vira_decimal_10_2_sem_perder_centavos(tmp_path, monkeypatch):
    banco = _ambiente(tmp_path, monkeypatch)
    transformacao.main()
    [(tipo,)] = _consulta(
        banco,
        "SELECT data_type FROM information_schema.columns "
        "WHERE table_schema = 'refined' AND table_name = 'partidas' "
        "AND column_name = 'arrecadacao'",
    )
    valores = _consulta(
        banco, "SELECT arrecadacao FROM refined.partidas ORDER BY partida_id"
    )
    assert tipo == "DECIMAL(10,2)"
    assert valores == [(Decimal("1234567.89"),), (None,)]


def test_duplicata_exata_em_partidas_sai(tmp_path, monkeypatch):
    banco = _ambiente(tmp_path, monkeypatch)
    transformacao.main()
    assert _consulta(banco, "SELECT partida_id FROM refined.partidas ORDER BY 1") == [
        ("1",),
        ("2",),
    ]


def test_linha_repetida_em_gols_fica(tmp_path, monkeypatch):
    banco = _ambiente(tmp_path, monkeypatch)
    transformacao.main()
    assert _consulta(banco, "SELECT count(*) FROM refined.gols WHERE minuto = 81") == [
        (2,)
    ]


def test_texto_e_empate_ficam_como_chegaram(tmp_path, monkeypatch):
    banco = _ambiente(tmp_path, monkeypatch)
    transformacao.main()
    linhas = _consulta(
        banco, "SELECT arena, vencedor FROM refined.partidas ORDER BY partida_id"
    )
    assert linhas == [("\xa0Maracana", "Flamengo"), (None, "-")]


def test_valor_fora_do_formato_encerra_sem_virar_nulo(tmp_path, monkeypatch):
    linhas = _linhas_validas()
    # Posse sem '%': fora do formato, não pode virar NULL calado.
    linhas["estatisticas"][0]["posse_de_bola"] = "58"
    banco = _ambiente(tmp_path, monkeypatch, linhas)
    with pytest.raises(SystemExit) as saida:
        transformacao.main()
    assert saida.value.code == 1
    assert _tabelas(banco, "refined") == []


def test_inteiro_com_casa_decimal_encerra_em_vez_de_arredondar(tmp_path, monkeypatch):
    linhas = _linhas_validas()
    # O DuckDB arredondaria '1.5' para 2 em silêncio; a regex barra antes.
    linhas["partidas"][2]["rodata"] = "1.5"
    banco = _ambiente(tmp_path, monkeypatch, linhas)
    with pytest.raises(SystemExit):
        transformacao.main()
    assert _tabelas(banco, "refined") == []


def test_data_no_formato_mas_inexistente_encerra(tmp_path, monkeypatch):
    linhas = _linhas_validas()
    # Passa na regex dd/mm/aaaa, mas 31 de fevereiro não existe.
    linhas["partidas"][2]["data"] = "31/02/2025"
    banco = _ambiente(tmp_path, monkeypatch, linhas)
    with pytest.raises(SystemExit):
        transformacao.main()
    assert _tabelas(banco, "refined") == []


def test_chave_repetida_com_conteudo_diferente_encerra(tmp_path, monkeypatch):
    linhas = _linhas_validas()
    # Mesma partida_id 1 com outro placar: não há como escolher uma.
    linhas["partidas"][1] = dict(linhas["partidas"][0], mandante_Placar="3")
    banco = _ambiente(tmp_path, monkeypatch, linhas)
    with pytest.raises(SystemExit):
        transformacao.main()
    assert _tabelas(banco, "refined") == []


def test_raw_nao_muda(tmp_path, monkeypatch):
    banco = _ambiente(tmp_path, monkeypatch)
    antes = _foto(banco, "raw")
    transformacao.main()
    assert _foto(banco, "raw") == antes


def test_rodar_duas_vezes_da_o_mesmo_refined(tmp_path, monkeypatch):
    banco = _ambiente(tmp_path, monkeypatch)
    transformacao.main()
    primeira = _foto(banco, "refined")
    transformacao.main()
    assert _foto(banco, "refined") == primeira


def test_tabela_faltando_em_raw_encerra(tmp_path, monkeypatch):
    banco = _ambiente(tmp_path, monkeypatch, sem=["cartoes"])
    with pytest.raises(SystemExit) as saida:
        transformacao.main()
    assert saida.value.code == 1
    assert _tabelas(banco, "refined") == []
