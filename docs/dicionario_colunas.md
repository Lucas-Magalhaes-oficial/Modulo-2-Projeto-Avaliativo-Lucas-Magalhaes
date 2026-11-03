# Dicionário das colunas dos dados brutos (Sprint 0)

Os 3 CSVs de `data/raw/` (separador vírgula, UTF-8) vêm do PNCP, são lidos como texto e convertidos por nós. A ligação é `compras (1) → itens (N) → resultados (N)`, pela chave `numero_controle_pncp` + `numero_item`. O **grão da fato** é o item de contratação.

- **Tipo após a limpeza:** o tipo que a coluna terá depois do tratamento em Python.
- **Preenchimento:** porcentagem de linhas não vazias **antes** da limpeza (nulos disfarçados, como `N/A`, ainda contam como preenchidos; veja `reports/auditoria.md`).
- **Exemplo:** primeiro valor preenchido do arquivo, exatamente como veio (cortado em 40 caracteres).

## compras.csv: uma linha por contratação (o "edital")

2.042 linhas e 25 colunas; 10 entram no pipeline e 15 não são usadas.

| Coluna | Significado | Tipo após a limpeza | Uso no pipeline | Preenchimento | Exemplo |
|---|---|---|---|---|---|
| `numero_controle_pncp` | Identificador da contratação (o "edital"). É a chave que liga compras, itens e resultados. | texto | Chave de ligação; entra na chave da fato | 100,0% | `00889834000108-1-000053/2023` |
| `ano_compra` | Ano do número da compra. Pode ser anterior a 2025; **não** é a data de publicação. | inteiro | Não usada | 100,0% | `2023` |
| `sequencial_compra` | Numeração sequencial da contratação. | inteiro | Não usada | 100,0% | `53` |
| `numero_compra` | Número da compra em texto livre (ex.: `PE 009/2024`). | texto | Não usada | 100,0% | `90037` |
| `processo` | Número do processo administrativo. Traz placeholders como `0` e `-`. | texto | Não usada | 100,0% | `0` |
| `objeto_compra` | Descrição do que se está comprando. Tem acento quebrado em alguns registros. | texto | Ajuda a classificar o perfil do gasto (regra 8) | 100,0% | `Contratação de serviços continuados de c…` |
| `srp` | Verdadeiro/falso: Sistema de Registro de Preços, que gera vários classificados por item. | verdadeiro/falso | Não usada direto (o efeito aparece nos resultados) | 100,0% | `False` |
| `cnpj_orgao` | CNPJ do órgão que comprou. Chega com máscara ou sem zero à esquerda. | documento (14 dígitos) | `dim_orgao.cnpj_orgao` (chave natural) | 100,0% | `00889834000108` |
| `razao_social_orgao` | Nome do órgão. O mesmo órgão aparece escrito de jeitos diferentes. | texto padronizado | `dim_orgao.nome_orgao` (regra 10) | 100,0% | `FUND COORD DE APERFEICOAMENTO DE PESSOAL…` |
| `poder_id` | Poder do órgão: E = Executivo, L = Legislativo, J = Judiciário, N = não informado. | texto | `dim_orgao.poder` (nome por extenso) | 100,0% | `E` |
| `esfera_id` | Esfera do órgão: `F` (federal) em todos os registros. | texto | Não usada | 100,0% | `F` |
| `uf_sigla` | Sigla da UF da unidade compradora. | texto | `dim_localidade.uf_sigla` (chave natural) e região (regra 11) | 100,0% | `DF` |
| `uf_nome` | Nome da UF. | texto padronizado | `dim_localidade.uf_nome` | 100,0% | `Distrito Federal` |
| `municipio` | Município da unidade compradora. | texto | Não usada | 100,0% | `Brasília` |
| `cod_ibge` | Código IBGE do município. | texto | Não usada | 100,0% | `5300108` |
| `nome_unidade` | Nome da unidade compradora. | texto padronizado | Não usada na modelagem | 100,0% | `MEC-FUCAPES-FUND.COORD.DE AP.NIV.SUPERIO…` |
| `modalidade_id` | Código da modalidade (4, 5, 6, 7, 8, 9 ou 12). É a chave; o nome vem da tabela do anexo 7.5. | inteiro | `dim_modalidade.modalidade_id` (chave natural) | 100,0% | `5` |
| `modalidade_nome` | Nome da modalidade como veio; o nome padronizado é montado a partir do id. | texto | Substituída pelo nome padronizado (regra 9) | 100,0% | `Concorrência - Presencial` |
| `modo_disputa` | Modo de disputa do certame (14 grafias distintas). | texto | Não usada | 100,0% | `Fechado` |
| `situacao_compra` | Situação da contratação (ex.: Divulgada no PNCP, Revogada). | texto | Não usada | 100,0% | `Divulgada no PNCP` |
| `valor_total_estimado` | Total estimado da **contratação**. Não serve para a fato, porque o grão é o item. | decimal | Não usada (a fato recalcula por item) | 100,0% | `20307804.45` |
| `valor_total_homologado` | Total homologado da **contratação**. Não serve para a fato, porque o grão é o item. | decimal | Não usada (a fato recalcula por item) | 100,0% | `19.290.383,46` |
| `data_publicacao` | Quando o edital foi publicado, em 6 formatos de escrita. | data | `fato.data_publicacao`; base do ciclo (regra 7) | 100,0% | `2025-01-06T11:51:06` |
| `data_abertura_proposta` | Início da janela de propostas. | data | Não usada | 69,8% | `06.03.2025` |
| `data_encerramento_proposta` | Fim da janela de propostas. Tem anos impossíveis (2034 a 9999). | data | Não usada | 69,8% | `30.04.2025` |

## itens.csv: uma linha por item licitado

7.077 linhas e 14 colunas; 8 entram no pipeline e 6 não são usadas.

| Coluna | Significado | Tipo após a limpeza | Uso no pipeline | Preenchimento | Exemplo |
|---|---|---|---|---|---|
| `numero_controle_pncp` | Contratação a que o item pertence. | texto | Chave do item (com `numero_item`) | 100,0% | `00889834000108-1-000053/2023` |
| `numero_item` | Número do item dentro da contratação. | inteiro | Chave do item (com `numero_controle_pncp`) | 100,0% | `1` |
| `descricao` | O que é o item. Tem acento quebrado e espaços sobrando. | texto padronizado | `fato.descricao_item`; entra no perfil do gasto | 100,0% | `Resenha de Notícia / Agenciamento de Inf…` |
| `material_ou_servico` | Classificação do item: Material ou Serviço. | texto | Base do perfil do gasto (regra 8) | 100,0% | `Serviço` |
| `categoria_item` | Vem **sempre** como "Não se aplica", então não ajuda. | texto | Não usada | 100,0% | `Não se aplica` |
| `quantidade` | Quantidade licitada do item. | decimal | `fato.quantidade` quando a homologada vem vazia ou zero (regra 5) | 100,0% | `3.0` |
| `unidade_medida` | Unidade do item, com grafias variadas e valores estranhos (ex.: `UNIDADE 0,00`). | texto | Não usada | 99,9% | `UNIDADE` |
| `valor_unitario_estimado` | O que o governo esperava pagar por unidade. | decimal | `fato.valor_unitario_estimado` | 100,0% | `6769268.15` |
| `valor_total_estimado` | Total estimado do item como veio. O valor da fato é recalculado: unitário × quantidade. | decimal | Recalculado (regra 5) | 100,0% | `20.307.804,45` |
| `sigiloso` | Verdadeiro/falso: orçamento sigiloso (sem estimado utilizável). | verdadeiro/falso | Item sigiloso é rejeitado (regra 4) | 100,0% | `False` |
| `situacao_item` | Situação do item (13 valores distintos). | texto | Não usada | 100,0% | `Homologado` |
| `tem_resultado` | Verdadeiro/falso: o item tem fornecedor vencedor. A auditoria mostrou 0 divergências com os resultados válidos. | verdadeiro/falso | Não usada direto: a regra 3 decide pela existência de resultado válido | 100,0% | `True` |
| `catalogo_codigo_item` | Código do catálogo oficial. Quase sempre vazio. | texto | Não usada | 0,1% | `2` |
| `criterio_julgamento` | Critério de julgamento (ex.: Menor preço, Técnica e preço). | texto | Não usada | 100,0% | `Melhor técnica` |

## resultados.csv: uma linha por fornecedor classificado em cada item

15.896 linhas e 13 colunas; 13 entram no pipeline e 0 não são usadas.

| Coluna | Significado | Tipo após a limpeza | Uso no pipeline | Preenchimento | Exemplo |
|---|---|---|---|---|---|
| `numero_controle_pncp` | Contratação a que o resultado pertence. | texto | Chave do item (com `numero_item`) | 100,0% | `00889834000108-1-000053/2023` |
| `numero_item` | Item ao qual o resultado pertence. | inteiro | Chave do item (com `numero_controle_pncp`) | 100,0% | `1` |
| `sequencial_resultado` | Número de sequência do resultado; serve para **desempatar** (lido como número: 2 vem antes de 10). | inteiro | Escolha do vencedor (regra 2) | 100,0% | `1` |
| `ordem_classificacao_srp` | Posição no ranking: 1 = vencedor; **vazio vale 1**. | inteiro | Escolha do vencedor (regra 2) | 24,7% | `1.0` |
| `ni_fornecedor` | CNPJ ou CPF do fornecedor. Chega com máscara ou sem zero à esquerda. | documento (14 ou 11 dígitos) | `dim_fornecedor.ni_fornecedor` (chave natural) | 100,0% | `51.593.855/0001-04` |
| `tipo_pessoa` | PJ, PF ou PE (estrangeiro). Define o tamanho do documento. | texto | `dim_fornecedor.tipo_pessoa` | 100,0% | `PJ` |
| `nome_fornecedor` | Nome do fornecedor, em grafias diferentes. | texto padronizado | `dim_fornecedor.nome_fornecedor` | 100,0% | `CRIATIVA DIGITAL COMUNICACOES LTDA` |
| `porte` | Porte da empresa (ME, EPP, Demais). Muitas linhas vêm como "Não informado". | texto | `dim_fornecedor.porte` | 100,0% | `Demais` |
| `quantidade_homologada` | Quantidade efetivamente comprada. | decimal | `fato.quantidade` (regra 5) | 100,0% | `R$ 3,00` |
| `valor_unitario_homologado` | O que o governo pagou por unidade. | decimal | `fato.valor_unitario_homologado` | 100,0% | `6.430.127,82` |
| `valor_total_homologado` | Total homologado como veio. O valor da fato é recalculado: unitário × quantidade. | decimal | Recalculado (regra 5) | 100,0% | `19290383.46` |
| `data_resultado` | Data da homologação, em 6 formatos de escrita. | data | `fato.data_homologacao` (regra 7) | 100,0% | `10/03/2026 00:00` |
| `data_cancelamento` | Preenchida = resultado cancelado. | data | Descarta o resultado antes de escolher o vencedor (regra 2) | 0,4% | `2025-10-31T00:00:00` |