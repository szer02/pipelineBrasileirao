-- Grão: um clube campeão.
-- Quem mais ganhou o Brasileirão? Só as temporadas do dado (2003 em diante).
-- Campeão: 1.º lugar da temporada pelos mesmos critérios do mart 04 (pontos,
-- vitórias, saldo, gols pró, contados pelo placar). A lógica é repetida aqui,
-- lendo de refined, para o mart não depender de outro mart.
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
por_clube AS (
    -- Grão: um clube numa temporada.
    SELECT
        temporada,
        clube,
        sum(CASE WHEN gols_pro > gols_contra THEN 1 ELSE 0 END)  AS vitorias,
        sum(CASE WHEN gols_pro = gols_contra THEN 1 ELSE 0 END)  AS empates,
        sum(gols_pro) - sum(gols_contra)                         AS saldo,
        sum(gols_pro)                                            AS gols_pro
    FROM jogo_clube
    GROUP BY temporada, clube
),
campeao AS (
    -- Grão: uma temporada (o 1.º colocado).
    SELECT temporada, clube
    FROM por_clube
    QUALIFY rank() OVER (PARTITION BY temporada
                         ORDER BY 3 * vitorias + empates DESC, vitorias DESC, saldo DESC, gols_pro DESC) = 1
)
SELECT
    clube,
    count(*)                                                   AS titulos,
    string_agg(temporada::VARCHAR, ', ' ORDER BY temporada)    AS temporadas,
    max(temporada)                                             AS ultimo_titulo,
    rank() OVER (ORDER BY count(*) DESC)                       AS posicao
FROM campeao
GROUP BY clube
ORDER BY posicao, ultimo_titulo DESC