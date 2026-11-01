-- Grão: uma situação de posse ('mais_posse', 'menos_posse', 'igual').
-- Quem fica mais com a bola vence mais?
-- Denominador: partidas com a posse dos dois clubes. Linha zerada ou 'None'
-- (estatística não coletada) já chega nula de refined e fica fora.
-- Cada partida entra duas vezes, uma por clube: a coluna jogos soma o dobro
-- das partidas.
WITH posse_partida AS (
    -- Grão: uma partida com a posse dos dois clubes.
    SELECT
        p.partida_id,
        p.placar_mandante,
        p.placar_visitante,
        em.posse_pct AS posse_mandante,
        ev.posse_pct AS posse_visitante
    FROM refined.partidas     AS p
    JOIN refined.estatisticas AS em ON em.partida_id = p.partida_id AND em.clube = p.mandante
    JOIN refined.estatisticas AS ev ON ev.partida_id = p.partida_id AND ev.clube = p.visitante
    WHERE em.posse_pct IS NOT NULL
      AND ev.posse_pct IS NOT NULL
),
jogo_clube AS (
    -- Grão: um clube numa partida.
    SELECT posse_mandante AS posse, posse_visitante AS posse_adversario,
           placar_mandante AS gols_pro, placar_visitante AS gols_contra
    FROM posse_partida
    UNION ALL
    SELECT posse_visitante, posse_mandante, placar_visitante, placar_mandante
    FROM posse_partida
)
SELECT
    CASE WHEN posse > posse_adversario THEN 'mais_posse'
         WHEN posse < posse_adversario THEN 'menos_posse'
         ELSE 'igual' END                                              AS situacao,
    count(*)                                                           AS jogos,
    sum(CASE WHEN gols_pro >  gols_contra THEN 1 ELSE 0 END)           AS vitorias,
    sum(CASE WHEN gols_pro =  gols_contra THEN 1 ELSE 0 END)           AS empates,
    sum(CASE WHEN gols_pro <  gols_contra THEN 1 ELSE 0 END)           AS derrotas,
    round(100.0 * sum(CASE WHEN gols_pro > gols_contra THEN 1 ELSE 0 END)
          / count(*), 1)                                               AS pct_vitorias
FROM jogo_clube
GROUP BY situacao
ORDER BY situacao