"""Testes de pipeline/ingestao.py, com .csv.gz pequenos escritos em tmp_path."""

import gzip

import duckdb
import pytest

from pipeline import db, ingestao

PARTIDAS = (
    "ID,rodata,data,arena,mandante_Placar,vencedor\n"
    # \xa0 no início de arena: não pode ser aparado.
    "1,1,30/03/2025,\xa0Maracana,2,Flamengo\n"
    # arena vazia: único caso que vira NULL; '-' de empate fica como texto.
    "2,1,31/03/2025,,1,-\n"
)
ESTATISTICAS = (
    "partida_id,clube,posse_de_bola\n"
    # '58%' continua texto, com o '%'.
    "1,Flamengo,58%\n"
    # 'None' é o marcador do arquivo de origem: tem que continuar texto.
    "1,Palmeiras,None\n"
)
# '90+9' não pode virar número nesta etapa.
GOLS = "partida_id,clube,minuto\n1,Flamengo,90+9\n"
# '07' com zero à esquerda: a inferência leria 7.
CARTOES = "partida_id,clube,num_camisa\n1,Palmeiras,07\n"

ARQUIVOS = {
    "campeonato-brasileiro-full.csv.gz": PARTIDAS,
    "campeonato-brasileiro-estatisticas-full.csv.gz": ESTATISTICAS,
    "campeonato-brasileiro-gols.csv.gz": GOLS,
    "campeonato-brasileiro-cartoes.csv.gz": CARTOES,
}


def _ambiente(tmp_path, monkeypatch, sem=()):
    pasta = tmp_path / "raw"
    pasta.mkdir()
    for nome, texto in ARQUIVOS.items():
        if nome not in sem:
            with gzip.open(pasta / nome, "wt", encoding="utf-8", newline="") as f:
                f.write(texto)
    # Arquivo fora do mapa: tem que ser ignorado.
    (pasta / "Legenda.txt").write_text("documentação", encoding="utf-8")
    banco = tmp_path / "teste.duckdb"
    monkeypatch.setattr(ingestao, "PASTA_RAW", pasta)
    monkeypatch.setattr(db, "_BANCO", banco)
    return banco


def _consulta(banco, sql):
    con = duckdb.connect(str(banco))
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def test_cada_csv_vira_tabela_com_as_mesmas_linhas(tmp_path, monkeypatch):
    banco = _ambiente(tmp_path, monkeypatch)
    ingestao.main()
    contagens = _consulta(
        banco,
        "SELECT 'partidas', count(*) FROM raw.partidas UNION ALL "
        "SELECT 'estatisticas', count(*) FROM raw.estatisticas UNION ALL "
        "SELECT 'gols', count(*) FROM raw.gols UNION ALL "
        "SELECT 'cartoes', count(*) FROM raw.cartoes",
    )
    assert dict(contagens) == {
        "partidas": 2,
        "estatisticas": 2,
        "gols": 1,
        "cartoes": 1,
    }


def test_toda_coluna_entra_como_varchar(tmp_path, monkeypatch):
    banco = _ambiente(tmp_path, monkeypatch)
    ingestao.main()
    tipos = _consulta(
        banco,
        "SELECT DISTINCT data_type FROM information_schema.columns WHERE table_schema = 'raw'",
    )
    assert tipos == [("VARCHAR",)]


def test_texto_none_continua_texto_e_campo_vazio_vira_nulo(tmp_path, monkeypatch):
    banco = _ambiente(tmp_path, monkeypatch)
    ingestao.main()
    posse = _consulta(
        banco, "SELECT clube, posse_de_bola FROM raw.estatisticas ORDER BY clube"
    )
    arena = _consulta(banco, "SELECT arena FROM raw.partidas WHERE ID = '2'")
    assert posse == [("Flamengo", "58%"), ("Palmeiras", "None")]
    assert arena == [(None,)]


def test_nomes_de_coluna_e_valores_ficam_como_chegaram(tmp_path, monkeypatch):
    banco = _ambiente(tmp_path, monkeypatch)
    ingestao.main()
    colunas = _consulta(
        banco,
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = 'raw' AND table_name = 'partidas' ORDER BY ordinal_position",
    )
    partida = _consulta(banco, "SELECT arena, vencedor FROM raw.partidas ORDER BY ID")
    minuto = _consulta(banco, "SELECT minuto FROM raw.gols")
    camisa = _consulta(banco, "SELECT num_camisa FROM raw.cartoes")
    assert [c for (c,) in colunas] == [
        "ID",
        "rodata",
        "data",
        "arena",
        "mandante_Placar",
        "vencedor",
    ]
    assert partida == [("\xa0Maracana", "Flamengo"), (None, "-")]
    assert minuto == [("90+9",)]
    assert camisa == [("07",)]


def test_arquivo_fora_do_mapa_e_ignorado(tmp_path, monkeypatch):
    banco = _ambiente(tmp_path, monkeypatch)
    ingestao.main()
    tabelas = _consulta(
        banco,
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = 'raw' ORDER BY table_name",
    )
    assert tabelas == [("cartoes",), ("estatisticas",), ("gols",), ("partidas",)]


def test_rodar_duas_vezes_recria_as_tabelas_em_vez_de_acrescentar(
    tmp_path, monkeypatch
):
    banco = _ambiente(tmp_path, monkeypatch)
    ingestao.main()
    ingestao.main()
    assert _consulta(banco, "SELECT count(*) FROM raw.partidas") == [(2,)]


def test_arquivo_faltando_encerra_sem_criar_o_banco(tmp_path, monkeypatch):
    banco = _ambiente(tmp_path, monkeypatch, sem=["campeonato-brasileiro-gols.csv.gz"])
    with pytest.raises(SystemExit) as saida:
        ingestao.main()
    assert saida.value.code == 1
    assert not banco.exists()
