CONTEXTO
Estou construindo um pipeline de dados em Python sobre o dataset público do
Campeonato Brasileiro de Futebol (Kaggle, Série A de 2003 a 2025). Trabalho
com spec-driven development: a spec abaixo é a fonte da verdade e o código é
consequência dela. Não acrescente requisito que não esteja escrito aqui.
Se algo estiver ambíguo, pergunte antes de escrever código.

STACK
- Python 3.13, uv, DuckDB (brasileirao.duckdb na raiz do projeto)
- streamlit e plotly (plotly.express ou plotly.graph_objects), já
  instalados com uv add

O QUE JÁ EXISTE (use, não reimplemente)
O schema marts, com catorze tabelas, criado por pipeline/marts.py:
  gols_por_temporada, artilheiros, mando_de_campo, classificacao,
  gols_por_partida, aproveitamento_por_clube, cartoes_por_posicao,
  posse_e_resultado, arrecadacao_pareto, partidas_por_dia_da_semana,
  titulos_por_clube, kpis, gols_por_minuto, artilheiros_por_clube.
Cada mart tem o grão e as regras na primeira linha do sql/marts/NN_nome.sql.

ARTEFATOS A PRODUZIR
painel.py, na raiz: leitura, formatação, identidade dos clubes e gráficos.
  Não importa streamlit.
app.py, na raiz: a página. Executável com:
  uv run streamlit run app.py
.streamlit/config.toml: o tema.

SPEC
1. LEITURA (painel.py)
   ler(marts) -> dict nome -> DataFrame. Para cada nome, só
   SELECT * FROM marts.<nome>. Nenhuma outra SQL.
   Conexão com duckdb.connect("brasileirao.duckdb", read_only=True), aberta
   e fechada dentro de ler(). Motivo: conexão aberta segura o arquivo, e o
   pipeline.marts não consegue gravar com o painel de pé.

2. NENHUM CÁLCULO
   Proibido em painel.py e app.py: groupby, sum, mean, count, merge, pivot,
   e qualquer conta entre colunas (inclusive saldo = gols_pro - gols_contra).
   Permitido: ordenar, filtrar linhas, head(n), renomear coluna, formatar
   texto e escolher cor.
   Motivo: número novo na tela exige um .sql novo em marts. Se faltar
   algum número, pare e diga qual mart está faltando.

3. TEMA E IDENTIDADE
   .streamlit/config.toml com tema escuro: base "dark", primaryColor
   "#FFDF00" (amarelo), backgroundColor "#0B1F14", secondaryBackgroundColor
   "#12301F", textColor "#F1F5F0".
   Nos gráficos: cor principal verde "#009C3B"; amarelo "#FFDF00" só no
   destaque que o título comenta (campeão, acréscimos, clube escolhido).
   Fundo dos gráficos transparente, para seguir o tema.
   Emblema do painel: um círculo verde com borda amarela e o texto "BR",
   feito em HTML/CSS. Nenhuma logo oficial, nenhum escudo de clube.
   Motivo: logos e escudos são marcas registradas, e o repositório é público.
   Identidade de cada clube: um dicionário CLUBES em painel.py, com os 46
   nomes exatamente como estão no dado ("Sao Paulo", "Gremio"...), e para
   cada um: nome de exibição com acento ("São Paulo", "Grêmio"), sigla
   (ex.: "SPFC") e duas cores (fundo e texto) das cores tradicionais do
   clube. Clube que não estiver no dicionário: nome como chegou, sigla com
   as três primeiras letras em maiúsculas, cores verde e branco.
   O "escudo" na tela é um bloco em HTML/CSS com as duas cores e a sigla.
   Os cartões são em HTML/CSS (st.markdown com unsafe_allow_html), não
   st.metric: rótulo pequeno em cima, número grande embaixo.

4. NAVEGAÇÃO
   st.set_page_config com layout="wide", page_title "Brasileirão em
   números" e initial_sidebar_state="collapsed".
   Barra lateral: st.selectbox "Escolha a visão", com "Visão geral" primeiro
   e depois os 46 clubes de aproveitamento_por_clube em ordem alfabética do
   nome de exibição. Padrão: "Visão geral". Embaixo, o botão "Recarregar
   dados" (item 8) e a linha "Fonte: Kaggle · Campeonato Brasileiro de
   Futebol".
   Motivo da barra recolhida: a entrada é a visão geral, com a tela inteira;
   quem quer um clube abre a barra.

5. VISÃO GERAL (app.py), de cima para baixo
   Cabeçalho: emblema + título "Brasileirão em números" + subtítulo
     "Série A · pontos corridos · <kpis.temporada_inicial> a
     <kpis.temporada_final>".
   Faixa de sete cartões, nesta ordem:
     Partidas (kpis.partidas)
     Gols (kpis.gols)
     Média de gols por partida (kpis.media_gols, 2 casas)
     Mandante vence · % das partidas (mando_de_campo.pct_vitorias_mandante,
       1 casa)
     Gols nos acréscimos · desde 2014 (kpis.pct_gols_acrescimo, 1 casa)
     Clubes (kpis.clubes)
     Arrecadação · só 2025 (kpis.arrecadacao_total, reais)
   Três abas (st.tabs): "Campeonato", "Temporada", "Jogadores".
   Aba Campeonato:
     Largura inteira: 01 · Média de gols por temporada (linha com
       marcadores, media_gols por temporada).
     Três colunas: 11 · Títulos por clube (barras horizontais, ordem do
       mart: posicao e depois ultimo_titulo, primeiro em cima; nome de
       exibição); 06 · Aproveitamento, top 10 (barras horizontais, maior em
       cima, rótulo "Mirassol · 1 temporada" com a coluna temporadas);
       13 · Gols por minuto (barras verticais na ordem da coluna ordem,
       faixas "45+" e "90+" em amarelo).
     Duas colunas: 08 · Posse e vitória (barras de pct_vitorias por
       situacao); 05 · Gols por partida (barras de pct_partidas por
       gols_na_partida).
   Aba Temporada:
     st.selectbox com as temporadas de gols_por_temporada, padrão a última.
     Pódio: três cartões lado a lado com as linhas de classificacao da
       temporada escolhida com posicao 1, 2 e 3 (ouro, prata, bronze), cada
       um com escudo, nome de exibição, pontos e "V-E-D".
     Tabela (st.dataframe) com a classificacao da temporada, ordenada por
       posicao, colunas renomeadas para o português da tela.
   Aba Jogadores:
     st.slider "Quantos artilheiros", de 5 a 20, padrão 10.
     02 · Artilheiros desde 2014: head(n) de artilheiros, barras
       horizontais, maior em cima; ao passar o mouse, clubes, gols_penalti
       e temporadas.

6. PÁGINA DO CLUBE (app.py), quando a barra lateral tem um clube escolhido
   Cabeçalho: escudo + nome de exibição + uma etiqueta com troféu por ano
     de título (titulos_por_clube.temporadas do clube). Sem linha em
     titulos_por_clube: "Sem títulos entre <temporada_inicial> e
     <temporada_final>".
   Cartões, duas faixas:
     Títulos (titulos_por_clube.titulos; 0 se o clube não tiver linha),
     Temporadas na Série A ("<temporadas> de <kpis.temporadas>"),
     Jogos, Aproveitamento (1 casa);
     Vitórias, Empates, Derrotas, Gols marcados, Gols sofridos
     (tudo de aproveitamento_por_clube).
   04 · Posição em cada temporada: só pontos, sem linha ligando, eixo
     vertical invertido (1.º no topo), eixo horizontal de
     kpis.temporada_inicial a kpis.temporada_final. Pontos com posicao 1
     em amarelo e maiores. Temporada sem linha do clube em classificacao
     fica vazia no gráfico, e a legenda diz "temporada sem ponto: o clube
     não estava na Série A". Motivo: completar as temporadas faltantes
     seria merge, e o vazio já mostra a ausência.
   Tabela das campanhas: as linhas de classificacao do clube, da temporada
     mais recente para a mais antiga.
   14 · Artilheiros pelo clube desde 2014: artilheiros_por_clube do clube,
     as 10 primeiras por posicao, barras horizontais na cor do clube.
     Sem linha do clube: st.info "Gols por jogador só existem a partir de
     2014, e este clube não jogou a Série A desde então."

7. FORMATO (painel.py), funções puras, sem streamlit e sem banco
   reais(valor, casas=2)  -> "R$ 518.065.218,68"
   pct(valor, casas=1)    -> "49,6%"
   numero(valor, casas=0) -> "23.474"
   Milhar com ponto, decimal com vírgula, sempre. Não use locale do sistema.
   Nos gráficos plotly, separators=",.".
   Motivo: o resultado não pode depender da máquina de quem roda.
   Uma função por gráfico, recebendo o DataFrame (já filtrado pelo app.py,
   quando for o caso) e devolvendo a figura plotly. Título com o número do
   mart ("01 · Média de gols por temporada"), eixo com unidade.
   width="stretch" (use_container_width está descontinuado).
   Motivo: as funções puras podem ser testadas sem subir o Streamlit, e um
   relatório HTML pode reaproveitá-las.

8. CACHE E ERRO
   Leitura com st.cache_data. O botão "Recarregar dados" limpa o cache.
   Sem brasileirao.duckdb, ou faltando qualquer um dos catorze marts:
   st.error dizendo quais e o comando "uv run python -m pipeline.marts",
   e st.stop().

CRITÉRIOS DE ACEITE
- A página abre na Visão geral, com a barra lateral recolhida.
- Subtítulo "Série A · pontos corridos · 2003 a 2025".
- Os sete cartões mostram: 9.165 · 23.474 · 2,56 · 49,6% · 10,5% · 46 ·
  R$ 518.065.218,68.
- Títulos com Flamengo, Palmeiras e Corinthians (4) em cima, nessa ordem.
- Gols por minuto com 8 barras, de "0-15" a "90+", e as duas de
  acréscimo em amarelo.
- Aba Temporada abre em 2025, com pódio Flamengo 79, Palmeiras 76 e
  Cruzeiro 70.
- Aba Jogadores abre com 10 barras e Gabriel Barbosa (107) em cima.
- Escolhendo São Paulo na barra lateral: títulos 2006, 2007 e 2008;
  23 de 23 temporadas; 894 jogos; 53,5%; 396 vitórias, 246 empates,
  252 derrotas; 1.259 gols marcados e 969 sofridos; Luciano da Rocha
  Neves (62) em cima nos artilheiros.
- Escolhendo Palmeiras: nenhum ponto em 2013 no gráfico de posição.
- Escolhendo Guarani: a mensagem de st.info no lugar dos artilheiros e
  "Sem títulos entre 2003 e 2025".
- Uma busca por "groupby", ".sum(", ".mean(" e "merge" em painel.py e
  app.py não encontra nada.
- Com o painel de pé, uv run python -m pipeline.marts roda sem erro de lock.

ENTREGA
1. A spec como docstring no topo de painel.py, com o motivo de cada regra.
2. O código, comentado só onde a decisão não é óbvia.
3. Uma lista final do que você assumiu e que não estava na spec.