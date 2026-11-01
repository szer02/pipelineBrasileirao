-- Quem mais fez gols?
-- Grão: um atleta (pelo nome). A tabela gols só existe de 2014 em diante.
-- Gol contra fica fora: não é gol do atleta que aparece na linha.
-- Atleta que trocou de clube soma tudo numa linha; os clubes vão em lista.
SELECT
    g.atleta,
    count(*)                                              AS gols,
    count(*) FILTER (WHERE g.tipo = 'Penalty')            AS gols_penalti,
    count(*) FILTER (WHERE g.acrescimo IS NOT NULL)       AS gols_acrescimo,
    count(DISTINCT year(p.data - INTERVAL 2 MONTH))       AS temporadas,
    string_agg(DISTINCT g.clube, ', ' ORDER BY g.clube)   AS clubes
FROM refined.gols     AS g
JOIN refined.partidas AS p ON p.partida_id = g.partida_id
WHERE g.tipo IS DISTINCT FROM 'Gol Contra'
GROUP BY g.atleta
ORDER BY gols DESC, g.atleta