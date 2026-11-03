# Medidas DAX e tabela Calendário (Power BI)

Este documento reúne o modelo do dashboard (`powerbi/`): a tabela Calendário e as 15 medidas obrigatórias, mais as medidas extras. Os números de conferência são os mesmos do `sql/02_perguntas.sql`.

## Modelo

| Tabela | Papel | Relacionamento |
|---|---|---|
| `fato_item_contratado` | Fato (uma linha por item de contratação) | recebe as 4 dimensões e o Calendário |
| `dim_orgao`, `dim_fornecedor`, `dim_modalidade`, `dim_localidade` | Dimensões | 1:N para a fato, filtro da dimensão para a fato, pela chave substituta `sk_...` |
| `Calendario` | Dimensão de tempo, criada em DAX | `Data` → `data_publicacao` (ativa) e `Data` → `data_homologacao` (inativa, usada com `USERELATIONSHIP`) |
| `Medidas` | Tabela só com as medidas (sem soma implícita arrastando coluna) | nenhum |

## Tabela Calendário

Os limites vêm dos dados (menor e maior data da fato), não são digitados. Cobre os anos inteiros de 2025 e 2026, porque há homologações em 2026.

```dax
Calendario =
VAR _inicio = MIN ( MIN ( fato_item_contratado[data_publicacao] ), MIN ( fato_item_contratado[data_homologacao] ) )
VAR _fim    = MAX ( MAX ( fato_item_contratado[data_publicacao] ), MAX ( fato_item_contratado[data_homologacao] ) )
RETURN
    SELECTCOLUMNS (
        CALENDAR ( DATE ( YEAR ( _inicio ), 1, 1 ), DATE ( YEAR ( _fim ), 12, 31 ) ),
        "Data", [Date],
        "Ano", YEAR ( [Date] ),
        "Mês Número", MONTH ( [Date] ),
        "Mês", FORMAT ( [Date], "mmmm" ),
        "Mês Abreviado", FORMAT ( [Date], "mmm" ),
        "AnoMês", YEAR ( [Date] ) * 100 + MONTH ( [Date] ),
        "Ano-Mês", FORMAT ( [Date], "yyyy-mm" )
    )
```

Ajustes depois de criar a tabela:

- Coluna `Mês`: classificar por `Mês Número`. Coluna `Mês Abreviado`: classificar por `Mês Número`. Coluna `Ano-Mês`: classificar por `AnoMês`.
- Marcar como tabela de datas, usando a coluna `Data`.
- Relacionamentos: `Calendario[Data]` → `fato_item_contratado[data_publicacao]` (ativo) e `Calendario[Data]` → `fato_item_contratado[data_homologacao]` (inativo).
- Desligar a hierarquia automática de data (Arquivo → Opções → Arquivo atual → Carregamento de dados → Hora/data automática).

## As 15 medidas obrigatórias

Pasta de exibição entre parênteses. Formato entre colchetes.

### P1 Economia

**1. Valor Estimado Comparável** (moeda R$)

```dax
Valor Estimado Comparável =
CALCULATE (
    SUM ( fato_item_contratado[valor_total_estimado] ),
    fato_item_contratado[comparavel] = 1
)
```

**2. Volume Homologado** (moeda R$)

```dax
Volume Homologado =
SUM ( fato_item_contratado[valor_total_homologado] )
```

**3. Economia (R$)** (moeda R$)

```dax
Economia (R$) =
VAR _estimado   = [Valor Estimado Comparável]
VAR _homologado = CALCULATE ( [Volume Homologado], fato_item_contratado[comparavel] = 1 )
RETURN
    _estimado - _homologado
```

**4. Economia %** (porcentagem, 2 casas)

```dax
Economia % =
DIVIDE ( [Economia (R$)], [Valor Estimado Comparável] )
```

**5. % de Itens Comparáveis** (porcentagem, 2 casas)

```dax
% de Itens Comparáveis =
DIVIDE (
    CALCULATE ( COUNTROWS ( fato_item_contratado ), fato_item_contratado[comparavel] = 1 ),
    COUNTROWS ( fato_item_contratado )
)
```

### P2 Fornecedores

**6. Participação do Fornecedor %** (porcentagem, 2 casas)

```dax
Participação do Fornecedor % =
VAR _volumeFornecedor = [Volume Homologado]
VAR _volumeTotal      = CALCULATE ( [Volume Homologado], ALL ( dim_fornecedor ) )
RETURN
    DIVIDE ( _volumeFornecedor, _volumeTotal )
```

**7. Ranking do Fornecedor** (número inteiro)

```dax
Ranking do Fornecedor =
IF (
    ISBLANK ( [Volume Homologado] ),
    BLANK (),
    RANKX ( ALL ( dim_fornecedor ), [Volume Homologado], , DESC )
)
```

**8. Concentração Top 10 %** (porcentagem, 2 casas). Use em cartão, sem filtro de fornecedor.

```dax
Concentração Top 10 % =
VAR _volumeTop10 =
    CALCULATE (
        [Volume Homologado],
        KEEPFILTERS ( TOPN ( 10, ALL ( dim_fornecedor ), [Volume Homologado], DESC ) )
    )
VAR _volumeTotal = CALCULATE ( [Volume Homologado], ALL ( dim_fornecedor ) )
RETURN
    DIVIDE ( _volumeTop10, _volumeTotal )
```

### P3 Modalidades

**9. Participação no Volume %** (porcentagem, 2 casas). Funciona em qualquer linha: modalidade, região, UF ou perfil.

```dax
Participação no Volume % =
DIVIDE (
    [Volume Homologado],
    CALCULATE ( [Volume Homologado], ALLSELECTED () )
)
```

**10. Deságio vs Média Geral (p.p.)** (número decimal, 1 casa, nunca formatar como %)

```dax
Deságio vs Média Geral (p.p.) =
VAR _atual = [Economia %]
VAR _geral = CALCULATE ( [Economia %], REMOVEFILTERS () )
RETURN
    IF ( ISBLANK ( _atual ), BLANK (), ( _atual - _geral ) * 100 )
```

### P4 Ciclo

**11. Ciclo Médio (dias)** (número decimal, 1 casa)

```dax
Ciclo Médio (dias) =
AVERAGE ( fato_item_contratado[dias_ciclo] )
```

**12. Ciclo Máximo (dias)** (número inteiro)

```dax
Ciclo Máximo (dias) =
MAX ( fato_item_contratado[dias_ciclo] )
```

**13. Itens sem Ciclo** (número inteiro)

```dax
Itens sem Ciclo =
VAR _total    = COUNTROWS ( fato_item_contratado )
VAR _comCiclo = COUNT ( fato_item_contratado[dias_ciclo] )
RETURN
    _total - _comCiclo
```

### P5 Regional

**14. Qtd Unidades Compradoras** (número inteiro). Conta na fato, porque o filtro de região ou UF chega até a fato e não até `dim_orgao`.

```dax
Qtd Unidades Compradoras =
DISTINCTCOUNT ( fato_item_contratado[sk_orgao] )
```

### P6 Perfil

**15. Ticket Médio por Item (R$)** (moeda R$)

```dax
Ticket Médio por Item (R$) =
DIVIDE ( [Volume Homologado], COUNTROWS ( fato_item_contratado ) )
```

## Medidas extras

**Itens com Sobrepreço** (pasta P1 Economia). Itens comparáveis em que o homologado ficou acima do estimado.

```dax
Itens com Sobrepreço =
COUNTROWS (
    FILTER (
        fato_item_contratado,
        fato_item_contratado[comparavel] = 1
            && fato_item_contratado[valor_total_homologado] > fato_item_contratado[valor_total_estimado]
    )
)
```

**Economia Média por Item (R$)** (pasta P1 Economia). Usa uma função iteradora (`AVERAGEX`).

```dax
Economia Média por Item (R$) =
AVERAGEX (
    FILTER ( fato_item_contratado, fato_item_contratado[comparavel] = 1 ),
    fato_item_contratado[economia_valor]
)
```

**Volume por Data de Homologação** (pasta P4 Ciclo). Mostra o uso de `USERELATIONSHIP`: usa a relação inativa do Calendário com `data_homologacao`.

```dax
Volume por Data de Homologação =
CALCULATE (
    [Volume Homologado],
    USERELATIONSHIP ( Calendario[Data], fato_item_contratado[data_homologacao] )
)
```

**Variação Mensal %** (pasta Extras, porcentagem). Volume do mês contra o mês anterior.

```dax
Variação Mensal % =
VAR _atual    = [Volume Homologado]
VAR _anterior = CALCULATE ( [Volume Homologado], DATEADD ( Calendario[Data], -1, MONTH ) )
RETURN
    DIVIDE ( _atual - _anterior, _anterior )
```

**Volume Acumulado no Ano** (pasta Extras, moeda R$).

```dax
Volume Acumulado no Ano =
CALCULATE ( [Volume Homologado], DATESYTD ( Calendario[Data] ) )
```

## Conferência: valores esperados (sem nenhum filtro, em cartões)

| Medida | Valor esperado |
|---|---|
| Valor Estimado Comparável | R$ 6.867.663.469,91 |
| Volume Homologado | R$ 8.044.498.805,74 |
| Economia (R$) | R$ 992.861.686,95 |
| Economia % | 14,46% |
| % de Itens Comparáveis | 89,08% |
| Concentração Top 10 % | 41,43% |
| Ciclo Médio (dias) | 48,1 |
| Ciclo Máximo (dias) | 611 |
| Itens sem Ciclo | 230 |
| Qtd Unidades Compradoras | 363 |
| Ticket Médio por Item (R$) | R$ 1.313.173,16 |
| Itens com Sobrepreço | 27 |
| Economia Média por Item (R$) | R$ 181.942,77 |

Conferência por linha, em tabelas ou gráficos:

| Onde | Medida | Valor esperado |
|---|---|---|
| Fornecedor NOW SEGUROS SA | Participação do Fornecedor % | 13,18% |
| Fornecedor NOW SEGUROS SA | Ranking do Fornecedor | 1 |
| Modalidade Concorrência - Eletrônica | Participação no Volume % | 58,43% |
| Modalidade Pregão - Eletrônico | Deságio vs Média Geral (p.p.) | 9,6 (9,56) |
| Modalidade Credenciamento | Economia % e Deságio | vazios (esperado, não é erro) |
| Região Centro-Oeste | Participação no Volume % | 44,25% |
| Região Centro-Oeste | Qtd Unidades Compradoras | 107 |
| Perfil Obras e engenharia | Participação no Volume % | 60,82% (60,8% com 1 casa) |

## Medidas de apoio (página 4 e dica de ferramenta)

**Ciclo Médio (mín. 5 itens)** (pasta P4 Ciclo, número decimal, 1 casa). Mostra o ciclo médio só dos órgãos com 5 ou mais itens com ciclo, como pede a pergunta 4.

```dax
Ciclo Médio (mín. 5 itens) =
VAR _itens = [Itens com Ciclo]
RETURN
    IF ( _itens >= 5, [Ciclo Médio (dias)] )
```

**Qtd Itens** (número inteiro). Usada na dica de ferramenta.

```dax
Qtd Itens =
COUNTROWS ( fato_item_contratado )
```

**Título do Tooltip** (texto). Mostra o nome do fornecedor, da modalidade, do órgão, da UF, do perfil ou do mês sobre o qual o mouse está.

```dax
Título do Tooltip =
VAR _selecionado =
    SELECTEDVALUE (
        dim_fornecedor[nome_fornecedor],
        SELECTEDVALUE (
            dim_modalidade[nome_modalidade],
            SELECTEDVALUE (
                dim_orgao[nome_orgao],
                SELECTEDVALUE (
                    dim_localidade[uf_nome],
                    SELECTEDVALUE (
                        fato_item_contratado[perfil_gasto],
                        SELECTEDVALUE ( Calendario[Ano-Mês], "Visão geral" )
                    )
                )
            )
        )
    )
RETURN
    "Detalhe: " & _selecionado
```

## Menu e dica de ferramenta

- **Menu retrátil:** em cada página, o botão `Menu` abre um painel (retângulo, navegador de páginas e botão `Fechar`) e o `Fechar` o esconde. Quem alterna é um par de indicadores (bookmarks) por página, `Pn Menu Aberto` e `Pn Menu Fechado`, sem salvar os dados.
- **Dica de ferramenta:** a página `Tooltip` (oculta, tipo "Dica de ferramenta") traz os números de volume, economia, quantidade de itens e ciclo médio e está ligada aos gráficos de cada página.