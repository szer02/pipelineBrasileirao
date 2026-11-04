CONTEXTO
Estou construindo um pipeline de dados em Python sobre o dataset público
"Campeonato Brasileiro de Futebol" do Kaggle (Série A de 2003 a 2025, com
estatísticas, gols e cartões). Trabalho com spec-driven development: a spec
abaixo é a fonte da verdade e o código é consequência dela. Não acrescente
requisito que não esteja escrito aqui. Se algo estiver ambíguo, pergunte
antes de escrever código.

STACK
- Python 3.13, dependências gerenciadas com uv
- DuckDB, arquivo brasileirao.duckdb na raiz do projeto
- Nenhum orquestrador. Script executável pela linha de comando.

O QUE JÁ EXISTE (use, não reimplemente)
pipeline/db.py expõe:
  conectar()                       abre o brasileirao.duckdb, criando se faltar
  criar_schema(con, nome)          CREATE SCHEMA IF NOT EXISTS
  gravar(con, df, schema, tabela)  grava um DataFrame. NÃO usar aqui: a
                                   transformação é feita em SQL dentro do
                                   DuckDB, sem passar por pandas
pipeline/ingestao.py (etapa 1) já rodou. O schema raw tem quatro tabelas
(partidas, estatisticas, gols, cartoes), todas as colunas VARCHAR, só o
campo vazio como NULL (o texto 'None' entrou como texto).
Convenção do DuckDB 2.0 neste projeto: consumir cada resultado com
.complete() (ou fetchall) antes do próximo comando na conexão.

ARTEFATO A PRODUZIR
pipeline/transformacao.py, executável com:
  uv run python -m pipeline.transformacao

SPEC

1. ESCOPO
   Lê de raw, escreve no schema refined. Nunca escreve em raw.
   Entram as quatro tabelas: partidas, estatisticas, gols, cartoes.
   Nenhuma fica de fora.

2. NOMES
   Colunas em português, snake_case, com o mapa abaixo, completo e literal.
   Nenhuma coluna fora do mapa; nenhuma descartada. A única coluna nova é
   acrescimo (item 3), que sai da divisão de minuto.
   Motivo: é o vocabulário que vou digitar de memória nos JOINs da etapa 3,
   e o raw traz um erro de digitação (rodata) e maiúsculas soltas
   (mandante_Placar) que não quero carregar adiante.

   partidas
     ID -> partida_id                     rodata -> rodada
     data -> data                         hora -> hora
     mandante -> mandante                 visitante -> visitante
     formacao_mandante -> formacao_mandante
     formacao_visitante -> formacao_visitante
     tecnico_mandante -> tecnico_mandante
     tecnico_visitante -> tecnico_visitante
     vencedor -> vencedor                 arena -> arena
     mandante_Placar -> placar_mandante   visitante_Placar -> placar_visitante
     mandante_Estado -> uf_mandante       visitante_Estado -> uf_visitante
     arrecadacao -> arrecadacao
   estatisticas
     partida_id -> partida_id             rodata -> rodada
     clube -> clube                       chutes -> chutes
     chutes_no_alvo -> chutes_no_alvo     posse_de_bola -> posse_pct
     passes -> passes                     precisao_passes -> precisao_passes_pct
     faltas -> faltas                     cartao_amarelo -> cartao_amarelo
     cartao_vermelho -> cartao_vermelho   impedimentos -> impedimentos
     escanteios -> escanteios
   gols
     partida_id -> partida_id             rodata -> rodada
     clube -> clube                       atleta -> atleta
     minuto -> minuto, acrescimo          tipo_de_gol -> tipo
   cartoes
     partida_id -> partida_id             rodata -> rodada
     clube -> clube                       cartao -> cartao
     atleta -> atleta                     num_camisa -> num_camisa
     posicao -> posicao                   minuto -> minuto, acrescimo

3. TIPOS
   data: DATE, formato declarado '%d/%m/%Y'.
     Motivo: dia/mês/ano em 100% das 9.165 linhas. Sem formato declarado,
     a leitura pode trocar dia por mês em silêncio (03/04 vira 4 de março).
   hora: TIME, formato declarado '%H:%M'. Motivo: HH:MM em 100% das linhas.
     data e hora ficam separadas, como chegaram.
   arrecadacao: DECIMAL(10,2). Motivo: é dinheiro, e DOUBLE não representa
     centavos com exatidão. Em raw há no máximo 2 casas decimais e 7
     dígitos inteiros (maior valor 5.983.920,00).
   posse_pct e precisao_passes_pct: INTEGER, tirando o '%' do fim
     ('55%' -> 55). O texto 'None' vira NULL (item 6).
     Motivo: percentual é medida, entra em média; com '%' é texto.
   minuto (gols e cartoes): dividido em duas colunas INTEGER.
     '90+9' -> minuto 90, acrescimo 9
     '31'   -> minuto 31, acrescimo NULL
     Motivo: '90+9' não cabe em um número sem perder informação, e 99
     seria um minuto que não existe. Com duas colunas nada se perde, e o
     NULL em acrescimo quer dizer "fora dos acréscimos", sem ambiguidade.
     Em raw só existem os formatos N (27.424) e N+N (4.349), sempre com
     45 ou 90 antes do '+'.
   Contagens e medidas: INTEGER. São elas rodada, placar_mandante,
     placar_visitante, chutes, chutes_no_alvo, passes, faltas,
     cartao_amarelo, cartao_vermelho, impedimentos, escanteios, minuto
     e acrescimo.
   Todo o resto continua VARCHAR, inclusive partida_id e num_camisa.
     Motivo: são identificadores, nunca são somados. partida_id é o rótulo
     da partida e num_camisa é o rótulo do jogador (existe camisa 123 e
     700); nenhum dos dois entra em conta.
   A conversão é feita em SQL pelo DuckDB (strptime, CAST), disparada pelo
   Python. Motivo: o dado já está no banco; não há por que trazê-lo para a
   memória só para converter tipo.

4. CONVERSÃO QUE FALHA
   Para tudo. Use strptime e CAST, que estouram, e nunca try_strptime,
   TRY_CAST ou errors="coerce", que transformam falha em nulo.
   Antes de converter, cada coluna convertida passa por uma checagem de
   formato por regex (inteiro só com dígitos; percentual dígitos + '%';
   minuto N ou N+N; arrecadacao dígitos com ponto e até 2 casas; data
   dd/mm/aaaa; hora HH:MM). Valor fora do formato para tudo do mesmo jeito.
   Motivo: o DuckDB 2.0 arredonda em silêncio (CAST('1.5' AS INTEGER) dá
   2); a checagem é o que transforma esse arredondamento em erro.
   Ao falhar: diga tabela, coluna e um exemplo do valor que não converteu,
   e encerre com sys.exit(1).
   Motivo: um nulo fabricado pela conversão fica indistinguível de um nulo
   verdadeiro do dado, para sempre.

5. DUPLICATAS
   Chave de cada tabela:
     partidas (partida_id)
     estatisticas (partida_id, clube): uma linha por clube em cada partida
   Nessas duas: linha inteira repetida mantém uma e conta quantas saíram;
   chave repetida com conteúdo diferente para, mostra a chave e as linhas
   conflitantes, sys.exit(1). Não escolhe uma por conta própria.
   Motivo: escolher em silêncio é decidir sem dizer que decidiu.
   gols e cartoes não têm chave: a unidade é o evento, e dois eventos
   iguais podem existir de verdade (o mesmo atleta marcando duas vezes no
   mesmo minuto). Linha inteira repetida é contada e mostrada na tela,
   mas não sai.
   Motivo: apagar um gol repetido quebraria a igualdade, hoje exata, entre
   o arquivo de gols e o placar das partidas.

6. NULOS
   Nenhuma linha é apagada por ter nulo. Nenhum nulo é preenchido.
   Única conversão para nulo: o texto exato 'None' em posse_pct e
   precisao_passes_pct. Motivo: 'None' é o marcador de ausência do
   arquivo de origem, igual ao campo vazio na prática, mas não cabe em
   INTEGER. A saída na tela conta separadamente quantos nulos vieram de
   'None', para a decisão não sumir.
   Motivo da regra geral: o nulo aqui é informação. Formação e técnico só
   existem de 2014 em diante; arrecadação só existe em 2025; tipo de gol
   nulo é gol normal (nem pênalti nem contra). Preencher qualquer um
   desses inventa dado.
   Anomalias de negócio ficam como chegaram. refined não corrige fato;
   quem decide o que fazer com elas é a pergunta que o mart responde:
   - 10.750 linhas de estatisticas inteiramente zeradas (até 2013, toda a
     temporada 2024 e casos soltos): zero ali é "não coletado";
   - os cartões de estatisticas não batem com o arquivo cartoes;
   - 268 gols contra com crédito de clube ambíguo;
   - vencedor '-' para empate (2.421 partidas), mantido como texto;
   - 'Zagueira' (22) ao lado de 'Zagueiro' em posicao;
   - arena com espaço invisível (\xa0) no início em 5.077 partidas;
   - 1 partida em que a posse dos dois clubes não soma 100;
   - 1 partida de 2007 às 00:00;
   - jogos da temporada 2020 com data em 2021 (a temporada é decisão de
     mart, não coluna da refined).

7. SAÍDA NA TELA
   Uma linha por tabela, no formato:
     refined.partidas            9.165 -> 9.165 linhas  (0 duplicatas)
   Abaixo dela, indentadas, as colunas com nulo e a contagem:
       nulos mantidos: formacao_mandante 4.975, tecnico_mandante 4.610, ...
   Em estatisticas, uma linha a mais com os nulos vindos de 'None':
       'None' -> NULL: posse_pct 1.550, precisao_passes_pct 3.854
   Em gols e cartoes, "(N repetidas mantidas)" no lugar de duplicatas.
   As contagens vêm do banco, milhar separado por ponto. Linha final com o
   total. stdout reconfigurado para utf-8.
   (Atualizado por SDD/refatoracao.md: a saída é feita pelo logging de
   pipeline/log.py, com o mesmo texto; erro vai para o stderr. main() só
   encadeia uma função por etapa.)

REEXECUÇÃO E GRAVAÇÃO
   CREATE OR REPLACE TABLE, nunca acrescenta. Rodar dez vezes = rodar uma.
   Toda checagem (formato, conversão, chaves) roda antes de gravar
   qualquer tabela, e as quatro tabelas são gravadas numa transação só:
   tudo ou nada.
   Motivo: um refined pela metade, com tabelas de execuções diferentes,
   produz JOIN que não fecha sem erro nenhum.

ERRO
   Antes de transformar, verifica se as quatro tabelas de entrada existem
   em raw. Faltando qualquer uma: lista quais, diz para rodar
   "uv run python -m pipeline.ingestao" e encerra com sys.exit(1).

CRITÉRIOS DE ACEITE
- Quatro tabelas em refined; linhas que saem = linhas que entram
  (partidas 9.165, estatisticas 18.330, gols 10.820, cartoes 20.953).
  Total: 59.268. Com este dado, 0 duplicatas em todas.
- DESCRIBE refined.partidas mostra DATE em data, TIME em hora,
  DECIMAL(10,2) em arrecadacao, INTEGER em rodada e nos placares,
  VARCHAR em partida_id.
- Nulos depois = nulos antes, coluna por coluna:
  partidas: formacao_mandante 4.975, formacao_visitante 4.975,
    tecnico_mandante 4.610, tecnico_visitante 4.610, arrecadacao 8.785;
  gols: tipo 9.527; cartoes: atleta 6, num_camisa 386, posicao 1.198.
  Exceção documentada: posse_pct 10.762 (9.212 vazios + 1.550 'None') e
  precisao_passes_pct 13.066 (9.212 + 3.854).
- acrescimo preenchido em 1.140 gols e 3.209 cartões; minuto nunca nulo.
- sum(arrecadacao) = 518.065.218,68, centavo por centavo com raw.
- sum(placar_mandante + placar_visitante) = 23.474; em partidas de 2014
  em diante, a soma do placar é igual ao número de linhas de gols
  (10.820).
- sum(posse_pct) = 378.399.
- Rodar duas vezes seguidas imprime exatamente a mesma coisa.

ENTREGA, nesta ordem
1. A spec como docstring no topo do arquivo, dizendo por que cada regra
   existe, e não só o que ela manda fazer.
2. O código, com comentários apenas onde a decisão não é óbvia pelo código.
3. Uma lista final do que você assumiu e que não estava na spec. Se a lista
   não estiver vazia, é a minha spec que precisa melhorar.