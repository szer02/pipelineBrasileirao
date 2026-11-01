-- Quantos gols saem por temporada?
-- Grão: uma temporada.
-- Temporada: year(data - 2 meses); jogos de jan/fev contam na do ano anterior
-- (a de 2020 terminou em fev/2021). Gol vem do placar, que cobre todas as temporadas.
SELECT
    year(data - INTERVAL 2 MONTH)                                     AS temporada,
    count(*)                                                          AS partidas,
    sum(placar_mandante + placar_visitante)                           AS gols,
    round(sum(placar_mandante + placar_visitante) / count(*), 2)      AS media_gols
FROM refined.partidas
GROUP BY temporada
ORDER BY temporada