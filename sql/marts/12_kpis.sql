-- Os cartões do painel que não saem prontos dos marts 01 a 11.
-- Grão: o campeonato inteiro, uma linha. Cada CTE também tem uma linha só,
-- e é isso que torna seguro juntá-las sem ON.
WITH campeonato AS (
    -- Temporada: year(data - 2 meses), a mesma regra dos marts 01, 04 e 11.
    SELECT
        min(year(data - INTERVAL 2 MONTH))                            AS temporada_inicial,
        max(year(data - INTERVAL 2 MONTH))                            AS temporada_final,
        count(DISTINCT year(data - INTERVAL 2 MONTH))                 AS temporadas,
        count(*)                                                      AS partidas,
        sum(placar_mandante + placar_visitante)                       AS gols,
        round(sum(placar_mandante + placar_visitante) / count(*), 2)  AS media_gols
    FROM refined.partidas
),
clubes AS (
    -- Clube que jogou ao menos uma partida, como mandante ou visitante.
    SELECT count(DISTINCT clube) AS clubes
    FROM (SELECT mandante AS clube FROM refined.partidas
          UNION
          SELECT visitante FROM refined.partidas)
),
acrescimos AS (
    -- Só a tabela gols tem o minuto, e ela começa em 2014.
    SELECT round(100.0 * count(*) FILTER (WHERE acrescimo IS NOT NULL) / count(*), 1) AS pct_gols_acrescimo
    FROM refined.gols
),
renda AS (
    -- Só a temporada 2025 tem arrecadação.
    SELECT sum(arrecadacao) AS arrecadacao_total
    FROM refined.partidas
)
SELECT *
FROM campeonato, clubes, acrescimos, renda