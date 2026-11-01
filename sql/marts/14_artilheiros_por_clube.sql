-- Grão: um atleta num clube.
-- Quem mais fez gols por cada clube? A tabela gols só existe de 2014 em diante.
-- Gol contra fica fora, como no mart 02. Diferente do 02, um atleta que passou
-- por três clubes tem três linhas: os gols de cada linha são só por aquele
-- clube. A coluna gols soma por clube, mas o mesmo atleta aparece em várias.
-- posicao: ranking dentro do clube, do maior para o menor; empate leva a
-- mesma posição.
SELECT
    g.clube,
    g.atleta,
    count(*)                                              AS gols,
    count(*) FILTER (WHERE g.tipo = 'Penalty')            AS gols_penalti,
    count(DISTINCT year(p.data - INTERVAL 2 MONTH))       AS temporadas,
    rank() OVER (PARTITION BY g.clube ORDER BY count(*) DESC) AS posicao
FROM refined.gols     AS g
JOIN refined.partidas AS p ON p.partida_id = g.partida_id
WHERE g.tipo IS DISTINCT FROM 'Gol Contra'
GROUP BY g.clube, g.atleta
ORDER BY g.clube, posicao, g.atleta