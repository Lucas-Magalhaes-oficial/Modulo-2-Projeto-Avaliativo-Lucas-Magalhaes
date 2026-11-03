# Auditoria dos dados brutos (Sprint 1)

Relatório gerado por `python -m src.auditoria`, lendo `data/raw/` sem alterar nada. "Linhas" são linhas do arquivo; "células" são valores individuais (uma linha pode ter vários).

## Resumo: dicionário das inconsistências

| # | Inconsistência | Onde | Ocorrências | Como será tratada |
|---|---|---|---|---|
| 1 | Máscara no CNPJ do órgão | compras.cnpj_orgao | 176 linhas | limpar_documento: manter só os dígitos (desafio 1) |
| 2 | Zero à esquerda perdido no CNPJ do órgão | compras.cnpj_orgao | 77 linhas | limpar_documento: completar com zeros até 14 dígitos (desafio 1) |
| 3 | Máscara no CPF/CNPJ do fornecedor | resultados.ni_fornecedor | 1.631 linhas | limpar_documento: manter só os dígitos (desafio 1) |
| 4 | Zero à esquerda perdido no CPF/CNPJ do fornecedor | resultados.ni_fornecedor | 353 linhas | limpar_documento: zeros até 14 (PJ) ou 11 (PF) dígitos (desafio 1) |
| 5 | Valores com "R$" | colunas de dinheiro e quantidade | 12.055 células | converter_numero: tirar o R$ antes de converter (desafio 2) |
| 6 | Espaço sem quebra ou invisível dentro de números | colunas de dinheiro e quantidade | 3.051 células | converter_numero: ignorar qualquer espaço (desafio 2) |
| 7 | Números negativos (sinal ou parênteses) | colunas de dinheiro e quantidade | 0 células | converter_numero: aplicar o sinal depois de converter (desafio 2) |
| 8 | Vírgula como decimal (formato brasileiro) | colunas de dinheiro e quantidade | 15.175 células | converter_numero: ponto de milhar sai, vírgula vira ponto (regra 12) |
| 9 | Vírgula como milhar (formato americano) | colunas de dinheiro e quantidade | 1.468 células | converter_numero: vírgula de milhar sai (regra 12) |
| 10 | Ponto ou vírgula sozinho com 3 casas (parece milhar, mas é decimal) | colunas de dinheiro e quantidade | 137 células | converter_numero: separador sozinho é sempre decimal (regra 12) |
| 11 | Datas escritas em vários formatos | 5 colunas de data | 10.549 células fora do AAAA-MM-DD simples (hora ou outro formato) | converter_data: testa cada formato da lista FORMATOS_DATA (desafio 3) |
| 12 | Datas com ano impossível (2034 a 9999), que não viram data válida | data_encerramento_proposta | 65 células | converter_data: devolve vazio (None) quando o ano está fora de 2000–2030 (coluna fora do modelo) |
| 13 | Homologação anterior à publicação (impossível) | resultados.data_resultado × compras.data_publicacao | 234 linhas de resultado | montar_tabelas, regra 7: anular data de homologação e ciclo; o item continua na fato |
| 14 | Nulos disfarçados (N/A, NULL, -, SEM INFORMAÇÃO, NÃO SE APLICA...) | todas as colunas | 15.016 células | eh_nulo / limpar_texto: viram vazio (None) (desafio 4) |
| 15 | "0" usado como nulo em campo de texto | colunas de texto | 101 células | limpar_texto(zero_eh_nulo=True); em quantidade e valores o 0 continua sendo número (desafio 4) |
| 16 | Acento quebrado (AquisiÃ§Ã£o) | colunas de texto | 202 células | consertar_acento: refaz a leitura Latin-1 → UTF-8 (desafio 5) |
| 17 | Espaço sem quebra ou caractere invisível | colunas de texto e de documento | 1.963 células | remover_invisiveis + tirar_espacos (desafio 5) |
| 18 | Espaços nas pontas ou repetidos | colunas de texto e de documento | 3.774 células | tirar_espacos: uma palavra por vez, um espaço entre elas (desafio 5) |
| 19 | Mesmo CNPJ de órgão com o nome escrito de jeitos diferentes | compras.razao_social_orgao | 67 CNPJs com mais de uma grafia → 0 depois de padronizar | padronizar_nome: maiúsculas, acento e espaços; o ranking agrupa pelo nome padronizado (regra 10) |
| 20 | Mesmo fornecedor com portes diferentes ou porte em branco em algumas linhas | resultados.porte | 61 documentos com conflito; 194 com porte a completar | montar_tabelas: uma linha por documento, com o porte mais frequente entre os preenchidos |
| 21 | Mesmo fornecedor com nomes diferentes depois de padronizar | resultados.nome_fornecedor | 16 documentos | montar_tabelas: uma linha por documento, com o nome mais frequente |
| 22 | Resultados cancelados no meio dos classificados | resultados.data_cancelamento | 62 linhas | montar_tabelas, regra 2: descartar os cancelados ANTES de escolher o 1º colocado |
| 23 | Itens sem resultado homologado | itens × resultados | 852 itens | montar_tabelas, regra 3: ficam fora da fato (não contam como rejeitados) |
| 24 | Empate na melhor posição (Credenciamento e outros) | resultados.ordem_classificacao_srp | 405 itens | montar_tabelas, regra 2: vale o menor sequencial_resultado, lido como número |

## 1. Visão geral e relacionamento entre os arquivos

| Arquivo | Linhas | Colunas | Chave | Chaves repetidas |
|---|---|---|---|---|
| compras.csv | 2.042 | 25 | numero_controle_pncp | 0 |
| itens.csv | 7.077 | 14 | numero_controle_pncp + numero_item | 0 |
| resultados.csv | 15.896 | 13 | numero_controle_pncp + numero_item + sequencial_resultado | 0 |

| Verificação de relacionamento | Ocorrências |
|---|---|
| itens sem contratação correspondente em compras | 0 |
| resultados sem item correspondente em itens | 0 |
| contratações de compras sem nenhum item | 0 |

## 2. Documentos (CNPJ/CPF): máscara e zeros perdidos

**compras.cnpj_orgao** (a limpeza deixa só dígitos e completa para 14 com zeros à esquerda)

| Linhas | Com máscara (pontos, barra, traço) | Zero à esquerda perdido (menos de 14 dígitos) | Com 14 dígitos | Com mais de 14 | CNPJs distintos antes → depois |
|---|---|---|---|---|---|
| 2.042 | 176 | 77 | 1.965 | 0 | 476 → 370 |

**resultados.ni_fornecedor** por tipo de pessoa (PJ = 14 dígitos, PF = 11; PE não tem formato fixo)

| tipo_pessoa | Linhas | Com máscara | Zero à esquerda perdido | Tamanho correto | Maior que o esperado | Documentos distintos antes → depois |
|---|---|---|---|---|---|---|
| PE (estrangeiro) | 21 | - | - | - | - | 13 (sem padrão: mantido como veio) |
| PF | 4.531 | 392 | 159 | 4.372 | 0 | 3.957 → 3.832 |
| PJ | 11.344 | 1.239 | 194 | 11.150 | 0 | 7.054 → 6.454 |

## 3. Dinheiro e quantidades: formatos de número

| Coluna | Preenchidos | Com "R$" | Espaço invisível | Negativos | 3 casas (parece milhar) | Formatos encontrados |
|---|---|---|---|---|---|---|
| compras.valor_total_estimado | 2.042 | 344 | 86 | 0 | 0 | ponto decimal (1234.56): 1.533; formato BR com milhar (1.234.567,89): 403; formato US com milhar (1,234,567.89): 64; virgula decimal (1234,56): 42 |
| compras.valor_total_homologado | 2.042 | 346 | 77 | 0 | 0 | ponto decimal (1234.56): 1.523; formato BR com milhar (1.234.567,89): 406; formato US com milhar (1,234,567.89): 77; virgula decimal (1234,56): 36 |
| itens.quantidade | 7.077 | 1.148 | 264 | 0 | 0 | ponto decimal (1234.56): 5.596; virgula decimal (1234,56): 1.262; formato BR com milhar (1.234.567,89): 185; formato US com milhar (1,234,567.89): 34 |
| itens.valor_unitario_estimado | 7.077 | 1.188 | 301 | 0 | 31 | ponto decimal (1234.56): 5.475; virgula decimal (1234,56): 953; formato BR com milhar (1.234.567,89): 536; formato US com milhar (1,234,567.89): 113 |
| itens.valor_total_estimado | 7.077 | 1.171 | 299 | 0 | 9 | ponto decimal (1234.56): 5.415; formato BR com milhar (1.234.567,89): 1.103; virgula decimal (1234,56): 359; formato US com milhar (1,234,567.89): 200 |
| resultados.quantidade_homologada | 15.896 | 2.561 | 622 | 0 | 0 | ponto decimal (1234.56): 12.472; virgula decimal (1234,56): 2.245; formato BR com milhar (1.234.567,89): 974; formato US com milhar (1,234,567.89): 205 |
| resultados.valor_unitario_homologado | 15.896 | 2.650 | 704 | 0 | 80 | ponto decimal (1234.56): 12.282; virgula decimal (1234,56): 2.077; formato BR com milhar (1.234.567,89): 1.279; formato US com milhar (1,234,567.89): 258 |
| resultados.valor_total_homologado | 15.896 | 2.647 | 698 | 0 | 17 | ponto decimal (1234.56): 12.064; formato BR com milhar (1.234.567,89): 2.625; virgula decimal (1234,56): 690; formato US com milhar (1,234,567.89): 517 |

Regra desta base (regra 12): um ponto ou uma vírgula **sozinho** é sempre o decimal (`746.815` vale 746,815). Só o separador repetido (`1.234.567`) é milhar; quando aparecem os dois símbolos, o último é o decimal.

## 4. Datas: formatos e cronologia

| Coluna | Preenchidas | Formatos distintos | Não convertíveis | Formatos encontrados |
|---|---|---|---|---|
| compras.data_publicacao | 2.042 | 6 | 0 | AAAA-MM-DD com hora (2025-01-06T11:51:06): 1.319; DD/MM/AAAA, com ou sem hora (02/01/2025 09:03): 243; DD-MM-AAAA (06-03-2025): 138; DD.MM.AAAA (06.03.2025): 120; AAAA/MM/DD (2025/03/06): 116; AAAAMMDD (20250102): 106 |
| compras.data_abertura_proposta | 1.425 | 6 | 0 | AAAA-MM-DD com hora (2025-01-06T11:51:06): 912; DD/MM/AAAA, com ou sem hora (02/01/2025 09:03): 164; AAAAMMDD (20250102): 95; AAAA/MM/DD (2025/03/06): 86; DD-MM-AAAA (06-03-2025): 85; DD.MM.AAAA (06.03.2025): 83 |
| compras.data_encerramento_proposta | 1.425 | 6 | 65 | AAAA-MM-DD com hora (2025-01-06T11:51:06): 926; DD/MM/AAAA, com ou sem hora (02/01/2025 09:03): 179; DD.MM.AAAA (06.03.2025): 84; AAAAMMDD (20250102): 83; AAAA/MM/DD (2025/03/06): 78; DD-MM-AAAA (06-03-2025): 75 |
| resultados.data_resultado | 15.896 | 6 | 0 | AAAA-MM-DD (2025-10-31): 10.301; DD/MM/AAAA, com ou sem hora (02/01/2025 09:03): 1.863; AAAA/MM/DD (2025/03/06): 960; DD.MM.AAAA (06.03.2025): 937; AAAAMMDD (20250102): 923; DD-MM-AAAA (06-03-2025): 912 |
| resultados.data_cancelamento | 62 | 1 | 0 | AAAA-MM-DD com hora (2025-01-06T11:51:06): 62 |

| Cronologia | Ocorrências |
|---|---|
| resultados com data_resultado ANTERIOR à data_publicacao da contratação | 234 linhas |
| resultados sem data_resultado | 0 linhas |
| resultados homologados em 2026 (o Calendário precisa cobrir 2025 e 2026) | 3.819 linhas |
| contratações com data_publicacao fora de 2025 | 0 contratações |

## 5. Nulos disfarçados e zeros

| Coluna | Vazios | Nulos disfarçados (N/A, -, SEM INFORMAÇÃO...) | Valor "0" | "0" é nulo? |
|---|---|---|---|---|
| compras.processo | 0 | 65 | 12 | sim (campo de texto) |
| compras.modo_disputa | 0 | 960 | 7 | sim (campo de texto) |
| compras.data_abertura_proposta | 617 | 0 | 0 | sim (campo de texto) |
| compras.data_encerramento_proposta | 617 | 0 | 0 | sim (campo de texto) |
| itens.categoria_item | 0 | 7.077 | 0 | sim (campo de texto) |
| itens.unidade_medida | 9 | 0 | 0 | sim (campo de texto) |
| itens.situacao_item | 0 | 195 | 25 | sim (campo de texto) |
| itens.catalogo_codigo_item | 7.068 | 0 | 0 | sim (campo de texto) |
| itens.criterio_julgamento | 0 | 1.883 | 0 | sim (campo de texto) |
| resultados.ordem_classificacao_srp | 11.976 | 0 | 0 | sim (campo de texto) |
| resultados.porte | 0 | 4.836 | 57 | sim (campo de texto) |
| resultados.data_cancelamento | 15.834 | 0 | 0 | sim (campo de texto) |

## 6. Texto: acento quebrado e espaços

| Coluna | Acento quebrado | Espaço sem quebra | Invisível (largura zero) | Espaço nas pontas | Espaços repetidos |
|---|---|---|---|---|---|
| compras.processo | 0 | 0 | 0 | 46 | 8 |
| compras.objeto_compra | 43 | 64 | 1 | 264 | 317 |
| compras.cnpj_orgao | 0 | 131 | 0 | 131 | 0 |
| compras.razao_social_orgao | 0 | 53 | 0 | 53 | 58 |
| compras.municipio | 28 | 55 | 0 | 55 | 55 |
| compras.nome_unidade | 14 | 49 | 0 | 49 | 63 |
| compras.valor_total_estimado | 0 | 86 | 0 | 172 | 0 |
| compras.valor_total_homologado | 0 | 77 | 0 | 153 | 0 |
| itens.descricao | 116 | 196 | 0 | 295 | 458 |
| itens.quantidade | 0 | 264 | 0 | 551 | 0 |
| itens.unidade_medida | 0 | 0 | 0 | 935 | 858 |
| itens.valor_unitario_estimado | 0 | 301 | 0 | 561 | 0 |
| itens.valor_total_estimado | 0 | 299 | 0 | 588 | 0 |
| resultados.ni_fornecedor | 0 | 990 | 0 | 990 | 0 |
| resultados.nome_fornecedor | 1 | 424 | 0 | 437 | 488 |
| resultados.quantidade_homologada | 0 | 622 | 0 | 1.267 | 0 |
| resultados.valor_unitario_homologado | 0 | 704 | 0 | 1.352 | 0 |
| resultados.valor_total_homologado | 0 | 698 | 0 | 1.332 | 0 |

## 7. Nomes: órgãos, fornecedores e unidades

**Órgãos** (o mesmo órgão tem várias unidades, com CNPJ diferente, e nomes escritos de jeitos diferentes)

| Verificação | Quantidade |
|---|---|
| CNPJs de órgão distintos (depois de limpar a máscara e os zeros) | 370 |
| nomes de órgão distintos, como vieram | 440 |
| nomes de órgão distintos, depois de maiúsculas, espaços e acento | 352 |
| CNPJs com mais de uma grafia de nome, como vieram | 67 |
| CNPJs com mais de um nome depois de padronizar | 0 |

**Fornecedores**

| Verificação | Quantidade |
|---|---|
| fornecedores distintos (documento limpo) | 10.299 |
| documentos com mais de uma grafia de nome, como vieram | 490 |
| documentos com mais de um nome depois de padronizar | 16 |
| documentos com portes preenchidos DIFERENTES entre si (conflito real) | 61 |
| documentos com porte em branco em algumas linhas e preenchido em outras | 194 |
| documentos sem nenhum porte preenchido ('Não informado' ou vazio) | 3.986 |

**itens.unidade_medida** (grafias variadas e valores estranhos como `UNIDADE 0,00`; a coluna não entra no modelo, então fica só registrada)

| Verificação | Quantidade |
|---|---|
| valores distintos, como vieram | 344 |
| valores distintos depois de maiúsculas e espaços | 340 |

## 8. Armadilhas das regras de negócio

| Verificação | Ocorrências |
|---|---|
| resultados cancelados (data_cancelamento preenchida) | 62 linhas |
| itens sem nenhum resultado válido (descartados pela regra 3) | 852 itens |
| ... dos quais a flag tem_resultado diz True (só têm resultados cancelados) | 0 itens |
| ... dos quais a flag tem_resultado diz False | 852 itens |
| itens marcados tem_resultado = False, mas com resultado válido | 0 itens |
| itens com mais de um classificado válido (Registro de Preços) | 405 itens |
| itens com empate na melhor posição (precisa do menor sequencial_resultado) | 405 itens |
| resultados com ordem_classificacao_srp vazia (vale 1) | 11.976 linhas |
| resultados com sequencial_resultado de 10 ou mais (a ordem tem que ser numérica) | 7.842 linhas |
| itens de contratações em Credenciamento (modalidade 12; fora da economia) | 819 itens |
| itens com orçamento sigiloso (sigiloso = True) | 54 itens |
| valores de modalidade_nome por modalidade_id (se > 1, o nome varia) | 1 no máximo |