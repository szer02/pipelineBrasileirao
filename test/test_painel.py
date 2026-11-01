"""Testes de painel.py: formato, leitura num DuckDB inventado em tmp_path,
identidade dos clubes, HTML e uma figura por gráfico."""

import duckdb
import pandas as pd
import pytest

import painel

# ---------------------------------------------------------------- formato


def test_numero_usa_ponto_no_milhar_e_virgula_no_decimal():
    assert painel.numero(1234567) == "1.234.567"
    assert painel.numero(2.5, 2) == "2,50"
    assert painel.numero(-1234.5, 1) == "-1.234,5"
    # Float vindo de HUGEINT: sem casas, sem ",0".
    assert painel.numero(79.0) == "79"


def test_pct_tem_uma_casa_por_padrao_e_simbolo_no_fim():
    assert painel.pct(49.56) == "49,6%"
    assert painel.pct(100) == "100,0%"
    assert painel.pct(7.25, 2) == "7,25%"


def test_reais_tem_prefixo_e_duas_casas_por_padrao():
    assert painel.reais(1234567.89) == "R$ 1.234.567,89"
    assert painel.reais(0.5) == "R$ 0,50"
    assert painel.reais(1000, 0) == "R$ 1.000"


# ---------------------------------------------------------------- leitura


def _banco(tmp_path, monkeypatch):
    banco = tmp_path / "teste.duckdb"
    monkeypatch.setattr(painel, "BANCO", banco)
    con = duckdb.connect(str(banco))
    con.execute("CREATE SCHEMA marts")
    # Dois marts inventados, com contagens diferentes para não se confundirem.
    con.execute(
        "CREATE TABLE marts.um AS SELECT * FROM (VALUES (1, 'a'), (2, 'b')) t(n, s)"
    )
    con.execute("CREATE TABLE marts.dois AS SELECT 10 AS n")
    con.close()
    return banco


def test_ler_devolve_um_dataframe_por_mart(tmp_path, monkeypatch):
    _banco(tmp_path, monkeypatch)
    dados = painel.ler(["um", "dois"])
    assert list(dados) == ["um", "dois"]
    assert dados["um"].to_dict("records") == [{"n": 1, "s": "a"}, {"n": 2, "s": "b"}]
    assert dados["dois"].to_dict("records") == [{"n": 10}]


def test_ler_fecha_a_conexao_e_libera_o_banco_para_escrita(tmp_path, monkeypatch):
    banco = _banco(tmp_path, monkeypatch)
    painel.ler(["um"])
    # Com a conexão read_only ainda aberta, esta escrita falharia.
    con = duckdb.connect(str(banco))
    con.execute("CREATE TABLE marts.tres AS SELECT 1 AS n")
    con.close()
    assert painel.ler(["tres"])["tres"].to_dict("records") == [{"n": 1}]


def test_ler_lista_os_marts_que_faltam(tmp_path, monkeypatch):
    _banco(tmp_path, monkeypatch)
    with pytest.raises(painel.MartsFaltando) as erro:
        painel.ler(["um", "nao_existe", "dois", "tambem_nao"])
    assert erro.value.faltando == ["nao_existe", "tambem_nao"]
    assert erro.value.banco_existe is True


def test_ler_sem_banco_avisa_todos_os_marts_e_nao_cria_o_arquivo(tmp_path, monkeypatch):
    banco = tmp_path / "nao_existe.duckdb"
    monkeypatch.setattr(painel, "BANCO", banco)
    with pytest.raises(painel.MartsFaltando) as erro:
        painel.ler(["um", "dois"])
    assert erro.value.faltando == ["um", "dois"]
    assert erro.value.banco_existe is False
    assert not banco.exists()


# ---------------------------------------------------------------- identidade


def test_clube_fora_do_dicionario_recebe_tres_letras_e_cores_padrao():
    assert painel.clube("Novo Hamburgo") == (
        "Novo Hamburgo",
        "NOV",
        painel.VERDE,
        "#FFFFFF",
    )


def test_clube_do_dicionario_tem_nome_com_acento_e_sigla():
    nome, sigla, _, _ = painel.clube("Sao Paulo")
    assert nome == "São Paulo"
    assert sigla == "SPFC"


def test_ordem_alfabetica_ignora_acento():
    clubes = ["Sport", "Sao Paulo", "Santos", "Avai", "America-MG"]
    ordenados = sorted(clubes, key=painel.ordem_alfabetica)
    assert ordenados == ["America-MG", "Avai", "Santos", "Sao Paulo", "Sport"]


def test_lista_de_clubes_vira_nomes_de_exibicao():
    assert painel.nomes_exibicao("Gremio, Sao Paulo, Novo Hamburgo") == (
        "Grêmio, São Paulo, Novo Hamburgo"
    )


# ---------------------------------------------------------------- HTML


def test_escudo_tem_a_sigla_e_as_duas_cores_do_clube():
    _, sigla, fundo, texto = painel.clube("Flamengo")
    bloco = painel.escudo("Flamengo")
    assert f">{sigla}<" in bloco
    assert f"background:{fundo}" in bloco
    assert f"color:{texto}" in bloco


def test_cartoes_tem_um_bloco_por_item_com_texto_escapado():
    bloco = painel.cartoes([("Gols", "10"), ("A < B", "1")])
    assert bloco.count('class="br-cartao"') == 2
    assert "A &lt; B" in bloco
    assert "A < B" not in bloco


def test_etiquetas_tem_uma_por_ano_de_titulo():
    bloco = painel.etiquetas_titulos("2006, 2007, 2008")
    assert bloco.count("br-etiqueta") == 3
    assert "🏆 2007" in bloco


def test_cabecalho_junta_simbolo_titulo_e_linha_de_baixo():
    bloco = painel.cabecalho(painel.emblema(), "Título", painel.subtitulo("sub"))
    assert ">BR<" in bloco
    assert "<h1>Título</h1>" in bloco
    assert ">sub<" in bloco


def test_cartao_do_podio_mostra_nome_pontos_e_v_e_d():
    linha = pd.Series(
        {
            "posicao": 1,
            "clube": "Gremio",
            "pontos": 79.0,
            "vitorias": 23.0,
            "empates": 10.0,
            "derrotas": 5.0,
        }
    )
    bloco = painel.cartao_podio(linha)
    assert "Grêmio" in bloco
    assert "79 pts" in bloco
    assert "V-E-D 23-10-5" in bloco
    assert "ouro" in bloco


def test_tabela_de_classificacao_renomeia_esconde_coluna_e_mostra_inteiros():
    df = pd.DataFrame(
        {
            "temporada": [2024, 2024],
            "posicao": [1, 2],
            "clube": ["Gremio", "Novo Hamburgo"],
            # HUGEINT chega como float.
            "pontos": [70.0, 65.0],
        }
    )
    tabela = painel.tabela_classificacao(df, esconder="temporada")
    assert list(tabela.columns) == ["Posição", "Clube", "Pontos"]
    assert tabela["Clube"].tolist() == ["Grêmio", "Novo Hamburgo"]
    assert tabela["Pontos"].dtype == "int64"
    assert tabela["Pontos"].tolist() == [70, 65]


# ---------------------------------------------------------------- gráficos


def _pontos(fig):
    return len(fig.data[0].x)


def test_grafico_01_tem_um_ponto_por_temporada():
    df = pd.DataFrame(
        {
            "temporada": [2023, 2024, 2025],
            "partidas": [380, 380, 380],
            "gols": [900, 950, 1000],
            "media_gols": [2.37, 2.5, 2.63],
        }
    )
    fig = painel.grafico_media_gols(df)
    assert _pontos(fig) == 3
    assert fig.layout.title.text.startswith("01 · ")


def test_todo_grafico_usa_separador_brasileiro_e_fundo_transparente():
    df = pd.DataFrame(
        {"gols_na_partida": [0, 1], "partidas": [10, 30], "pct_partidas": [25.0, 75.0]}
    )
    fig = painel.grafico_gols_por_partida(df)
    assert fig.layout.separators == ",."
    assert fig.layout.paper_bgcolor == "rgba(0,0,0,0)"
    assert fig.layout.plot_bgcolor == "rgba(0,0,0,0)"
    assert _pontos(fig) == 2


def test_grafico_11_tem_uma_barra_por_clube_campeao():
    df = pd.DataFrame(
        {
            "clube": ["Flamengo", "Gremio"],
            "titulos": [2, 1],
            "temporadas": ["2019, 2020", "1996"],
            "ultimo_titulo": [2020, 1996],
            "posicao": [1, 2],
        }
    )
    fig = painel.grafico_titulos(df)
    assert len(fig.data[0].y) == 2
    assert list(fig.data[0].y) == ["Flamengo", "Grêmio"]


def test_grafico_06_rotula_temporada_no_singular_e_no_plural():
    df = pd.DataFrame(
        {
            "clube": ["Mirassol", "Sao Paulo"],
            "temporadas": [1, 3],
            "jogos": [38, 114],
            "pontos": [67, 180],
            "aproveitamento_pct": [58.8, 52.6],
        }
    )
    fig = painel.grafico_aproveitamento(df)
    assert list(fig.data[0].y) == ["Mirassol · 1 temporada", "São Paulo · 3 temporadas"]


def test_grafico_13_pinta_so_os_acrescimos_de_amarelo():
    df = pd.DataFrame(
        {
            "ordem": [1, 4, 8],
            "faixa": ["0-15", "45+", "90+"],
            "gols": [10, 2, 3],
            "pct_gols": [66.7, 13.3, 20.0],
        }
    )
    fig = painel.grafico_gols_por_minuto(df)
    assert _pontos(fig) == 3
    assert list(fig.data[0].marker.color) == [
        painel.VERDE,
        painel.AMARELO,
        painel.AMARELO,
    ]


def test_grafico_08_tem_uma_barra_por_situacao_de_posse():
    df = pd.DataFrame(
        {
            "situacao": ["igual", "mais_posse", "menos_posse"],
            "jogos": [2, 10, 10],
            "pct_vitorias": [50.0, 40.0, 30.0],
        }
    )
    fig = painel.grafico_posse(df)
    assert list(fig.data[0].x) == ["Posse igual", "Mais posse", "Menos posse"]


def test_grafico_02_tem_uma_barra_por_artilheiro():
    df = pd.DataFrame(
        {
            "atleta": ["A", "B", "C", "D", "E"],
            "gols": [9, 8, 7, 6, 5],
            "gols_penalti": [1, 0, 0, 2, 0],
            "temporadas": [3, 2, 1, 1, 4],
            "clubes": ["Gremio", "Santos", "Bahia, Sport", "Vasco", "Ceara"],
        }
    )
    fig = painel.grafico_artilheiros(df)
    assert len(fig.data[0].y) == 5


def test_grafico_04_tem_um_ponto_por_temporada_e_campeao_em_amarelo():
    # Sem 2013: a temporada ausente não vira ponto.
    df = pd.DataFrame(
        {"temporada": [2012, 2014], "posicao": [18, 1], "pontos": [34, 80]}
    )
    fig = painel.grafico_posicao(df, 2003, 2025)
    assert _pontos(fig) == 2
    assert list(fig.data[0].marker.color) == [painel.VERDE, painel.AMARELO]
    assert list(fig.layout.xaxis.range) == [2003, 2025]
    assert fig.data[0].mode == "markers"


def test_grafico_14_usa_a_cor_do_clube():
    df = pd.DataFrame(
        {
            "atleta": ["Fred", "Cano"],
            "gols": [20, 15],
            "gols_penalti": [3, 2],
            "temporadas": [4, 3],
        }
    )
    fig = painel.grafico_artilheiros_clube(df, "Fluminense")
    _, _, fundo, texto = painel.clube("Fluminense")
    assert len(fig.data[0].y) == 2
    assert fig.data[0].marker.color == fundo
    assert fig.data[0].marker.line.color == texto
