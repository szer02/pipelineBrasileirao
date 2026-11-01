-- Grão: um clube.
-- Qual o aproveitamento de cada clube em todas as temporadas que jogou?
-- Aproveitamento: pontos ganhos sobre pontos disputados (3 por jogo), somados
-- primeiro e divididos depois. O grão muda duas vezes: partida -> clube numa
-- partida (CTE) -> clube (SELECT final). Média dos aproveitamentos de cada
-- temporada daria outro número: 2003 e 2004 tiveram 46 jogos, as outras 38.
-- Vitórias, empates, derrotas e gols são as somas do clube em todas as
-- temporadas, para a página do clube no painel.
WITH jogo_clube AS (
    -- Grão: um clube numa partida.
    SELECT year(data - INTERVAL 2 MONTH) AS temporada, mandante AS clube,
           placar_mandante AS gols_pro, placar_visitante AS gols_contra
    FROM refined.partidas
    UNION ALL
    SELECT year(data - INTERVAL 2 MONTH), visitante,
           placar_visitante, placar_mandante
    FROM refined.partidas
),
resultado AS (
    -- Grão: um clube numa partida, com os pontos ganhos.
    SELECT
        temporada,
        clube,
        gols_pro,
        gols_contra,
        CASE WHEN gols_pro > gols_contra THEN 3
             WHEN gols_pro = gols_contra THEN 1 ELSE 0 END AS pontos
    FROM jogo_clube
)
SELECT
    clube,
    count(DISTINCT temporada)                      AS temporadas,
    count(*)                                       AS jogos,
    sum(pontos)                                    AS pontos,
    round(100.0 * sum(pontos) / (3 * count(*)), 1) AS aproveitamento_pct,
    count(*) FILTER (WHERE pontos = 3)             AS vitorias,
    count(*) FILTER (WHERE pontos = 1)             AS empates,
    count(*) FILTER (WHERE pontos = 0)             AS derrotas,
    sum(gols_pro)                                  AS gols_pro,
    sum(gols_contra)                               AS gols_contra
FROM resultado
GROUP BY clube
ORDER BY aproveitamento_pct DESC, clube