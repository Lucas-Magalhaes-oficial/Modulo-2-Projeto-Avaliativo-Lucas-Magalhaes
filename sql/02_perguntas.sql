-- =====================================================================================================
-- 02_perguntas.sql  -  As 6 PERGUNTAS DE NEGOCIO da Controladoria, respondidas em SQL
-- =====================================================================================================
-- Rode no pgAdmin (Query Tool) conectado ao banco pncp_controladoria, DEPOIS da carga (python -m src.carregar).
-- O pgAdmin mostra so o resultado da ULTIMA consulta quando se roda o arquivo todo: para ver cada uma,
-- selecione o trecho da consulta (do SELECT ou WITH ate o ponto e virgula) e aperte F5.
--
-- Regras que valem para todas as perguntas (secao 4.2 e 4.4 do enunciado):
--  * Percentual = SOMA / SOMA, nunca media de percentuais.
--  * A economia so conta os itens COMPARAVEIS (comparavel = 1): fora Credenciamento e razao fora de 0,1 a 10.
--  * Volume = soma do valor total homologado de TODOS os itens da fato (comparaveis ou nao).
--  * NULLIF(denominador, 0) evita divisao por zero (Credenciamento nao tem item comparavel).
--  * Os numeros daqui sao os mesmos das medidas do dashboard no Power BI.
-- =====================================================================================================


-- =====================================================================================================
-- PERGUNTA 1  -  Economia global do Poder Publico
-- Qual e o percentual e o valor financeiro nominal economizado pelo governo
-- (diferenca entre valor estimado e valor homologado)?
-- =====================================================================================================
SELECT
    COUNT(*)                                                                         AS itens_na_fato,
    COUNT(*) FILTER (WHERE comparavel = 1)                                           AS itens_comparaveis,
    SUM(CASE WHEN comparavel = 1 THEN valor_total_estimado   ELSE 0 END)             AS estimado_comparavel,
    SUM(CASE WHEN comparavel = 1 THEN valor_total_homologado ELSE 0 END)             AS homologado_comparavel,
    SUM(CASE WHEN comparavel = 1 THEN economia_valor         ELSE 0 END)             AS economia_nominal,
    ROUND(100.0 * SUM(CASE WHEN comparavel = 1 THEN economia_valor ELSE 0 END)
          / NULLIF(SUM(CASE WHEN comparavel = 1 THEN valor_total_estimado ELSE 0 END), 0), 2)
                                                                                     AS economia_pct
FROM fato_item_contratado;


-- =====================================================================================================
-- PERGUNTA 2  -  Concentracao e risco de fornecedores
-- Quem sao os maiores fornecedores em volume financeiro e qual percentual do orcamento publico
-- esta concentrado neles?
-- (fornecedor = CNPJ/CPF limpo: o mesmo nome com CNPJ diferente, como uma filial, conta como outro)
-- =====================================================================================================

-- 2a) Os 10 maiores fornecedores, com a participacao de cada um no volume total
SELECT
    ROW_NUMBER() OVER (ORDER BY SUM(f.valor_total_homologado) DESC)                  AS posicao,
    d.nome_fornecedor,
    d.ni_fornecedor,
    SUM(f.valor_total_homologado)                                                    AS volume_homologado,
    ROUND(100.0 * SUM(f.valor_total_homologado)
          / (SELECT SUM(valor_total_homologado) FROM fato_item_contratado), 2)       AS participacao_pct
FROM fato_item_contratado AS f
JOIN dim_fornecedor       AS d ON d.sk_fornecedor = f.sk_fornecedor
GROUP BY d.sk_fornecedor, d.nome_fornecedor, d.ni_fornecedor
ORDER BY volume_homologado DESC
LIMIT 10;

-- 2b) Concentracao dos 10 maiores juntos: quanto do volume total eles representam
WITH top10 AS (
    SELECT sk_fornecedor, SUM(valor_total_homologado) AS volume
    FROM fato_item_contratado
    GROUP BY sk_fornecedor
    ORDER BY volume DESC
    LIMIT 10
)
SELECT
    SUM(volume)                                                                      AS volume_top10,
    (SELECT SUM(valor_total_homologado) FROM fato_item_contratado)                   AS volume_total,
    ROUND(100.0 * SUM(volume)
          / (SELECT SUM(valor_total_homologado) FROM fato_item_contratado), 2)       AS concentracao_top10_pct
FROM top10;


-- =====================================================================================================
-- PERGUNTA 3  -  Eficacia por modalidade
-- Quais modalidades licitatorias trazem maior desagio/economia e quais concentram o maior volume de recursos?
-- (desagio = economia %; "vs media geral" esta em pontos percentuais; Credenciamento fica sem economia)
-- =====================================================================================================
WITH geral AS (
    SELECT 100.0 * SUM(CASE WHEN comparavel = 1 THEN economia_valor ELSE 0 END)
           / NULLIF(SUM(CASE WHEN comparavel = 1 THEN valor_total_estimado ELSE 0 END), 0) AS economia_pct_geral
    FROM fato_item_contratado
)
SELECT
    m.nome_modalidade,
    COUNT(*)                                                                         AS itens,
    SUM(f.valor_total_homologado)                                                    AS volume_homologado,
    ROUND(100.0 * SUM(f.valor_total_homologado)
          / (SELECT SUM(valor_total_homologado) FROM fato_item_contratado), 2)       AS participacao_volume_pct,
    SUM(CASE WHEN f.comparavel = 1 THEN f.economia_valor ELSE 0 END)                 AS economia_nominal,
    ROUND(100.0 * SUM(CASE WHEN f.comparavel = 1 THEN f.economia_valor ELSE 0 END)
          / NULLIF(SUM(CASE WHEN f.comparavel = 1 THEN f.valor_total_estimado ELSE 0 END), 0), 2)
                                                                                     AS economia_pct,
    ROUND(100.0 * SUM(CASE WHEN f.comparavel = 1 THEN f.economia_valor ELSE 0 END)
          / NULLIF(SUM(CASE WHEN f.comparavel = 1 THEN f.valor_total_estimado ELSE 0 END), 0)
          - (SELECT economia_pct_geral FROM geral), 2)                               AS desagio_vs_media_pp
FROM fato_item_contratado AS f
JOIN dim_modalidade       AS m ON m.sk_modalidade = f.sk_modalidade
GROUP BY m.sk_modalidade, m.nome_modalidade
ORDER BY economia_pct DESC NULLS LAST;


-- =====================================================================================================
-- PERGUNTA 4  -  Tempo do ciclo de compras
-- Qual a duracao media (em dias) entre o lancamento do edital e a sua homologacao final,
-- segmentada por orgao?
-- (agrupa pelo NOME padronizado do orgao, conta so itens com ciclo e mostra so orgaos com 5 ou mais)
-- =====================================================================================================

-- 4a) Ciclo medio por orgao
SELECT
    o.nome_orgao,
    COUNT(f.dias_ciclo)                                                              AS itens_com_ciclo,
    COUNT(DISTINCT o.cnpj_orgao)                                                     AS unidades_compradoras,
    ROUND(AVG(f.dias_ciclo), 1)                                                      AS ciclo_medio_dias,
    MAX(f.dias_ciclo)                                                                AS ciclo_maximo_dias
FROM fato_item_contratado AS f
JOIN dim_orgao            AS o ON o.sk_orgao = f.sk_orgao
GROUP BY o.nome_orgao
HAVING COUNT(f.dias_ciclo) >= 5
ORDER BY ciclo_medio_dias DESC;

-- 4b) Visao geral do ciclo (medida de apoio): media, maximo e itens sem ciclo
SELECT
    ROUND(AVG(dias_ciclo), 1)                                                        AS ciclo_medio_dias,
    MAX(dias_ciclo)                                                                  AS ciclo_maximo_dias,
    COUNT(dias_ciclo)                                                                AS itens_com_ciclo,
    COUNT(*) - COUNT(dias_ciclo)                                                     AS itens_sem_ciclo
FROM fato_item_contratado;


-- =====================================================================================================
-- PERGUNTA 5  -  Distribuicao regional
-- Quais estados e regioes concentram as maiores despesas e quais apresentam os melhores indicadores
-- de desconto?
-- =====================================================================================================

-- 5a) Por regiao
SELECT
    l.regiao,
    COUNT(*)                                                                         AS itens,
    COUNT(DISTINCT f.sk_orgao)                                                       AS unidades_compradoras,
    SUM(f.valor_total_homologado)                                                    AS volume_homologado,
    ROUND(100.0 * SUM(f.valor_total_homologado)
          / (SELECT SUM(valor_total_homologado) FROM fato_item_contratado), 2)       AS participacao_volume_pct,
    ROUND(100.0 * SUM(CASE WHEN f.comparavel = 1 THEN f.economia_valor ELSE 0 END)
          / NULLIF(SUM(CASE WHEN f.comparavel = 1 THEN f.valor_total_estimado ELSE 0 END), 0), 2)
                                                                                     AS economia_pct
FROM fato_item_contratado AS f
JOIN dim_localidade       AS l ON l.sk_localidade = f.sk_localidade
GROUP BY l.regiao
ORDER BY volume_homologado DESC;

-- 5b) Por estado (UF)
SELECT
    l.uf_sigla,
    l.uf_nome,
    l.regiao,
    COUNT(*)                                                                         AS itens,
    COUNT(DISTINCT f.sk_orgao)                                                       AS unidades_compradoras,
    SUM(f.valor_total_homologado)                                                    AS volume_homologado,
    ROUND(100.0 * SUM(f.valor_total_homologado)
          / (SELECT SUM(valor_total_homologado) FROM fato_item_contratado), 2)       AS participacao_volume_pct,
    ROUND(100.0 * SUM(CASE WHEN f.comparavel = 1 THEN f.economia_valor ELSE 0 END)
          / NULLIF(SUM(CASE WHEN f.comparavel = 1 THEN f.valor_total_estimado ELSE 0 END), 0), 2)
                                                                                     AS economia_pct
FROM fato_item_contratado AS f
JOIN dim_localidade       AS l ON l.sk_localidade = f.sk_localidade
GROUP BY l.sk_localidade, l.uf_sigla, l.uf_nome, l.regiao
ORDER BY volume_homologado DESC;


-- =====================================================================================================
-- PERGUNTA 6  -  Perfil dos gastos
-- Como os recursos se distribuem entre bens, servicos e obras e engenharia?
-- (perfil_gasto e coluna da propria fato: nao precisa de JOIN)
-- =====================================================================================================
SELECT
    perfil_gasto,
    COUNT(*)                                                                         AS itens,
    SUM(valor_total_homologado)                                                      AS volume_homologado,
    ROUND(100.0 * SUM(valor_total_homologado)
          / (SELECT SUM(valor_total_homologado) FROM fato_item_contratado), 1)       AS participacao_volume_pct,
    ROUND(SUM(valor_total_homologado) / COUNT(*), 2)                                 AS ticket_medio_por_item,
    ROUND(100.0 * SUM(CASE WHEN comparavel = 1 THEN economia_valor ELSE 0 END)
          / NULLIF(SUM(CASE WHEN comparavel = 1 THEN valor_total_estimado ELSE 0 END), 0), 2)
                                                                                     AS economia_pct
FROM fato_item_contratado
GROUP BY perfil_gasto
ORDER BY volume_homologado DESC;


-- =====================================================================================================
-- CONFERENCIA COM A PROVA REAL (anexo 8 do enunciado)
-- Cada linha traz o valor do banco e o valor esperado (em texto, com ponto decimal, para nao depender do idioma
-- do servidor). Pequenas diferencas de centavos sao normais.
-- =====================================================================================================
SELECT  1 AS ordem, 'Itens na fato'                           AS conferencia, COUNT(*)::TEXT                                                           AS no_banco, '6126'            AS esperado FROM fato_item_contratado
UNION ALL
SELECT  2, 'Contratacoes distintas',                 COUNT(DISTINCT numero_controle_pncp)::TEXT,                                              '1962'            FROM fato_item_contratado
UNION ALL
SELECT  3, 'Orgaos (CNPJ) na fato',                  COUNT(DISTINCT sk_orgao)::TEXT,                                                          '363'             FROM fato_item_contratado
UNION ALL
SELECT  4, 'Fornecedores na fato',                   COUNT(DISTINCT sk_fornecedor)::TEXT,                                                     '2652'            FROM fato_item_contratado
UNION ALL
SELECT  5, 'Soma do valor total homologado',         SUM(valor_total_homologado)::TEXT,                                                       '8044498805.74'   FROM fato_item_contratado
UNION ALL
SELECT  6, 'Soma do estimado, todos os itens',       SUM(valor_total_estimado)::TEXT,                                                         '32629639732.13'  FROM fato_item_contratado
UNION ALL
SELECT  7, 'Soma do estimado so da base comparavel', (SUM(valor_total_estimado) FILTER (WHERE comparavel = 1))::TEXT,                         '6867663469.91'   FROM fato_item_contratado
UNION ALL
SELECT  8, 'Itens na base comparavel',               (COUNT(*) FILTER (WHERE comparavel = 1))::TEXT,                                          '5457'            FROM fato_item_contratado
UNION ALL
SELECT  9, 'Economia nominal na base comparavel',    (SUM(economia_valor) FILTER (WHERE comparavel = 1))::TEXT,                               '992861686.95'    FROM fato_item_contratado
UNION ALL
SELECT 10, 'Economia % na base comparavel',          ROUND(100.0 * SUM(economia_valor) FILTER (WHERE comparavel = 1) / SUM(valor_total_estimado) FILTER (WHERE comparavel = 1), 2)::TEXT || '%', '14.46%' FROM fato_item_contratado
UNION ALL
SELECT 11, 'Itens com sobrepreco (homologado > estimado)', (COUNT(*) FILTER (WHERE comparavel = 1 AND valor_total_homologado > valor_total_estimado))::TEXT, '27' FROM fato_item_contratado
UNION ALL
SELECT 12, 'Itens com ciclo valido',                 COUNT(dias_ciclo)::TEXT,                                                                 '5896'            FROM fato_item_contratado
UNION ALL
SELECT 13, 'Ciclo medio (dias)',                     ROUND(AVG(dias_ciclo), 1)::TEXT,                                                         '48.1'            FROM fato_item_contratado
UNION ALL
SELECT 14, 'Ciclo maximo (dias)',                    MAX(dias_ciclo)::TEXT,                                                                   '611'             FROM fato_item_contratado
UNION ALL
SELECT 15, 'Itens sem ciclo',                        (COUNT(*) - COUNT(dias_ciclo))::TEXT,                                                    '230'             FROM fato_item_contratado
ORDER BY ordem;