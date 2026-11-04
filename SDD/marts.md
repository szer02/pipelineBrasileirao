CONTEXTO
Estou construindo um pipeline de dados em Python sobre o dataset público do
Campeonato Brasileiro de Futebol (Kaggle, 2003-2025). Trabalho com
spec-driven development: a spec abaixo é a fonte da verdade e o código é
consequência dela. Não acrescente requisito que não esteja escrito aqui.
Se algo estiver ambíguo, pergunte antes de escrever código.

STACK
- Python 3.13, uv, DuckDB (brasileirao.duckdb na raiz do projeto)

O QUE JÁ EXISTE (use, não reimplemente)
pipeline/db.py: conectar(), criar_schema(con, nome)
O schema refined, com quatro tabelas (partidas, estatisticas, gols,
cartoes), criado por pipeline/transformacao.py.
A pasta sql/marts/, com arquivos NN_nome.sql. Cada arquivo tem um único
SELECT, que pode começar com comentários (--) e com WITH.

ARTEFATO A PRODUZIR
pipeline/marts.py, executável com:
  uv run python -m pipeline.marts

SPEC
1. ESCOPO
   Lê de refined, escreve no schema marts. Nunca escreve em raw nem em refined.
   O schema marts é apagado e recriado a cada execução (DROP SCHEMA IF
   EXISTS marts CASCADE). Motivo: um mart cujo arquivo foi apagado não pode
   continuar existindo no banco.

2. UM ARQUIVO, UMA TABELA
   Lê todos os sql/marts/*.sql em ordem alfabética, com encoding utf-8-sig.
   Motivo do utf-8-sig: o PowerShell 5.1 grava BOM com -Encoding utf8, e o
   BOM no início do arquivo quebraria a SQL.
   Nome da tabela = nome do arquivo sem a extensão e sem o prefixo numérico:
     sql/marts/01_gols_por_temporada.sql -> marts.gols_por_temporada
   Executa: CREATE TABLE marts.<nome> AS <conteúdo do arquivo>
   Tira espaços e um ponto e vírgula do final do conteúdo, e nada mais.
   O Python não altera, não monta e não completa a SQL.
   Motivo: a regra de negócio mora inteira no arquivo .sql.

3. SAÍDA NA TELA
   Uma linha por mart, com a contagem vinda do banco, milhar com ponto:
     ✓ marts.gols_por_temporada        23 linhas
   Linha final com o número de marts e o total de linhas.
   stdout reconfigurado para utf-8.
   (Atualizado por SDD/refatoracao.md: a saída é feita pelo logging de
   pipeline/log.py, com o mesmo texto; erro vai para o stderr. main() só
   encadeia uma função por etapa.)

4. ERRO
   Antes de tudo: se faltar qualquer uma das quatro tabelas em refined
   (partidas, estatisticas, gols, cartoes), lista quais, diz para rodar
   "uv run python -m pipeline.transformacao" e encerra com sys.exit(1).
   Se um .sql falhar: mostra o nome do arquivo e a mensagem do DuckDB,
   não executa os seguintes, sys.exit(1).
   Se um mart voltar com zero linhas: mostra o nome e encerra com
   sys.exit(1). Motivo: mart vazio é quase sempre um JOIN que não casou,
   e um painel vazio parece um campeonato sem jogos.
   Se sql/marts/ não tiver nenhum arquivo: avisa e sys.exit(1).
   Antes de executar qualquer SQL: arquivo sem prefixo NN_ ou dois
   arquivos que dão o mesmo nome de tabela -> lista quais e sys.exit(1).
   Tudo roda numa transação só: se qualquer passo falhar (inclusive o
   mart vazio), o schema marts volta a ser o da última execução que deu
   certo. Motivo: um schema pela metade quebra o painel sem avisar.

CRITÉRIOS DE ACEITE
- Com um arquivo sql/marts/00_teste.sql contendo "SELECT 1 AS x", cria
  marts.teste com 1 linha.
- Apagar o arquivo e rodar de novo faz marts.teste desaparecer.
- Um arquivo com erro de sintaxe para tudo, com o nome do arquivo na tela,
  e marts continua exatamente como estava antes da execução.
- Um arquivo teste.sql, sem prefixo, para antes de executar qualquer SQL.
- Rodar duas vezes seguidas imprime exatamente a mesma coisa.
- Com os 11 arquivos atuais de sql/marts/, a linha final mostra 11 marts
  e 2.190 linhas (23, 1.593, 1, 470, 12, 46, 6, 3, 20, 7 e 9, na ordem
  dos arquivos).

ENTREGA
1. A spec como docstring no topo do arquivo, com o motivo de cada regra.
2. O código, comentado só onde a decisão não é óbvia.
3. Uma lista final do que você assumiu e que não estava na spec.