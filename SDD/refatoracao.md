CONTEXTO
O projeto foi entregue e aprovado. A avaliação apontou três melhorias:
  1) pipeline/transformacao.py:333 main tem 120 linhas e
     pipeline/marts.py:86 main tem 87: separe por etapa.
  2) São 37 prints no pipeline: use logging.
  3) brasileirao.duckdb (2,4 MB) está versionado para o deploy; documente
     que ele é gerado e como regenerar.
Trabalho com spec-driven development: a spec abaixo é a fonte da verdade.
Esta é uma refatoração: nenhum número, tabela ou tela muda.

O QUE JÁ EXISTE
pipeline/db.py, ingestao.py, transformacao.py, marts.py, painel.py, app.py,
sql/marts/*.sql (14), test/ (70 testes, 98%) e o painel publicado no
Streamlit Community Cloud, que lê o brasileirao.duckdb do repositório.

SPEC

R1. FUNÇÕES POR ETAPA
    Em transformacao.py e marts.py, main() só encadeia as etapas, uma
    função para cada:
      transformacao: conferir raw, validar formato, validar conversão,
        validar chaves, gravar refined, relatar.
      marts: conferir refined, listar e validar os arquivos .sql, executar
        os marts na transação, relatar.
    A ordem das etapas, as mensagens e o comportamento não mudam.
    ingestao.py fica como está: o main() dela já é curto.
    Por quê: cada etapa lida, testada e alterada sem atravessar as outras.

R2. LOGGING NO LUGAR DE PRINT
    Nenhum print em pipeline/. Arquivo novo pipeline/log.py com
    configurar_log(), chamado no início de cada main():
    - formato só com o texto da mensagem (sem data, sem nível);
    - INFO no stdout, WARNING e acima no stderr;
    - stdout e stderr reconfigurados para utf-8;
    - chamar de novo troca os handlers, não acrescenta;
    - configura só o logger "pipeline", nunca o raiz.
    O relatório de cada etapa sai em INFO; as mensagens que antecedem um
    sys.exit(1) saem em ERROR.
    Não vai para db.py: a regra D2 diz que db.py não imprime nada.
    Por quê do texto igual: a saída é o instrumento de conferência e o
    critério "rodar duas vezes imprime a mesma coisa" continua valendo.
    Por quê do stderr: separar erro de relatório é o que o print não fazia.

R3. README: O BANCO VERSIONADO
    Explicar que o brasileirao.duckdb é gerado pelos três comandos do
    pipeline, que só está no repositório porque o Streamlit Cloud não roda
    o pipeline, que o painel online se atualiza sozinho a cada push, e o
    passo a passo para regenerar e publicar. O banco não é gerado no
    deploy.
    Por quê: quem lê o repositório precisa saber que o arquivo é derivado e
    que não se edita à mão.

FORA DO ESCOPO
painel.py, app.py, sql/marts/, os testes e o ui.py não mudam.

CRITÉRIOS DE ACEITE
- As três etapas, rodadas sobre os mesmos raw/*.csv.gz, imprimem no
  stdout exatamente o mesmo texto de antes, com o stderr vazio.
- O banco gerado é igual ao de antes, tabela por tabela (EXCEPT ALL vazio
  nos dois sentidos, nos schemas raw, refined e marts).
- Nos caminhos de erro, o texto é o mesmo de antes e sai no stderr, com o
  stdout vazio e saída 1.
- Uma busca por "print(" em pipeline/ volta vazia.
- uv run pytest --cov: os 70 testes passam e o TOTAL fica acima de 60%.
