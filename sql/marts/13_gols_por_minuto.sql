-- Grão: uma faixa de 15 minutos de jogo, com os acréscimos de cada tempo à parte.
-- Em que momento do jogo saem os gols? A tabela gols só existe de 2014 em diante.
-- Todo gol conta, inclusive gol contra: a pergunta é quando a bola entrou.
-- Gol com acréscimo vai para '45+' ou '90+', não para a faixa do minuto 45 ou 90.
SELECT
    CASE WHEN acrescimo IS NOT NULL AND minuto = 45 THEN 4
         WHEN acrescimo IS NOT NULL AND minuto = 90 THEN 8
         WHEN minuto <= 15 THEN 1
         WHEN minuto <= 30 THEN 2
         WHEN minuto <= 45 THEN 3
         WHEN minuto <= 60 THEN 5
         WHEN minuto <= 75 THEN 6
         ELSE 7 END                                    AS ordem,
    CASE WHEN acrescimo IS NOT NULL AND minuto = 45 THEN '45+'
         WHEN acrescimo IS NOT NULL AND minuto = 90 THEN '90+'
         WHEN minuto <= 15 THEN '0-15'
         WHEN minuto <= 30 THEN '16-30'
         WHEN minuto <= 45 THEN '31-45'
         WHEN minuto <= 60 THEN '46-60'
         WHEN minuto <= 75 THEN '61-75'
         ELSE '76-90' END                              AS faixa,
    count(*)                                           AS gols,
    round(100.0 * count(*) / sum(count(*)) OVER (), 1) AS pct_gols
FROM refined.gols
GROUP BY ordem, faixa
ORDER BY ordem