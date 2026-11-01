-- Qual a classificação de cada temporada?
-- Grão: um clube numa temporada.
-- Pontos: vitória 3, empate 1, derrota 0, contados só pelo placar.
-- Punições do tribunal (perda de pontos) não estão no dado e não entram.
-- Desempate: pontos, vitórias, saldo, gols pró; igual em tudo, mesma posição.
WITH jogo_clube AS (
    -- Grão: um clube numa partida (cada partida vira duas linhas).
    SELECT year(data - INTERVAL 2 MONTH) AS temporada, mandante AS clube,
           placar_mandante AS gols_pro, placar_visitante AS gols_contra
    FROM refined.partidas
    UNION ALL
    SELECT year(data - INTERVAL 2 MONTH), visitante,
           placar_visitante, placar_mandante
    FROM refined.partidas
),
por_clube AS (
    -- Grão: um clube numa temporada.
    SELECT
        temporada,
        clube,
        count(*)                                                AS jogos,
        sum(CASE WHEN gols_pro >  gols_contra THEN 1 ELSE 0 END) AS vitorias,
        sum(CASE WHEN gols_pro =  gols_contra THEN 1 ELSE 0 END) AS empates,
        sum(CASE WHEN gols_pro <  gols_contra THEN 1 ELSE 0 END) AS derrotas,
        sum(gols_pro)                                           AS gols_pro,
        sum(gols_contra)                                        AS gols_contra,
        sum(gols_pro) - sum(gols_contra)                        AS saldo
    FROM jogo_clube
    GROUP BY temporada, clube
)
SELECT
    temporada,
    rank() OVER (PARTITION BY temporada
                 ORDER BY 3 * vitorias + empates DESC, vitorias DESC, saldo DESC, gols_pro DESC) AS posicao,
    clube,
    3 * vitorias + empates AS pontos,
    jogos,
    vitorias,
    empates,
    derrotas,
    gols_pro,
    gols_contra,
    saldo
FROM por_clube
ORDER BY temporada, posicao, clube