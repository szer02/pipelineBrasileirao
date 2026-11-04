CONTEXTO
Estou construindo um pipeline de dados em Python sobre o dataset público
"Campeonato Brasileiro de Futebol" do Kaggle (partidas da Série A de 2003 a
2025, com estatísticas, gols e cartões). Trabalho com spec-driven
development: a spec abaixo é a fonte da verdade e o código é consequência
dela. Não acrescente requisito que não esteja escrito aqui. Se algo estiver
ambíguo, pergunte antes de escrever código.

STACK
- Python 3.13, dependências gerenciadas com uv
- pandas para ler os arquivos
- DuckDB como banco, arquivo brasileirao.duckdb na raiz do projeto
- Nenhum orquestrador. Script executável pela linha de comando.

O QUE JÁ EXISTE
Só a pasta raw/ com os quatro .csv.gz, um Legenda.txt e o pyproject.toml.
Nenhum código ainda.

ARTEFATOS A PRODUZIR, nesta ordem
1. pipeline/db.py, o módulo de conexão que todas as etapas vão importar
   (spec própria logo abaixo; é a primeira coisa a existir)
2. pipeline/ingestao.py, executável com:
     uv run python -m pipeline.ingestao
3. ui.py, na raiz do projeto, executável com:
     uv run python ui.py
   (spec própria no fim deste prompt; ui.py e ingestao.py não se importam)

SPEC DO pipeline/db.py (primeiro artefato)
Expõe exatamente isto, com estes nomes:
  PASTA_RAW                          Path da pasta raw/ com os quatro .csv.gz
  conectar()                         abre o brasileirao.duckdb, criando se faltar
  criar_schema(con, nome)            CREATE SCHEMA IF NOT EXISTS
  gravar(con, df, schema, tabela)    grava e devolve a contagem lida do banco

D1. CAMINHOS
    PASTA_RAW e o brasileirao.duckdb são resolvidos a partir da localização
    do próprio db.py (a pasta acima de pipeline/), nunca do diretório
    corrente.
    Motivo: rodar o script de outra pasta não pode criar um
    brasileirao.duckdb vazio no lugar errado, que parece ingestão quebrada.
D2. TRÊS FUNÇÕES E UMA CONSTANTE, NADA MAIS
    db.py não lê CSV, não conhece nome de tabela, não imprime nada e não
    converte tipo. Quem decide tudo isso é cada etapa.
    Motivo: as etapas seguintes importam este arquivo. Regra de negócio
    escondida aqui vale para todas as etapas sem aparecer em nenhuma spec.
D3. gravar
    Recria a tabela (CREATE OR REPLACE TABLE schema.tabela) com as colunas
    e os tipos do DataFrame, sem alterar nada: coluna str vira VARCHAR,
    nulo continua NULL. Não deixa view ou tabela temporária para trás.
    Devolve SELECT count(*) da tabela recém-gravada, lido do banco.
    Motivo: a contagem que aparece na tela tem que ser a do que foi
    gravado, não a do que estava na memória.
D4. CONEXÃO
    conectar() devolve a conexão aberta; quem chama é quem fecha.
    db.py não guarda conexão global.

CRITÉRIOS DE ACEITE (db.py)
- Importar pipeline.db não abre banco nem cria arquivo nenhum.
- conectar() chamado de dentro de outra pasta cria o brasileirao.duckdb na
  raiz do projeto, e não na pasta corrente.
- gravar() com um DataFrame de 3 linhas devolve 3, e rodar duas vezes
  continua devolvendo 3.

SPEC DA INGESTÃO (segundo artefato)

1. ESCOPO E NOMES
   Schema de destino: raw
   Mapa arquivo -> tabela, completo e literal:
     campeonato-brasileiro-full.csv.gz               -> partidas
     campeonato-brasileiro-estatisticas-full.csv.gz  -> estatisticas
     campeonato-brasileiro-gols.csv.gz               -> gols
     campeonato-brasileiro-cartoes.csv.gz            -> cartoes
   Os nomes vão para o português, curtos, porque é o vocabulário que vou
   digitar de memória num JOIN nas próximas etapas.
   raw/Legenda.txt fica na pasta e não é ingerido: é documentação, não
   dado. A ingestão lê só os quatro arquivos do mapa, pelo nome, e ignora
   qualquer outro arquivo da pasta.

2. PROIBIÇÕES (a regra central desta etapa)
   Nenhuma conversão de tipo. Nenhuma linha descartada ou deduplicada.
   Nenhum nome de coluna alterado: rodata, mandante_Placar, partida_id
   ficam exatamente como no cabeçalho do arquivo, inclusive o erro de
   digitação e as maiúsculas, mesmo divergindo do Legenda.txt.
   Nenhum valor corrigido, preenchido, aparado ou normalizado: o espaço
   invisível (\xa0) no início de arena, o "-" de empate em vencedor, o
   "90+9" em minuto e o "55%" em posse_de_bola entram como chegaram.
   Data continua texto, nulo continua nulo.
   Motivo: a fronteira entre "o dado que chegou" e "o dado que eu decidi"
   precisa existir em algum lugar, e esse lugar é a passagem de raw para
   refined, na etapa 2. Se a correção acontecer aqui, a fronteira some.

3. REEXECUÇÃO
   Rodar dez vezes tem que dar o mesmo resultado que rodar uma: a tabela é
   recriada (CREATE OR REPLACE), nunca acrescentada. É o que me deixa errar
   sem medo.

4. LEITURA DO ARQUIVO
   encoding declarado como utf-8, nunca adivinhado.
   Os .csv.gz são lidos direto, sem descompactar.
   Só o campo vazio vira nulo. Nenhum outro texto é tratado como nulo:
   desligue a lista padrão de nulos do pandas (keep_default_na=False,
   na_values=[""]).
   Motivo: por padrão o pandas transforma em nulo textos como "None", "NA"
   e "null". Em estatisticas, 1.550 linhas de posse_de_bola e 3.854 de
   precisao_passes trazem o texto "None", que é diferente do campo vazio.
   Com o padrão do pandas, esse texto viraria nulo calado e a etapa 2
   nunca mais conseguiria separar os dois casos.

5. TIPAGEM
   Toda coluna entra como texto (dtype=str), inferência desligada.
   Motivo: a inferência decide sozinha o que não é dela. Ela leria data em
   dd/mm/aaaa sem formato declarado, arrecadacao (inteiros e decimais com
   ponto misturados) como número de ponto flutuante, e minuto com "90+9"
   ora como número, ora como texto. A conversão acontece na etapa 2, onde
   é uma decisão registrada.

6. SAÍDA NA TELA
   Uma linha por tabela, com nome qualificado e contagem de linhas vinda do
   banco (não do DataFrame), milhar separado por ponto.
   Uma linha final com o total.
   Essa saída é meu único instrumento de conferência nesta etapa.
   O stdout precisa ser reconfigurado para utf-8: rodo no Prompt de Comando
   do Windows, onde acento sai embaralhado por padrão.
   (Atualizado por SDD/refatoracao.md: a saída é feita pelo logging de
   pipeline/log.py, com o mesmo texto; erro vai para o stderr.)

7. ERRO
   Antes de abrir o banco, verifique se os quatro arquivos existem.
   Faltando qualquer um: liste os que faltam, diga em que pasta procurou e
   encerre com sys.exit(1). Não ingira parcialmente.
   Motivo: ingerir três de quatro tabelas em silêncio produz um painel
   errado que parece certo.

CRITÉRIOS DE ACEITE (ingestão)
- A execução imprime quatro linhas e um total de 59.268 registros:
    raw.partidas        9.165
    raw.estatisticas   18.330
    raw.gols           10.820
    raw.cartoes        20.953
- Rodar duas vezes seguidas imprime exatamente a mesma coisa.
- DESCRIBE raw.partidas mostra todas as colunas como VARCHAR, com os nomes
  do cabeçalho (rodata, mandante_Placar...).
- Em raw.estatisticas, posse_de_bola tem 1.550 linhas com o texto 'None' e
  9.212 nulos; precisao_passes tem 3.854 linhas com 'None'.
- Em raw.partidas, 5.077 valores de arena começam com '\xa0', vencedor tem
  o valor '-', e arrecadacao tem 380 valores preenchidos.
- Remover um arquivo do mapa da pasta faz o script parar antes de gravar
  qualquer tabela. Remover o Legenda.txt não muda nada.
- O script termina sozinho e devolve o terminal: nenhum processo fica de pé.

SPEC DO ui.py (terceiro artefato)
Quero explorar o banco pelo navegador, em vez de ler tabela no terminal.

U1. O QUE FAZ
    Abre o brasileirao.duckdb da raiz do projeto, instala e carrega a
    extensão `ui` do DuckDB (INSTALL ui; LOAD ui;) e chama CALL start_ui(),
    que sobe o servidor em http://localhost:4213 e abre o navegador.
U2. FICA DE PÉ ATÉ CTRL+C
    A extensão serve enquanto a conexão estiver viva. O script mantém o
    processo rodando, imprime a URL e a instrução "Ctrl+C para encerrar", e
    no Ctrl+C fecha a conexão e sai limpo, sem traceback.
    Motivo: o arquivo .duckdb aceita um único processo escrevendo. Com o
    ui.py de pé, a ingestão falha com "Could not set lock on file". Saber
    exatamente como desligar o servidor faz parte da ferramenta.
U3. NÃO CRIA BANCO
    Se brasileirao.duckdb não existir, diga que é preciso rodar a ingestão
    antes e encerre com sys.exit(1). Por isso NÃO use conectar() de
    pipeline/db.py, que cria o arquivo quando ele falta: um banco vazio
    aberto no navegador parece ingestão quebrada.
U4. SEPARAÇÃO
    ui.py não importa pipeline/ingestao.py, e a ingestão não importa ui.py:
    a ingestão não sobe servidor, não abre navegador e não depende da
    extensão ui para rodar.
U5. SAÍDA NA TELA
    Mesma regra do item 6: stdout reconfigurado para utf-8.

CRITÉRIOS DE ACEITE (ui.py)
- uv run python ui.py abre o navegador em localhost:4213 e o schema raw
  aparece com as quatro tabelas.
- Ctrl+C devolve o terminal sem traceback, e logo depois a ingestão roda
  sem erro de lock.
- Renomear brasileirao.duckdb faz o ui.py parar com a mensagem, sem criar
  arquivo novo.

ENTREGA, nesta ordem, para cada um dos três arquivos
1. A spec como docstring no topo do arquivo, dizendo por que cada regra
   existe, e não só o que ela manda fazer.
2. O código, com comentários apenas onde a decisão não é óbvia pelo código.
3. Uma lista final do que você assumiu e que não estava na spec. Se a lista
   não estiver vazia, é a minha spec que precisa melhorar.