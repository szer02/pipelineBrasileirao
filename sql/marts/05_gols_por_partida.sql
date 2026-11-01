-- Quantos gols costuma ter uma partida?
-- Grão: um total de gols na partida (0 gol, 1 gol, 2 gols...).
WITH gols_partida AS (
    -- Grão: uma partida.
    SELECT partida_id, placar_mandante + placar_visitante AS gols
    FROM refined.partidas
)
SELECT
    gols                                               AS gols_na_partida,
    count(*)                                           AS partidas,
    round(100.0 * count(*) / sum(count(*)) OVER (), 2) AS pct_partidas
FROM gols_partida
GROUP BY gols
ORDER BY gols_na_partida