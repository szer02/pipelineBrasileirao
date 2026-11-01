"""Página do painel "Brasileirão em números".

Execução:
    uv run streamlit run app.py

A spec está na docstring de painel.py. Aqui só se escolhe o que vai para a
tela; leitura, formato, cores e gráficos vêm de painel.py, e todo número vem
pronto de um mart.
"""

import streamlit as st

import painel

VISAO_GERAL = "Visão geral"

st.set_page_config(
    page_title="Brasileirão em números",
    layout="wide",
    initial_sidebar_state="collapsed",
)
st.markdown(painel.CSS, unsafe_allow_html=True)


@st.cache_data
def carregar():
    return painel.ler(painel.MARTS)


def html(bloco: str) -> None:
    st.markdown(bloco, unsafe_allow_html=True)


def grafico(fig) -> None:
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


try:
    dados = carregar()
except painel.MartsFaltando as erro:
    if erro.banco_existe:
        st.error(
            "Faltam estes marts no brasileirao.duckdb: "
            + ", ".join(f"marts.{n}" for n in erro.faltando)
            + ".\n\nRode antes: `uv run python -m pipeline.marts`"
        )
    else:
        st.error(
            "O arquivo brasileirao.duckdb não foi encontrado, então faltam os "
            f"{len(erro.faltando)} marts.\n\nRode antes: `uv run python -m pipeline.marts`"
        )
    st.stop()

kpis = dados["kpis"].iloc[0]
inicial, final = int(kpis["temporada_inicial"]), int(kpis["temporada_final"])
aproveitamento = dados["aproveitamento_por_clube"]
classificacao = dados["classificacao"]

with st.sidebar:
    clubes = sorted(aproveitamento["clube"], key=painel.ordem_alfabetica)
    visao = st.selectbox(
        "Escolha a visão",
        [VISAO_GERAL, *clubes],
        format_func=lambda v: v if v == VISAO_GERAL else painel.nome_exibicao(v),
    )
    if st.button("Recarregar dados"):
        st.cache_data.clear()
        st.rerun()
    st.caption("Fonte: Kaggle · Campeonato Brasileiro de Futebol")


def visao_geral() -> None:
    html(
        painel.cabecalho(
            painel.emblema(),
            "Brasileirão em números",
            painel.subtitulo(f"Série A · pontos corridos · {inicial} a {final}"),
        )
    )
    mando = dados["mando_de_campo"].iloc[0]
    html(
        painel.cartoes(
            [
                ("Partidas", painel.numero(kpis["partidas"])),
                ("Gols", painel.numero(kpis["gols"])),
                ("Média de gols por partida", painel.numero(kpis["media_gols"], 2)),
                (
                    "Mandante vence · % das partidas",
                    painel.pct(mando["pct_vitorias_mandante"]),
                ),
                (
                    "Gols nos acréscimos · desde 2014",
                    painel.pct(kpis["pct_gols_acrescimo"]),
                ),
                ("Clubes", painel.numero(kpis["clubes"])),
                ("Arrecadação · só 2025", painel.reais(kpis["arrecadacao_total"])),
            ]
        )
    )

    aba_campeonato, aba_temporada, aba_jogadores = st.tabs(
        ["Campeonato", "Temporada", "Jogadores"]
    )

    with aba_campeonato:
        grafico(painel.grafico_media_gols(dados["gols_por_temporada"]))
        c1, c2, c3 = st.columns(3)
        with c1:
            titulos = dados["titulos_por_clube"].sort_values(
                ["posicao", "ultimo_titulo"], ascending=[True, False]
            )
            grafico(painel.grafico_titulos(titulos))
        with c2:
            top10 = aproveitamento.sort_values(
                ["aproveitamento_pct", "clube"], ascending=[False, True]
            ).head(10)
            grafico(painel.grafico_aproveitamento(top10))
        with c3:
            grafico(painel.grafico_gols_por_minuto(dados["gols_por_minuto"]))
        c1, c2 = st.columns(2)
        with c1:
            grafico(painel.grafico_posse(dados["posse_e_resultado"]))
        with c2:
            grafico(painel.grafico_gols_por_partida(dados["gols_por_partida"]))

    with aba_temporada:
        temporadas = sorted(dados["gols_por_temporada"]["temporada"])
        temporada = st.selectbox("Temporada", temporadas, index=len(temporadas) - 1)
        da_temporada = classificacao[
            classificacao["temporada"] == temporada
        ].sort_values(["posicao", "clube"])
        podio = da_temporada[da_temporada["posicao"].isin([1, 2, 3])]
        for coluna, (_, linha) in zip(st.columns(len(podio)), podio.iterrows()):
            with coluna:
                html(painel.cartao_podio(linha))
        st.markdown(f"#### Classificação {temporada}")
        st.dataframe(
            painel.tabela_classificacao(da_temporada, esconder="temporada"),
            width="stretch",
            hide_index=True,
        )

    with aba_jogadores:
        n = st.slider("Quantos artilheiros", min_value=5, max_value=20, value=10)
        artilheiros = dados["artilheiros"].sort_values(
            ["gols", "atleta"], ascending=[False, True]
        )
        grafico(painel.grafico_artilheiros(artilheiros.head(n)))


def pagina_do_clube(nome: str) -> None:
    linha = aproveitamento[aproveitamento["clube"] == nome].iloc[0]
    titulos = dados["titulos_por_clube"]
    titulos = titulos[titulos["clube"] == nome]
    if titulos.empty:
        abaixo = painel.subtitulo(f"Sem títulos entre {inicial} e {final}")
        n_titulos = 0
    else:
        abaixo = painel.etiquetas_titulos(titulos.iloc[0]["temporadas"])
        n_titulos = titulos.iloc[0]["titulos"]
    html(painel.cabecalho(painel.escudo(nome, 72), painel.nome_exibicao(nome), abaixo))

    html(
        painel.cartoes(
            [
                ("Títulos", painel.numero(n_titulos)),
                (
                    "Temporadas na Série A",
                    f"{painel.numero(linha['temporadas'])} de {painel.numero(kpis['temporadas'])}",
                ),
                ("Jogos", painel.numero(linha["jogos"])),
                ("Aproveitamento", painel.pct(linha["aproveitamento_pct"])),
            ]
        )
    )
    html(
        painel.cartoes(
            [
                ("Vitórias", painel.numero(linha["vitorias"])),
                ("Empates", painel.numero(linha["empates"])),
                ("Derrotas", painel.numero(linha["derrotas"])),
                ("Gols marcados", painel.numero(linha["gols_pro"])),
                ("Gols sofridos", painel.numero(linha["gols_contra"])),
            ]
        )
    )

    campanhas = classificacao[classificacao["clube"] == nome]
    grafico(painel.grafico_posicao(campanhas, inicial, final))

    st.markdown("#### Campanhas")
    st.dataframe(
        painel.tabela_classificacao(
            campanhas.sort_values("temporada", ascending=False), esconder="clube"
        ),
        width="stretch",
        hide_index=True,
    )

    artilheiros = dados["artilheiros_por_clube"]
    artilheiros = (
        artilheiros[artilheiros["clube"] == nome]
        .sort_values(["posicao", "atleta"])
        .head(10)
    )
    if artilheiros.empty:
        st.info(
            "Gols por jogador só existem a partir de 2014, e este clube não jogou "
            "a Série A desde então."
        )
    else:
        grafico(painel.grafico_artilheiros_clube(artilheiros, nome))


if visao == VISAO_GERAL:
    visao_geral()
else:
    pagina_do_clube(visao)
