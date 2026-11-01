"""Testes de pipeline/db.py, num DuckDB novo dentro de tmp_path."""

from pathlib import Path

import duckdb
import pandas as pd
import pytest

from pipeline import db


def _banco(tmp_path, monkeypatch) -> Path:
    caminho = tmp_path / "teste.duckdb"
    monkeypatch.setattr(db, "_BANCO", caminho)
    return caminho


def test_conectar_cria_o_banco_no_caminho_configurado(tmp_path, monkeypatch):
    caminho = _banco(tmp_path, monkeypatch)
    assert not caminho.exists()
    con = db.conectar()
    con.close()
    assert caminho.exists()


def test_pasta_raw_vem_da_localizacao_do_modulo_e_nao_do_diretorio_corrente(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    assert db.PASTA_RAW.is_absolute()
    assert db.PASTA_RAW == Path(db.__file__).resolve().parent.parent / "raw"


def test_criar_schema_pode_rodar_duas_vezes(tmp_path, monkeypatch):
    _banco(tmp_path, monkeypatch)
    con = db.conectar()
    db.criar_schema(con, "raw")
    db.criar_schema(con, "raw")
    schemas = con.execute(
        "SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'raw'"
    ).fetchall()
    con.close()
    assert schemas == [("raw",)]


def test_gravar_devolve_a_contagem_lida_do_banco(tmp_path, monkeypatch):
    _banco(tmp_path, monkeypatch)
    con = db.conectar()
    db.criar_schema(con, "raw")
    df = pd.DataFrame({"a": ["1", "2", "3"]}, dtype=str)
    n = db.gravar(con, df, "raw", "t")
    [(no_banco,)] = con.execute("SELECT count(*) FROM raw.t").fetchall()
    con.close()
    assert n == 3
    assert no_banco == 3


def test_gravar_mantem_texto_como_varchar_e_nulo_como_null(tmp_path, monkeypatch):
    _banco(tmp_path, monkeypatch)
    con = db.conectar()
    db.criar_schema(con, "raw")
    # "007" provaria uma conversão para número; None tem que chegar como NULL.
    df = pd.DataFrame({"camisa": ["007", None]}, dtype=str)
    db.gravar(con, df, "raw", "t")
    tipos = con.execute(
        "SELECT data_type FROM information_schema.columns WHERE table_name = 't'"
    ).fetchall()
    linhas = con.execute(
        "SELECT camisa FROM raw.t ORDER BY camisa NULLS LAST"
    ).fetchall()
    con.close()
    assert tipos == [("VARCHAR",)]
    assert linhas == [("007",), (None,)]


def test_gravar_duas_vezes_recria_a_tabela_em_vez_de_acrescentar(tmp_path, monkeypatch):
    _banco(tmp_path, monkeypatch)
    con = db.conectar()
    db.criar_schema(con, "raw")
    df = pd.DataFrame({"a": ["1", "2"]}, dtype=str)
    db.gravar(con, df, "raw", "t")
    n = db.gravar(con, df, "raw", "t")
    con.close()
    assert n == 2


def test_gravar_nao_deixa_view_registrada_na_conexao(tmp_path, monkeypatch):
    _banco(tmp_path, monkeypatch)
    con = db.conectar()
    db.criar_schema(con, "raw")
    db.gravar(con, pd.DataFrame({"a": ["1"]}, dtype=str), "raw", "t")
    with pytest.raises(duckdb.CatalogException):
        con.execute("SELECT * FROM _gravar_df").fetchall()
    con.close()
