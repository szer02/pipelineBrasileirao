-- Grão: um dia da semana.
-- Em que dia da semana se joga, e em qual saem mais gols?
-- isodow: 1 = segunda ... 7 = domingo; o nome é escrito no CASE para não
-- depender do idioma do sistema.
SELECT
    isodow(data)                                                  AS dia_num,
    CASE isodow(data)
        WHEN 1 THEN 'segunda' WHEN 2 THEN 'terça'  WHEN 3 THEN 'quarta'
        WHEN 4 THEN 'quinta'  WHEN 5 THEN 'sexta'  WHEN 6 THEN 'sábado'
        WHEN 7 THEN 'domingo' END                                 AS dia_semana,
    count(*)                                                      AS partidas,
    round(100.0 * count(*) / sum(count(*)) OVER (), 1)            AS pct_partidas,
    round(sum(placar_mandante + placar_visitante) / count(*), 2)  AS media_gols
FROM refined.partidas
GROUP BY dia_num
ORDER BY dia_num