# Brasileirão em números

Pipeline de dados em Python sobre o Campeonato Brasileiro de Futebol, Série A
de 2003 a 2025: do CSV bruto a um painel interativo, passando por três
camadas num banco DuckDB.

**Painel online:** [pipelinebrasileirao.streamlit.app](https://pipelinebrasileirao.streamlit.app/)

## Objetivo

Projeto final da trilha de **Engenheiro de Dados Jr** da Pós em Engenharia de
Dados e IA, para a passagem a **pleno**.

O projeto mostra, ponta a ponta, o trabalho de um engenheiro de dados:

- ingerir um dataset público sem perder nenhuma informação;
- tipar e limpar o dado com regras explícitas, que param o pipeline em vez de
  esconder o erro;
- modelar perguntas de negócio em SQL versionado, com o grão de cada tabela
  declarado;
- entregar um painel que só exibe números calculados no banco;
- cobrir tudo com testes automatizados que rodam em qualquer máquina.

Todo o desenvolvimento seguiu **spec-driven development**: cada etapa nasceu
de uma especificação escrita (pasta `SDD/`), e o código é consequência dela.
A spec de cada módulo está na docstring do topo do arquivo, com o motivo de
cada regra.

## Tecnologias utilizadas

| Tecnologia | Uso |
|---|---|
| Python 3.13 | linguagem do pipeline e do painel |
| [uv](https://docs.astral.sh/uv/) | ambiente virtual, dependências e execução |
| DuckDB 2.0 | banco analítico em arquivo único (`brasileirao.duckdb`) |
| pandas 3 | leitura dos CSV na ingestão |
| SQL | regras de negócio da camada de marts |
| Streamlit | painel web |
| Plotly | gráficos do painel |
| pytest + pytest-cov | testes unitários e cobertura |
| Ruff | lint e formatação |

## Arquitetura em camadas (medallion)

```mermaid
flowchart LR
    A["raw/*.csv.gz<br/>4 arquivos do Kaggle"] -->|pipeline.ingestao| B[("raw<br/>bronze")]
    B -->|pipeline.transformacao| C[("refined<br/>prata")]
    C -->|"pipeline.marts<br/>sql/marts/*.sql"| D[("marts<br/>ouro")]
    D -->|"painel.py + app.py"| E["Painel Streamlit"]
```

As três camadas são schemas do mesmo arquivo `brasileirao.duckdb`.

| Camada | Schema | Conteúdo | Regra central |
|---|---|---|---|
| Bronze | `raw` | `partidas`, `estatisticas`, `gols`, `cartoes`, exatamente como chegaram | nenhuma conversão, nenhum descarte: tudo VARCHAR |
| Prata | `refined` | as mesmas quatro tabelas, com tipos e nomes em português | conversão que falha para tudo; nada vira nulo em silêncio |
| Ouro | `marts` | 14 tabelas, uma por pergunta de negócio | cada tabela é um único SELECT num arquivo `.sql` |

## O que é uma linha de cada tabela

As quatro tabelas têm o mesmo nome e o mesmo número de linhas em `raw` e em
`refined`: a transformação tipa e renomeia, não descarta.

| Tabela | Uma linha é | Chave | Linhas |
|---|---|---|---|
| `partidas` | uma partida | `partida_id` | 9.165 |
| `estatisticas` | um clube numa partida | `partida_id`, `clube` | 18.330 |
| `gols` | um gol | sem chave: a linha inteira | 10.820 |
| `cartoes` | um cartão | sem chave: a linha inteira | 20.953 |

`gols`, `cartoes` e `estatisticas` apontam para `partidas` por `partida_id`.
Juntar `partidas` com `gols` ou `cartoes` multiplica linhas: cada partida se
repete uma vez por gol ou por cartão. Por isso nenhum mart soma placar depois
desse JOIN.

## Estrutura do projeto

```
pipeline_brasileirao/
├── raw/                         # dados de origem (.csv.gz) e Legenda.txt
├── pipeline/
│   ├── db.py                    # conexão e gravação, compartilhadas pelas etapas
│   ├── log.py                   # logging das etapas: relatório no stdout, erro no stderr
│   ├── ingestao.py              # etapa 1: CSV -> raw
│   ├── transformacao.py         # etapa 2: raw -> refined
│   └── marts.py                 # etapa 3: executa sql/marts/ -> marts
├── sql/marts/                   # 14 arquivos NN_nome.sql, um por mart
├── painel.py                    # leitura, formato, identidade dos clubes e gráficos
├── app.py                       # página do Streamlit
├── .streamlit/config.toml       # tema escuro verde e amarelo
├── test/                        # um arquivo de teste por módulo
├── SDD/                         # specs de cada etapa
├── ui.py                        # abre o banco na interface web do DuckDB
├── .mcp.json                    # servidor MCP do DuckDB (somente leitura)
├── pyproject.toml               # dependências, pytest e coverage
├── LICENSE                      # licença dos dados
└── brasileirao.duckdb           # gerado pelo pipeline; versionado só para o deploy
```

O `brasileirao.duckdb` não é fonte de nada: é a saída do pipeline. Veja
[O banco versionado e o deploy](#o-banco-versionado-e-o-deploy).

## Como usar

Pré-requisito: [uv](https://docs.astral.sh/uv/getting-started/installation/)
instalado. O uv baixa o Python 3.13 se ele não estiver na máquina.

```bash
# 1. Instalar as dependências (inclui as de desenvolvimento)
uv sync

# 2. Rodar o pipeline, nesta ordem
uv run python -m pipeline.ingestao       # raw/*.csv.gz -> schema raw
uv run python -m pipeline.transformacao  # raw -> refined
uv run python -m pipeline.marts          # refined -> marts

# 3. Abrir o painel (http://localhost:8501)
uv run streamlit run app.py
```

Cada etapa registra, pelo `logging`, uma linha por tabela com a contagem lida
do banco, e encerra com erro se a etapa anterior não tiver rodado. O
relatório sai no stdout e as mensagens de erro no stderr.

O painel abre na **Visão geral**, com três abas: Campeonato, Temporada e
Jogadores. Pela barra lateral, escolha um dos 46 clubes para ver a página
dele. Depois de rodar `pipeline.marts` com o painel aberto, use o botão
**Recarregar dados**.

Para explorar o banco no navegador:

```bash
uv run python ui.py   # Ctrl+C para encerrar
```

> O arquivo `.duckdb` aceita um único processo escrevendo. Com o `ui.py` de
> pé, as etapas do pipeline falham com erro de lock. O painel não tem esse
> problema: ele abre o banco só para leitura e fecha a conexão a cada leitura.

> O `.mcp.json` configura um servidor MCP para consultar o banco por uma IA,
> em somente leitura. Ele roda com `uvx`, que pode trazer um DuckDB mais
> antigo que o do projeto e falhar ao abrir o arquivo ("database file with
> version number 69"). Nesse caso, consulte pelo próprio projeto:
> `uv run python -c "import duckdb; ..."` com `read_only=True`.

Para adicionar um mart, crie `sql/marts/NN_nome.sql` com um único SELECT e
rode `pipeline.marts` de novo. A tabela `marts.nome` é criada sem mudar
nenhuma linha de Python.

### O que esperar

| Etapa | Saída |
|---|---|
| `pipeline.ingestao` | 4 tabelas em `raw`, 59.268 linhas |
| `pipeline.transformacao` | 59.268 -> 59.268 linhas (0 duplicatas removidas) |
| `pipeline.marts` | 14 marts, 4.662 linhas |
| `pytest --cov` | 70 testes passando, 98% de cobertura |

Rodar qualquer etapa duas vezes imprime exatamente a mesma coisa: cada
tabela é recriada, nada acumula.

## O banco versionado e o deploy

O `brasileirao.duckdb` é **gerado**, nunca editado à mão. Ele sai inteiro
dos três comandos do pipeline, a partir dos `raw/*.csv.gz` e dos
`sql/marts/*.sql`. Os dois mais o código são a fonte da verdade; o banco é
só o resultado.

**Por que ele está no repositório.** Arquivo gerado normalmente fica fora do
git, e o `.gitignore` ignora `*.duckdb`. A única exceção é este arquivo
(`!brasileirao.duckdb`), por causa do painel online: o Streamlit Community
Cloud só roda o `app.py` e lê o que está no repositório. Ele não roda o
pipeline. Sem o banco no git, o painel publicado abriria vazio.

**O deploy é automático.** O Streamlit Cloud acompanha o branch `main` e
republica o painel sozinho a cada push. Não há passo manual de deploy: o que
estiver no `main` é o que aparece em
[pipelinebrasileirao.streamlit.app](https://pipelinebrasileirao.streamlit.app/).

**Como regenerar e publicar.** Sempre que mudar um CSV de `raw/`, um `.sql`
de `sql/marts/` ou uma regra do pipeline:

```bash
# 1. Feche o ui.py, se estiver aberto (ele segura o lock do banco)

# 2. Regenere o banco inteiro, nesta ordem
uv run python -m pipeline.ingestao
uv run python -m pipeline.transformacao
uv run python -m pipeline.marts

# 3. Confira as contagens na tela (veja "O que esperar") e o painel local
uv run streamlit run app.py

# 4. Versione o banco junto com a mudança que o gerou
git add brasileirao.duckdb sql/ pipeline/
git commit -m "..."
git push   # o painel online se atualiza sozinho
```

Na prática, ninguém precisa se preocupar com o banco: basta rodar os três
comandos e commitar o resultado. Se o painel online mostrar um número
diferente do local, o banco commitado ficou desatualizado. Rode o pipeline de
novo e faça o commit.

## Regras

### Ingestão (raw)

- Lê só os quatro arquivos do mapa, pelo nome; qualquer outro arquivo da
  pasta é ignorado.
- Toda coluna entra como texto, com a inferência de tipo desligada. Os nomes
  das colunas ficam como no cabeçalho, inclusive `rodata` e `mandante_Placar`.
- Só o campo vazio vira nulo. O texto `'None'` continua texto, para a etapa
  seguinte poder separá-lo do vazio.
- Faltando qualquer um dos quatro arquivos, nada é ingerido.

### Transformação (refined)

- Colunas renomeadas para português, em snake_case, por um mapa completo
  (`rodata` → `rodada`, `ID` → `partida_id`).
- Tipos declarados:
  - `data` vira DATE, com o formato `dd/mm/aaaa` declarado;
  - `arrecadacao` vira DECIMAL(10,2), porque é dinheiro;
  - posse `'58%'` vira 58, e `'None'` vira nulo, contado à parte na tela;
  - minuto `'90+5'` vira duas colunas, `minuto` 90 e `acrescimo` 5.
- Cada valor passa por uma checagem de formato (regex) antes de converter. Um
  valor fora do formato para o pipeline e mostra tabela, coluna e exemplo,
  em vez de virar nulo.
- Duplicata exata em `partidas` e `estatisticas` sai. Em `gols` e `cartoes`
  a linha repetida fica, porque essas tabelas não têm chave e duas linhas
  iguais podem ser dois eventos. Hoje são 0 repetidas.
- Anomalias de negócio ficam como chegaram. Quem decide o que fazer com elas
  é o mart que responde a pergunta.
- As quatro tabelas são gravadas numa única transação.

### Marts

- Cada arquivo `NN_nome.sql` vira a tabela `marts.nome`.
- O schema `marts` é apagado e recriado a cada execução, numa única
  transação. Um mart cujo arquivo foi apagado some do banco.
- Se um `.sql` falhar ou um mart voltar vazio, o schema volta a ser o da
  última execução que deu certo.

### Painel

- Nenhum cálculo em Python: o painel só lê, ordena, filtra, renomeia e
  formata. Número novo na tela exige um `.sql` novo em `sql/marts/`.
- Formato brasileiro sempre (`23.474`, `49,6%`, `R$ 518.065.218,68`), sem
  depender do locale da máquina.
- Sem logos oficiais nem escudos, que são marcas registradas. Cada clube é
  representado por um bloco com sigla e cores tradicionais, feito em HTML/CSS.

## Definições de negócio

| Conceito | Definição |
|---|---|
| Temporada | `year(data - 2 meses)`: jogos de janeiro e fevereiro contam na temporada anterior (a de 2020 terminou em fevereiro de 2021) |
| Pontos | vitória 3, empate 1, derrota 0, contados pelo placar; punições do tribunal não estão no dado |
| Desempate | pontos, vitórias, saldo e gols pró; empate em tudo divide a posição |
| Campeão | 1.º colocado da temporada pelos critérios acima |
| Aproveitamento | pontos ganhos sobre pontos disputados (3 por jogo), somados no período todo antes de dividir |
| Artilharia | gol contra fica fora: não é gol do atleta que aparece na linha |
| Gols nos acréscimos | faixas `45+` e `90+`, separadas das faixas do minuto 45 e 90 |
| Cobertura do dado | gols por atleta desde 2014; cartões de 2014 a 2024; arrecadação só em 2025 |

Os 14 marts, a pergunta que cada um responde e o que é uma linha:

| Mart | Pergunta | Uma linha é |
|---|---|---|
| 01 `gols_por_temporada` | Quantos gols saem por temporada? | uma temporada |
| 02 `artilheiros` | Quem mais fez gols? | um atleta |
| 03 `mando_de_campo` | Jogar em casa ajuda? | o campeonato inteiro |
| 04 `classificacao` | Qual a classificação de cada temporada? | um clube numa temporada |
| 05 `gols_por_partida` | Quantos gols costuma ter uma partida? | um total de gols na partida |
| 06 `aproveitamento_por_clube` | Qual o aproveitamento de cada clube? | um clube |
| 07 `cartoes_por_posicao` | Que posição leva mais cartão? | uma posição em campo |
| 08 `posse_e_resultado` | Quem fica mais com a bola vence mais? | uma situação de posse |
| 09 `arrecadacao_pareto` | Que fração dos clubes faz 80% da arrecadação? | um clube mandante |
| 10 `partidas_por_dia_da_semana` | Em que dia se joga, e em qual saem mais gols? | um dia da semana |
| 11 `titulos_por_clube` | Quem mais ganhou o Brasileirão? | um clube campeão |
| 12 `kpis` | Os números dos cartões do painel | o campeonato inteiro |
| 13 `gols_por_minuto` | Em que momento do jogo saem os gols? | uma faixa de 15 minutos |
| 14 `artilheiros_por_clube` | Quem mais fez gols por cada clube? | um atleta num clube |

O grão e as regras de cada mart estão nos comentários do topo do arquivo
`.sql` correspondente.

## Testes

```bash
uv run pytest --cov
```

São 70 testes unitários, um arquivo por módulo em `test/`, com cobertura de
**98%** do código medido (a meta configurada é 60%). Ficam fora da medição o
`app.py`, que é layout e é conferido no navegador, e o `ui.py`.

Os testes seguem três princípios:

- **Nunca o banco nem os dados do projeto.** Cada teste cria um DuckDB novo
  numa pasta temporária, com poucas linhas inventadas. A suíte roda sem o
  pipeline ter rodado e não altera o banco de ninguém.
- **Resultado da regra, não do dado.** Cada linha de entrada tem um
  comentário dizendo por que está ali (gol aos 90+5, posse `'None'`, jogo em
  fevereiro, gol contra). O valor esperado sai da conta sobre essa entrada,
  nunca de um número medido no dado real.
- **DuckDB de verdade, sem mock.** O nome de cada teste é a frase que ele
  prova, por exemplo `test_gol_contra_fica_fora_do_artilheiro`.

O que os 98% **não** medem: coverage conta só linhas de Python. Os 14
arquivos `.sql`, onde mora a regra de negócio, ficam fora dessa conta. Cinco
deles têm teste de regra próprio, rodado sobre tabelas inventadas:

- 01: jogo de fevereiro conta na temporada anterior;
- 02: gol contra fica fora;
- 04: pontos 3/1/0;
- 13: gol aos 90+3 vai para a faixa `90+`;
- 14: atleta com dois clubes tem duas linhas.

Os outros nove são conferidos pelos totais que precisam bater entre marts:

- 9.165 partidas nos marts 01, 05 e 10;
- 18.330 jogos nos marts 04 e 06;
- 23.474 gols nos marts 01 e 12.

As linhas sem teste são os `if __name__ == "__main__"`, o ROLLBACK da
transformação (as checagens barram todo dado ruim antes dele) e dois
`raise` de segurança.

## Onde a IA errou ou assumiu algo, e como descobri

A IA participou de todas as etapas: escreveu o código a partir das specs e
ajudou a escrever as specs e os 14 `.sql` dos marts. Cada entrega terminou
com uma lista "o que assumi", e nada foi aceito sem conferência, quase
sempre contando linhas antes e depois.

| Etapa | O que aconteceu | Como descobri |
|---|---|---|
| Ingestão | O pandas, por padrão, transforma o texto `'None'` em nulo. As colunas de posse e de precisão de passe teriam perdido, sem aviso, a diferença entre "campo vazio" e `'None'`. A spec passou a exigir `keep_default_na=False`. | Analisando a raw antes de escrever a spec: contagem de `'None'` por coluna (1.550 na posse, 3.854 na precisão). |
| Refined | Em vez de assumir, a IA perguntou o que fazer com os nulos de posse, o acréscimo, as linhas repetidas e a linha de total. | As respostas fecharam a conta: 9.212 nulos vindos da raw + 1.550 `'None'` = 10.762 nulos na refined. |
| MCP | Ao propor a correção do MCP (o servidor não abria o banco por diferença de versão do DuckDB), a IA incluiu uma flag `--read-only` que pode não existir na versão atual e impediria o servidor de subir. | Revisando a proposta antes de aplicar: o servidor já é somente leitura por padrão. |
| Executor de marts | A IA escreveu na docstring motivos para regras que a spec não justificava, e deixou sem tratamento um `.sql` que não seja UTF-8 (sai traceback em vez de mensagem clara). | Lendo a lista "o que assumi" (11 itens) e a docstring contra a spec. |
| SQL dos marts | Escritos com a IA. Decisões dela que eu aceitei: temporada = `year(data - 2 meses)`, artilheiro agrupado pelo nome, punições do tribunal ignoradas, o valor `'Zagueira'` mantido como chegou. | Totais que precisam bater entre marts (9.165 partidas, 18.330 jogos, 23.474 gols, 23 títulos, um por temporada) e os 23 campeões comparados com a história. |
| Grão | Para a página do clube, filtrar o mart 02 por clube mostraria 84 gols do Luciano pelo São Paulo. Os 84 somam quatro clubes; pelo São Paulo foram 62. Virou o mart 14, com grão atleta × clube. | Comparando os gols do mesmo atleta nos dois grãos. |
| Painel | Para a busca do critério de aceite (`groupby`, `merge`...) voltar vazia, a IA reescreveu a docstring sem essas palavras. Não escondia cálculo, mas mostrou que buscar palavra prova pouco. | Uma busca mais larga (`.agg(`, `value_counts`, `.max(`...), que só achou "pivotar" na docstring. |
| Painel | As cores e siglas dos 46 clubes vieram do conhecimento da IA, sem fonte oficial. | A própria IA apontou as menos seguras: Barueri, Grêmio Prudente e Ipatinga. |
| Testes | Os 98% de cobertura não incluem os `.sql`, porque coverage mede só Python. | Lendo a tabela do coverage contra a lista de arquivos do projeto. |


## Versionamento

O projeto inteiro foi desenvolvido em um único dia, fora do git, e
versionado no fim: um commit por etapa, na ordem em que foram feitas
(configuração, dados de origem, ingestão, transformação, marts 01 a 11,
marts 12 a 14, painel, testes e README). Cada spec de `SDD/` entrou no
mesmo commit do código que ela gerou. Por isso as datas dos commits ficam
a poucos minutos umas das outras: registram o momento do versionamento,
não o do desenvolvimento.

## Origem e licença

Dados públicos de Adão Duque, via Kaggle:
[Campeonato Brasileiro de Futebol](https://www.kaggle.com/datasets/adaoduque/campeonato-brasileiro-de-futebol).
Redistribuídos aqui comprimidos, sem alteração de conteúdo, sob
[GPL-2.0](https://www.gnu.org/licenses/old-licenses/gpl-2.0.html). Veja
[LICENSE](LICENSE).