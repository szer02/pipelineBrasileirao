-- Jogar em casa ajuda?
-- Grão: o campeonato inteiro, uma linha.
-- Resultado vem do placar (bate 100% com a coluna vencedor).
SELECT
    count(*)                                                                  AS partidas,
    sum(CASE WHEN placar_mandante >  placar_visitante THEN 1 ELSE 0 END)      AS vitorias_mandante,
    sum(CASE WHEN placar_mandante =  placar_visitante THEN 1 ELSE 0 END)      AS empates,
    sum(CASE WHEN placar_mandante <  placar_visitante THEN 1 ELSE 0 END)      AS vitorias_visitante,
    round(100.0 * sum(CASE WHEN placar_mandante > placar_visitante THEN 1 ELSE 0 END)
          / count(*), 1)                                                      AS pct_vitorias_mandante,
    round(100.0 * sum(CASE WHEN placar_mandante = placar_visitante THEN 1 ELSE 0 END)
          / count(*), 1)                                                      AS pct_empates,
    round(100.0 * sum(CASE WHEN placar_mandante < placar_visitante THEN 1 ELSE 0 END)
          / count(*), 1)                                                      AS pct_vitorias_visitante
FROM refined.partidas