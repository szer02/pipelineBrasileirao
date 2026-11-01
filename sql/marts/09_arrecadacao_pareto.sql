-- Grão: um clube mandante com arrecadação.
-- Que fração dos clubes faz 80% da arrecadação? Só 2025 tem arrecadação.
-- A renda é do jogo em casa, por isso o clube é o mandante. Ordem do maior
-- para o menor; o nome do clube desempata, para a posição e o acumulado serem
-- os mesmos a cada execução.
WITH arrecadacao_clube AS (
    -- Grão: um clube mandante.
    SELECT
        mandante          AS clube,
        count(*)          AS jogos,
        sum(arrecadacao)  AS arrecadacao
    FROM refined.partidas
    WHERE arrecadacao IS NOT NULL
    GROUP BY mandante
)
SELECT
    clube,
    jogos,
    arrecadacao,
    round(arrecadacao / jogos, 2)                                AS media_por_jogo,
    row_number() OVER (ORDER BY arrecadacao DESC, clube)         AS posicao,
    round(100.0 * sum(arrecadacao) OVER (
              ORDER BY arrecadacao DESC, clube
              ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
          / sum(arrecadacao) OVER (), 2)                         AS pct_acumulado
FROM arrecadacao_clube
ORDER BY posicao