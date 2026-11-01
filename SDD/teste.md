CONTEXTO
Estou construindo um pipeline de dados em Python sobre o dataset público do
Campeonato Brasileiro de Futebol (Kaggle, Série A de 2003 a 2025). Trabalho
com spec-driven development: a spec abaixo é a fonte da verdade e o código é
consequência dela. Não acrescente requisito que não esteja escrito aqui.
Se algo estiver ambíguo, pergunte antes de escrever código.

STACK
- Python 3.13, uv, DuckDB
- pytest e pytest-cov, já instalados com uv add --dev

O QUE JÁ EXISTE (leia tudo antes de escrever qualquer teste)
pipeline/db.py, pipeline/ingestao.py, pipeline/transformacao.py,
pipeline/marts.py, painel.py, app.py e sql/marts/*.sql (14 arquivos).
Cada módulo tem a sua spec na docstring do topo, com critérios de aceite.
Cada .sql tem o grão e as regras nos comentários do topo.

ARTEFATOS A PRODUZIR
Pasta test/ na raiz, com um arquivo por módulo: test_db.py,
test_ingestao.py, test_transformacao.py, test_marts.py, test_painel.py.
Executável com:
  uv run pytest --cov
Configuração no pyproject.toml:
  [tool.pytest.ini_options]
  testpaths = ["test"]
  pythonpath = ["."]
  [tool.coverage.run]
  source = ["."]
  omit = ["test/*", "app.py", "ui.py", ".venv/*"]
  [tool.coverage.report]
  fail_under = 60
  show_missing = true

SPEC
1. META
   60% de coverage de linhas no TOTAL do código Python do projeto:
   pipeline/ e painel.py. A meta é do total, não de cada arquivo. Arquivo
   que nenhum teste importa conta como 0%, e é isso que o source = ["."]
   garante.
   Ficam fora da medição: app.py, a tela do Streamlit, conferida no
   navegador; e ui.py, que só abre a interface do DuckDB.
   Motivo: testar layout por coverage não prova nada.

2. NUNCA O BANCO NEM OS DADOS DO PROJETO
   Nenhum teste abre brasileirao.duckdb nem lê os arquivos de raw/.
   Cada teste usa tmp_path: um DuckDB novo dentro dele e, quando precisar
   de CSV, arquivos .csv.gz pequenos escritos pelo próprio teste. Para o
   código encontrar esses arquivos, use monkeypatch.setattr na constante
   de caminho do módulo (o banco em db.py e em painel.py, a pasta raw,
   a pasta sql/marts em marts.py) ou monkeypatch.chdir(tmp_path).
   Os testes dos marts podem ler os arquivos .sql reais de sql/marts/: o
   que não pode ser real é o dado.
   Motivo: o teste tem que rodar em qualquer máquina, sem o pipeline ter
   rodado, e não pode alterar o banco de ninguém.
   São testes unitários do código. Testes de qualidade sobre o dado real
   (chave única, domínio, totais que batem) ficam fora deste pedido.

3. DADO INVENTADO, RESULTADO DA REGRA
   Toda entrada é inventada pelo teste: poucas linhas, cada uma com um
   comentário dizendo por que está ali (gol aos 90+5, posse 'None', jogo
   em fevereiro, gol contra, empate, linha duplicada).
   O valor esperado sai da conta feita sobre essa entrada, nunca de um
   número medido no dado do Brasileirão (9.165, 23.474, 59.268, 10.762...).
   Motivo: o dado real muda a cada temporada; a regra não.

4. O QUE TESTAR
   Os critérios de aceite das docstrings são a lista de partida: cada
   critério que descreve uma regra vira pelo menos um teste. Em especial:
   - ingestão: o CSV vira tabela com as mesmas linhas, tudo VARCHAR; o
     texto 'None' continua texto e o campo vazio vira NULL; arquivo
     faltando encerra com SystemExit.
   - transformação: rodata vira rodada e ID vira partida_id; posse '58%'
     vira 58 e 'None' vira NULL; minuto '90+5' vira minuto 90 e acrescimo
     5, e '81' vira 81 com acrescimo NULL; data '30/03/2025' vira DATE;
     arrecadacao vira DECIMAL(10,2); duplicata exata em partidas sai e
     linha repetida em gols fica; valor fora do formato encerra com
     SystemExit, sem virar nulo; raw não muda.
   - marts (executor): arquivo sem prefixo NN_ para antes de executar;
     mart vazio encerra e deixa o schema marts como estava; arquivo
     apagado faz o mart sumir na execução seguinte; falta de tabela em
     refined encerra com SystemExit.
   - sql/marts, rodados sobre tabelas refined inventadas:
     01: jogo em fevereiro de 2021 conta na temporada 2020;
     02: gol contra fica fora do artilheiro;
     04: vitória vale 3, empate 1, derrota 0, e o mais pontuado é o 1.º;
     13: gol aos 90+3 vai para a faixa '90+', não para '76-90';
     14: atleta que marcou por dois clubes tem duas linhas, com os gols
         de cada clube.
   - painel: reais, pct e numero com entradas inventadas; ler() com um
     DuckDB inventado em tmp_path devolve um DataFrame por mart; clube fora
     do dicionário CLUBES recebe a sigla com as três primeiras letras e as
     cores padrão; cada função de gráfico devolve uma figura com tantos
     pontos quantas linhas tem o DataFrame inventado.
   Caminho de erro que encerra com sys.exit: pytest.raises(SystemExit).

5. ESTILO
   pytest puro: funções test_* com assert. Fixtures, só tmp_path e
   monkeypatch. DuckDB de verdade, nunca mock do banco.
   O nome do teste é a frase que ele prova:
     test_gol_contra_fica_fora_do_artilheiro
   Proibido: teste sem assert, skip, xfail, try/except em volta do assert,
   pytest.approx em dinheiro. Motivo: cada um sobe o coverage sem provar
   nada.

6. NÃO ALTERE O CÓDIGO DO PROJETO
   Nenhum arquivo muda fora de test/ e do pyproject.toml. Se uma parte só
   for testável mudando o código, não mude: liste na entrega, com o motivo.

CRITÉRIOS DE ACEITE
- uv run pytest --cov termina sem falha, com TOTAL de 60% ou mais.
- Com brasileirao.duckdb renomeado, o resultado é o mesmo.
- Rodar duas vezes seguidas imprime a mesma coisa.
- Uma busca por 9165, 23474 e 59268 dentro de test/ não encontra nada.
- git status mostra mudança só em test/ e no pyproject.toml.

ENTREGA
1. Os arquivos de teste.
2. A saída de uv run pytest --cov, com a tabela por arquivo.
3. As linhas que ficaram sem teste (coluna Missing) e por que não valeram
   o esforço agora.
4. Uma lista final do que você assumiu e que não estava na spec.