"""Etapa 4, parte sem Streamlit: leitura dos marts, formato, identidade dos
clubes e gráficos do painel "Brasileirão em números".

A página é app.py (uv run streamlit run app.py); o tema, .streamlit/config.toml.
Este módulo não importa streamlit.

1. LEITURA
   ler(marts) -> dict nome -> DataFrame. Para cada nome, só
   SELECT * FROM marts.<nome>. Nenhuma outra SQL.
   Conexão com duckdb.connect(<brasileirao.duckdb>, read_only=True), aberta e
   fechada dentro de ler().
   Por quê: conexão aberta segura o arquivo, e o pipeline.marts não consegue
   gravar com o painel de pé.

2. NENHUM CÁLCULO
   Proibido aqui e em app.py: agrupar, somar, tirar média, contar, juntar
   DataFrames, pivotar, e qualquer conta entre colunas (inclusive
   saldo = gols_pro - gols_contra). Os nomes dos métodos do pandas ficam de
   fora deste texto de propósito: a busca por eles nos dois arquivos é
   critério de aceite e tem que voltar vazia.
   Permitido: ordenar, filtrar linhas, head(n), renomear coluna, formatar
   texto e escolher cor.
   Por quê: número novo na tela exige um .sql novo em marts; a regra de
   negócio mora inteira em sql/marts/, onde tem grão e motivo escritos.

3. TEMA E IDENTIDADE
   .streamlit/config.toml com tema escuro: base "dark", primaryColor
   "#FFDF00", backgroundColor "#0B1F14", secondaryBackgroundColor "#12301F",
   textColor "#F1F5F0".
   Nos gráficos: cor principal verde "#009C3B"; amarelo "#FFDF00" só no
   destaque que o título comenta. Fundo dos gráficos transparente.
   Por quê: o amarelo só funciona como destaque se for raro; o fundo
   transparente faz o gráfico seguir o tema em vez de virar um retângulo.
   Emblema do painel: círculo verde com borda amarela e o texto "BR", em
   HTML/CSS. Nenhuma logo oficial, nenhum escudo de clube.
   Por quê: logos e escudos são marcas registradas, e o repositório é
   público.
   CLUBES: os 46 nomes exatamente como estão no dado, cada um com nome de
   exibição com acento, sigla e duas cores tradicionais (fundo e texto).
   Clube fora do dicionário: nome como chegou, sigla com as três primeiras
   letras em maiúsculas, verde e branco.
   Por quê: o dado não tem acento; a tela tem. E um clube novo no dado não
   pode derrubar o painel.
   O "escudo" é um bloco HTML/CSS com as duas cores e a sigla. Os cartões
   são HTML/CSS, não st.metric: rótulo pequeno em cima, número grande
   embaixo.
   Por quê: st.metric não aceita o formato brasileiro de número nem as
   cores do tema.

4. NAVEGAÇÃO (app.py)
   Página wide, título "Brasileirão em números", barra lateral recolhida,
   com o seletor "Escolha a visão" ("Visão geral" e os 46 clubes de
   aproveitamento_por_clube em ordem alfabética do nome de exibição), o
   botão "Recarregar dados" e a fonte.
   Por quê da barra recolhida: a entrada é a visão geral, com a tela
   inteira; quem quer um clube abre a barra.

5. VISÃO GERAL e 6. PÁGINA DO CLUBE (app.py)
   Montadas só com os marts lidos aqui e as funções abaixo. Na posição em
   cada temporada, temporada sem linha do clube fica vazia no gráfico.
   Por quê: completar as temporadas faltantes seria juntar tabelas, e o vazio já
   mostra a ausência.

7. FORMATO
   reais(valor, casas=2)  -> "R$ 518.065.218,68"
   pct(valor, casas=1)    -> "49,6%"
   numero(valor, casas=0) -> "23.474"
   Milhar com ponto, decimal com vírgula, sempre, sem locale do sistema.
   Nos gráficos, separators=",.".
   Por quê: o resultado não pode depender da máquina de quem roda.
   Uma função por gráfico, recebendo o DataFrame (já filtrado pelo app.py,
   quando for o caso) e devolvendo a figura plotly. Título com o número do
   mart, eixo com unidade.
   Por quê: as funções puras podem ser testadas sem subir o Streamlit, e um
   relatório HTML pode reaproveitá-las.

8. CACHE E ERRO (app.py)
   Leitura com st.cache_data; "Recarregar dados" limpa o cache. Sem o banco,
   ou faltando qualquer um dos catorze marts: st.error dizendo quais e o
   comando "uv run python -m pipeline.marts", e st.stop().
   Por quê: sem o cache, cada clique releria o banco; sem o erro explícito,
   um mart faltando apareceria como traceback do DuckDB.
"""

import html
import unicodedata
from pathlib import Path

import duckdb
import pandas as pd
import plotly.graph_objects as go

# Resolvido a partir deste arquivo, pelo mesmo motivo do D1 de pipeline/db.py:
# rodar de outra pasta não pode procurar o banco no lugar errado.
BANCO = Path(__file__).resolve().parent / "brasileirao.duckdb"

MARTS = (
    "gols_por_temporada",
    "artilheiros",
    "mando_de_campo",
    "classificacao",
    "gols_por_partida",
    "aproveitamento_por_clube",
    "cartoes_por_posicao",
    "posse_e_resultado",
    "arrecadacao_pareto",
    "partidas_por_dia_da_semana",
    "titulos_por_clube",
    "kpis",
    "gols_por_minuto",
    "artilheiros_por_clube",
)

VERDE = "#009C3B"
AMARELO = "#FFDF00"
TEXTO = "#F1F5F0"
FUNDO_CARTAO = "#12301F"
GRADE = "rgba(241, 245, 240, 0.12)"

# nome no dado -> (nome de exibição, sigla, cor de fundo, cor do texto)
CLUBES = {
    "America-MG": ("América-MG", "AME", "#00843D", "#FFFFFF"),
    "America-RN": ("América-RN", "ARN", "#C8102E", "#FFFFFF"),
    "Athletico-PR": ("Athletico-PR", "CAP", "#C8102E", "#000000"),
    "Atletico-GO": ("Atlético-GO", "ACG", "#E30613", "#000000"),
    "Atletico-MG": ("Atlético-MG", "CAM", "#000000", "#FFFFFF"),
    "Avai": ("Avaí", "AVA", "#0057A8", "#FFFFFF"),
    "Bahia": ("Bahia", "BAH", "#0055A4", "#FFFFFF"),
    "Barueri": ("Barueri", "GRB", "#003DA5", "#FFD100"),
    "Botafogo-RJ": ("Botafogo", "BOT", "#000000", "#FFFFFF"),
    "Bragantino": ("Bragantino", "RBB", "#FFFFFF", "#D7001E"),
    "Brasiliense": ("Brasiliense", "BRA", "#FFE000", "#00843D"),
    "CSA": ("CSA", "CSA", "#003DA5", "#FFFFFF"),
    "Ceara": ("Ceará", "CEA", "#000000", "#FFFFFF"),
    "Chapecoense": ("Chapecoense", "CHA", "#00843D", "#FFFFFF"),
    "Corinthians": ("Corinthians", "COR", "#000000", "#FFFFFF"),
    "Coritiba": ("Coritiba", "CFC", "#00563F", "#FFFFFF"),
    "Criciuma": ("Criciúma", "CRI", "#FFD200", "#000000"),
    "Cruzeiro": ("Cruzeiro", "CRU", "#003399", "#FFFFFF"),
    "Cuiaba": ("Cuiabá", "CUI", "#FFD700", "#00703C"),
    "Figueirense": ("Figueirense", "FIG", "#000000", "#FFFFFF"),
    "Flamengo": ("Flamengo", "FLA", "#C8102E", "#000000"),
    "Fluminense": ("Fluminense", "FLU", "#870A28", "#FFFFFF"),
    "Fortaleza": ("Fortaleza", "FOR", "#004A9F", "#FFFFFF"),
    "Goias": ("Goiás", "GOI", "#006633", "#FFFFFF"),
    "Gremio": ("Grêmio", "GRE", "#0D80BF", "#FFFFFF"),
    "Gremio Prudente": ("Grêmio Prudente", "GPR", "#003DA5", "#FFFFFF"),
    "Guarani": ("Guarani", "GUA", "#007A33", "#FFFFFF"),
    "Internacional": ("Internacional", "INT", "#E30613", "#FFFFFF"),
    "Ipatinga": ("Ipatinga", "IPA", "#0047AB", "#FFFFFF"),
    "Joinville": ("Joinville", "JEC", "#E30613", "#FFFFFF"),
    "Juventude": ("Juventude", "JUV", "#007A33", "#FFFFFF"),
    "Mirassol": ("Mirassol", "MIR", "#FFDD00", "#00843D"),
    "Nautico": ("Náutico", "NAU", "#D50032", "#FFFFFF"),
    "Palmeiras": ("Palmeiras", "PAL", "#006437", "#FFFFFF"),
    "Parana": ("Paraná", "PAR", "#003DA5", "#FFFFFF"),
    "Paysandu": ("Paysandu", "PAY", "#3FA9F5", "#FFFFFF"),
    "Ponte Preta": ("Ponte Preta", "PON", "#000000", "#FFFFFF"),
    "Portuguesa": ("Portuguesa", "POR", "#E30613", "#FFFFFF"),
    "Santa Cruz": ("Santa Cruz", "SCZ", "#000000", "#E30613"),
    "Santo Andre": ("Santo André", "STA", "#0047AB", "#FFFFFF"),
    "Santos": ("Santos", "SAN", "#FFFFFF", "#000000"),
    "Sao Caetano": ("São Caetano", "SCA", "#0047AB", "#FFFFFF"),
    "Sao Paulo": ("São Paulo", "SPFC", "#FFFFFF", "#E30613"),
    "Sport": ("Sport", "SPT", "#D50032", "#000000"),
    "Vasco": ("Vasco", "VAS", "#000000", "#FFFFFF"),
    "Vitoria": ("Vitória", "VIT", "#E30613", "#000000"),
}

COLUNAS_TELA = {
    "temporada": "Temporada",
    "posicao": "Posição",
    "clube": "Clube",
    "pontos": "Pontos",
    "jogos": "Jogos",
    "vitorias": "Vitórias",
    "empates": "Empates",
    "derrotas": "Derrotas",
    "gols_pro": "Gols pró",
    "gols_contra": "Gols contra",
    "saldo": "Saldo",
}

SITUACOES_POSSE = {
    "mais_posse": "Mais posse",
    "igual": "Posse igual",
    "menos_posse": "Menos posse",
}


# ---------------------------------------------------------------- leitura


class MartsFaltando(Exception):
    """Banco ausente (faltando = todos) ou marts que não existem nele."""

    def __init__(self, faltando: list[str], banco_existe: bool):
        super().__init__(", ".join(faltando))
        self.faltando = faltando
        self.banco_existe = banco_existe


def ler(marts) -> dict[str, pd.DataFrame]:
    # Sem o arquivo, o connect read_only falharia com mensagem do DuckDB; a
    # checagem antes deixa o app dizer o que rodar.
    if not BANCO.exists():
        raise MartsFaltando(list(marts), banco_existe=False)
    dados, faltando = {}, []
    con = duckdb.connect(str(BANCO), read_only=True)
    try:
        for nome in marts:
            try:
                dados[nome] = con.execute(f'SELECT * FROM marts."{nome}"').df()
            except duckdb.CatalogException:
                faltando.append(nome)
    finally:
        con.close()
    if faltando:
        raise MartsFaltando(faltando, banco_existe=True)
    return dados


# ---------------------------------------------------------------- formato


def numero(valor, casas=0) -> str:
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "_").replace(".", ",").replace("_", ".")


def pct(valor, casas=1) -> str:
    return f"{numero(valor, casas)}%"


def reais(valor, casas=2) -> str:
    return f"R$ {numero(valor, casas)}"


# ---------------------------------------------------------------- identidade


def clube(nome: str) -> tuple[str, str, str, str]:
    """(nome de exibição, sigla, fundo, texto), com o padrão para clube novo."""
    return CLUBES.get(nome, (nome, nome[:3].upper(), VERDE, "#FFFFFF"))


def nome_exibicao(nome: str) -> str:
    return clube(nome)[0]


def ordem_alfabetica(nome: str) -> str:
    # Sem tirar o acento, "São Paulo" iria para depois de "Sport" ('ã' > 'p').
    sem_acento = unicodedata.normalize("NFKD", nome_exibicao(nome))
    return "".join(c for c in sem_acento if not unicodedata.combining(c)).casefold()


def nomes_exibicao(lista: str) -> str:
    """'Gremio, Sao Paulo' -> 'Grêmio, São Paulo' (coluna clubes do mart 02)."""
    return ", ".join(nome_exibicao(n) for n in lista.split(", "))


# ---------------------------------------------------------------- HTML

CSS = f"""
<style>
.br-cabecalho {{display:flex; align-items:center; gap:16px; margin:4px 0 12px;}}
.br-cabecalho h1 {{margin:0; padding:0; font-size:2.1rem;}}
.br-sub {{opacity:.75; font-size:.95rem;}}
.br-emblema {{width:56px; height:56px; border-radius:50%; background:{VERDE};
  border:4px solid {AMARELO}; color:{AMARELO}; display:flex; align-items:center;
  justify-content:center; font-weight:900; font-size:1.25rem; flex:none;}}
.br-escudo {{display:flex; align-items:center; justify-content:center;
  border-radius:10px 10px 50% 50% / 10px 10px 40% 40%; font-weight:900;
  border:3px solid; flex:none; letter-spacing:.02em;}}
.br-cartoes {{display:grid; grid-template-columns:repeat(auto-fit, minmax(150px, 1fr));
  gap:12px; margin:8px 0 16px;}}
.br-cartao {{background:{FUNDO_CARTAO}; border:1px solid rgba(255,223,0,.18);
  border-radius:10px; padding:12px 14px; container-type:inline-size;}}
.br-rotulo {{font-size:.78rem; opacity:.75; line-height:1.25;}}
.br-valor {{font-size:1.7rem; font-weight:700; line-height:1.3; white-space:nowrap;}}
/* Dentro do cartão, o número acompanha a largura dele: com a barra lateral
   aberta, "R$ 518.065.218,68" passava da borda. 11cqi = 11% da largura do
   cartão, o que cabe nos 17 caracteres do maior valor. */
.br-cartao .br-valor {{font-size:clamp(1rem, 11cqi, 1.7rem);}}
.br-podio {{background:{FUNDO_CARTAO}; border-radius:10px; padding:14px;
  border-top:5px solid; display:flex; align-items:center; gap:14px;}}
.br-etiqueta {{display:inline-block; background:{FUNDO_CARTAO}; color:{AMARELO};
  border:1px solid {AMARELO}; border-radius:999px; padding:2px 10px;
  margin:4px 6px 0 0; font-size:.85rem;}}
</style>
"""

MEDALHAS = {
    1: ("1.º · ouro", "#FFDF00"),
    2: ("2.º · prata", "#C0C7C2"),
    3: ("3.º · bronze", "#CD7F32"),
}


def emblema() -> str:
    return '<div class="br-emblema">BR</div>'


def escudo(nome: str, tamanho: int = 56) -> str:
    _, sigla, fundo, texto = clube(nome)
    fonte = tamanho // 3 if len(sigla) <= 3 else tamanho // 4
    return (
        f'<div class="br-escudo" style="width:{tamanho}px; height:{tamanho}px; '
        f'background:{fundo}; color:{texto}; border-color:{texto}; font-size:{fonte}px;">'
        f"{html.escape(sigla)}</div>"
    )


def cabecalho(simbolo: str, titulo: str, abaixo: str) -> str:
    """Bloco com emblema ou escudo à esquerda, título e uma linha HTML embaixo."""
    return (
        f'<div class="br-cabecalho">{simbolo}<div><h1>{html.escape(titulo)}</h1>'
        f"{abaixo}</div></div>"
    )


def subtitulo(texto: str) -> str:
    return f'<div class="br-sub">{html.escape(texto)}</div>'


def etiquetas_titulos(temporadas: str) -> str:
    """'2006, 2007, 2008' -> uma etiqueta com troféu por ano."""
    return "".join(
        f'<span class="br-etiqueta">🏆 {html.escape(ano)}</span>'
        for ano in temporadas.split(", ")
    )


def cartoes(itens: list[tuple[str, str]]) -> str:
    """[(rótulo, valor já formatado)] -> faixa de cartões."""
    blocos = "".join(
        f'<div class="br-cartao"><div class="br-rotulo">{html.escape(r)}</div>'
        f'<div class="br-valor">{html.escape(v)}</div></div>'
        for r, v in itens
    )
    return f'<div class="br-cartoes">{blocos}</div>'


def cartao_podio(linha: pd.Series) -> str:
    """Uma linha de classificacao com posicao 1, 2 ou 3."""
    medalha, cor = MEDALHAS[int(linha["posicao"])]
    ved = "-".join(numero(linha[c]) for c in ("vitorias", "empates", "derrotas"))
    return (
        f'<div class="br-podio" style="border-top-color:{cor};">{escudo(linha["clube"])}'
        f'<div><div class="br-rotulo" style="color:{cor};">{medalha}</div>'
        f'<div style="font-weight:700; font-size:1.15rem;">'
        f"{html.escape(nome_exibicao(linha['clube']))}</div>"
        f'<div class="br-valor">{numero(linha["pontos"])} pts</div>'
        f'<div class="br-rotulo">V-E-D {ved}</div></div></div>'
    )


# ---------------------------------------------------------------- tabelas


def tabela_classificacao(df: pd.DataFrame, esconder: str) -> pd.DataFrame:
    """Classificação para st.dataframe: sem a coluna repetida na tela
    (temporada ou clube), clube com acento, colunas em português."""
    tabela = df.drop(columns=[esconder])
    if "clube" in tabela:
        tabela["clube"] = tabela["clube"].map(nome_exibicao)
    # HUGEINT chega do DuckDB como float; a tabela mostraria "79.0".
    inteiras = [c for c in tabela.columns if c != "clube"]
    tabela[inteiras] = tabela[inteiras].astype("int64")
    return tabela.rename(columns=COLUNAS_TELA)


# ---------------------------------------------------------------- gráficos


def _layout(
    fig: go.Figure, titulo: str, eixo_x: str, eixo_y: str, altura=380
) -> go.Figure:
    fig.update_layout(
        title={"text": titulo, "font": {"size": 16}},
        separators=",.",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": TEXTO},
        height=altura,
        margin={"l": 10, "r": 10, "t": 60, "b": 10},
        showlegend=False,
    )
    fig.update_xaxes(title_text=eixo_x, gridcolor=GRADE, zeroline=False)
    fig.update_yaxes(title_text=eixo_y, gridcolor=GRADE, zeroline=False)
    return fig


def _barras_horizontais(fig: go.Figure) -> go.Figure:
    # O plotly desenha a primeira categoria embaixo; invertido, a primeira
    # linha do DataFrame (já na ordem certa) fica em cima.
    fig.update_yaxes(autorange="reversed", gridcolor="rgba(0,0,0,0)")
    return fig


def grafico_media_gols(df: pd.DataFrame) -> go.Figure:
    """Mart 01, gols_por_temporada."""
    fig = go.Figure(
        go.Scatter(
            x=df["temporada"],
            y=df["media_gols"],
            mode="lines+markers",
            line={"color": VERDE, "width": 3},
            marker={"color": VERDE, "size": 8},
            customdata=df[["partidas", "gols"]],
            hovertemplate="%{x}<br>%{y:.2f} gols por partida"
            "<br>%{customdata[1]:,.0f} gols em %{customdata[0]:,.0f} partidas<extra></extra>",
        )
    )
    fig.update_xaxes(dtick=1, tickangle=-45)
    return _layout(
        fig, "01 · Média de gols por temporada", "temporada", "gols por partida"
    )


def grafico_titulos(df: pd.DataFrame) -> go.Figure:
    """Mart 11, titulos_por_clube, na ordem do mart."""
    fig = go.Figure(
        go.Bar(
            x=df["titulos"],
            y=df["clube"].map(nome_exibicao),
            orientation="h",
            marker_color=VERDE,
            text=df["titulos"],
            textposition="outside",
            customdata=df["temporadas"],
            hovertemplate="%{y}: %{x} títulos<br>%{customdata}<extra></extra>",
        )
    )
    fig.update_xaxes(dtick=1)
    return _barras_horizontais(_layout(fig, "11 · Títulos por clube", "títulos", ""))


def grafico_aproveitamento(df: pd.DataFrame) -> go.Figure:
    """Mart 06, aproveitamento_por_clube, já cortado no top 10 pelo app.py."""
    rotulos = [
        f"{nome_exibicao(c)} · {t} temporada{'' if t == 1 else 's'}"
        for c, t in zip(df["clube"], df["temporadas"])
    ]
    fig = go.Figure(
        go.Bar(
            x=df["aproveitamento_pct"],
            y=rotulos,
            orientation="h",
            marker_color=VERDE,
            text=[pct(v) for v in df["aproveitamento_pct"]],
            textposition="inside",
            customdata=df[["jogos", "pontos"]],
            hovertemplate="%{y}<br>%{x:.1f}% de aproveitamento"
            "<br>%{customdata[1]:,.0f} pontos em %{customdata[0]:,.0f} jogos<extra></extra>",
        )
    )
    return _barras_horizontais(
        _layout(fig, "06 · Aproveitamento, top 10", "% dos pontos disputados", "")
    )


def grafico_gols_por_minuto(df: pd.DataFrame) -> go.Figure:
    """Mart 13, gols_por_minuto, na ordem da coluna ordem; acréscimos em amarelo."""
    df = df.sort_values("ordem")
    cores = [AMARELO if f in ("45+", "90+") else VERDE for f in df["faixa"]]
    fig = go.Figure(
        go.Bar(
            x=df["faixa"],
            y=df["gols"],
            marker_color=cores,
            customdata=df["pct_gols"],
            hovertemplate="minuto %{x}<br>%{y:,.0f} gols (%{customdata:.1f}%)<extra></extra>",
        )
    )
    fig.update_xaxes(type="category")
    return _layout(
        fig, "13 · Gols por minuto · acréscimos em amarelo", "minuto do jogo", "gols"
    )


def grafico_posse(df: pd.DataFrame) -> go.Figure:
    """Mart 08, posse_e_resultado."""
    fig = go.Figure(
        go.Bar(
            x=df["situacao"].map(SITUACOES_POSSE),
            y=df["pct_vitorias"],
            marker_color=VERDE,
            text=[pct(v) for v in df["pct_vitorias"]],
            textposition="outside",
            customdata=df["jogos"],
            hovertemplate="%{x}<br>%{y:.1f}% de vitórias em %{customdata:,.0f} jogos<extra></extra>",
        )
    )
    return _layout(
        fig,
        "08 · Posse e vitória",
        "posse de bola em relação ao adversário",
        "% de vitórias",
    )


def grafico_gols_por_partida(df: pd.DataFrame) -> go.Figure:
    """Mart 05, gols_por_partida."""
    fig = go.Figure(
        go.Bar(
            x=df["gols_na_partida"],
            y=df["pct_partidas"],
            marker_color=VERDE,
            customdata=df["partidas"],
            hovertemplate="%{x} gols<br>%{y:.2f}% das partidas (%{customdata:,.0f})<extra></extra>",
        )
    )
    fig.update_xaxes(dtick=1)
    return _layout(fig, "05 · Gols por partida", "gols na partida", "% das partidas")


def grafico_artilheiros(df: pd.DataFrame) -> go.Figure:
    """Mart 02, artilheiros, já cortado com head(n) pelo app.py."""
    fig = go.Figure(
        go.Bar(
            x=df["gols"],
            y=df["atleta"],
            orientation="h",
            marker_color=VERDE,
            text=df["gols"],
            textposition="inside",
            customdata=list(
                zip(
                    df["clubes"].map(nomes_exibicao),
                    df["gols_penalti"],
                    df["temporadas"],
                )
            ),
            hovertemplate="<b>%{y}</b>: %{x} gols<br>clubes: %{customdata[0]}"
            "<br>de pênalti: %{customdata[1]}<br>temporadas: %{customdata[2]}<extra></extra>",
        )
    )
    altura = max(380, 34 * len(df))
    return _barras_horizontais(
        _layout(fig, "02 · Artilheiros desde 2014", "gols", "", altura=altura)
    )


def grafico_posicao(df: pd.DataFrame, inicial: int, final: int) -> go.Figure:
    """Mart 04, classificacao, só as linhas do clube. Temporada sem linha fica
    vazia: nada é completado."""
    campeao = df["posicao"] == 1
    fig = go.Figure(
        go.Scatter(
            x=df["temporada"],
            y=df["posicao"],
            mode="markers",
            marker={
                "color": [AMARELO if c else VERDE for c in campeao],
                "size": [18 if c else 11 for c in campeao],
                "line": {"color": TEXTO, "width": 1},
            },
            cliponaxis=False,
            customdata=df["pontos"],
            hovertemplate="%{x}: %{y}.º lugar, %{customdata:,.0f} pontos<extra></extra>",
        )
    )
    fig.update_layout(
        title_subtitle_text="temporada sem ponto: o clube não estava na Série A · campeão em amarelo"
    )
    # Eixo fixo de inicial a final: é o que deixa a ausência visível.
    fig.update_xaxes(range=[inicial, final], dtick=1, tickangle=-45)
    fig.update_yaxes(autorange="reversed", tickformat="d")
    fig = _layout(
        fig, "04 · Posição em cada temporada", "temporada", "posição (1.º no topo)"
    )
    fig.update_layout(margin={"t": 80})
    return fig


def grafico_artilheiros_clube(df: pd.DataFrame, nome: str) -> go.Figure:
    """Mart 14, artilheiros_por_clube, já filtrado e cortado pelo app.py."""
    _, _, fundo, texto = clube(nome)
    fig = go.Figure(
        go.Bar(
            x=df["gols"],
            y=df["atleta"],
            orientation="h",
            # A borda na cor do texto mantém visível um clube de fundo preto
            # sobre o tema escuro.
            marker={"color": fundo, "line": {"color": texto, "width": 2}},
            text=df["gols"],
            textposition="outside",
            customdata=df[["gols_penalti", "temporadas"]],
            hovertemplate="<b>%{y}</b>: %{x} gols<br>de pênalti: %{customdata[0]}"
            "<br>temporadas: %{customdata[1]}<extra></extra>",
        )
    )
    return _barras_horizontais(
        _layout(fig, "14 · Artilheiros pelo clube desde 2014", "gols pelo clube", "")
    )
