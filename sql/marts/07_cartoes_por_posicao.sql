-- Grão: uma posição em campo.
-- Que posição leva mais cartão? A tabela cartoes cobre 2014 a 2024.
-- Um atleta tem vários cartões (1:N): atletas conta pessoas distintas pelo
-- nome, cartoes conta linhas. Posição vazia vira 'sem_posicao'; 'Zagueira'
-- fica como chegou. A coluna atletas não soma entre posições.
SELECT
    coalesce(posicao, 'sem_posicao')                                     AS posicao,
    count(*)                                                             AS cartoes,
    count(*) FILTER (WHERE cartao = 'Amarelo')                           AS amarelos,
    count(*) FILTER (WHERE cartao = 'Vermelho')                          AS vermelhos,
    count(DISTINCT atleta)                                               AS atletas,
    round(count(*) / count(DISTINCT atleta), 2)                          AS cartoes_por_atleta,
    round(100.0 * count(*) / sum(count(*)) OVER (), 1)                   AS pct_cartoes
FROM refined.cartoes
GROUP BY 1
ORDER BY cartoes DESC