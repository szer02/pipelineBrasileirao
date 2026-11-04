"""Saída das etapas do pipeline pelo módulo logging, no lugar de print.

Expõe exatamente:
    configurar_log()    prepara o logger "pipeline"; cada etapa chama no
                        início do seu main()

L1. SÓ O TEXTO DA MENSAGEM
    Formato "%(message)s": sem data, sem nível, sem nome do módulo.
    Por quê: a saída de cada etapa é o instrumento de conferência (contagens,
    nulos, duplicatas) e é comparada entre execuções; "rodar duas vezes
    imprime exatamente a mesma coisa" deixaria de valer com data na linha.

L2. RELATÓRIO NO STDOUT, ERRO NO STDERR
    INFO vai para o stdout; WARNING e acima vão para o stderr.
    Por quê: é a separação que o print não fazia. Quem redireciona a saída
    para um arquivo continua vendo o erro no terminal.

L3. UTF-8
    stdout e stderr reconfigurados para utf-8.
    Por quê: no Prompt de Comando do Windows acento sai embaralhado por
    padrão, e agora há mensagem com acento nos dois canais.

L4. REEXECUÇÃO
    Chamar configurar_log() de novo troca os handlers, não acrescenta.
    Por quê: os testes chamam main() várias vezes no mesmo processo; handler
    acumulado imprimiria cada linha repetida.

L5. ESCOPO
    Configura só o logger "pipeline", nunca o logger raiz. Cada etapa usa
    logging.getLogger("pipeline.<etapa>"), escrito por extenso porque, com
    python -m, __name__ vale "__main__" e ficaria fora da hierarquia.
    Por quê: mexer no logger raiz mudaria a saída de bibliotecas e do pytest.

Importar este módulo não configura nada: só configurar_log() configura.
"""

import logging
import sys

NOME = "pipeline"


class _AteInfo(logging.Filter):
    def filter(self, registro: logging.LogRecord) -> bool:
        return registro.levelno < logging.WARNING


def configurar_log() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

    formato = logging.Formatter("%(message)s")

    saida = logging.StreamHandler(sys.stdout)
    saida.setLevel(logging.INFO)
    saida.addFilter(_AteInfo())
    saida.setFormatter(formato)

    erro = logging.StreamHandler(sys.stderr)
    erro.setLevel(logging.WARNING)
    erro.setFormatter(formato)

    logger = logging.getLogger(NOME)
    logger.setLevel(logging.INFO)
    for antigo in list(logger.handlers):
        logger.removeHandler(antigo)
    logger.addHandler(saida)
    logger.addHandler(erro)
