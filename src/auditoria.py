"""
auditoria.py  -  SPRINT 1: AUDITAR (contar os problemas dos CSVs brutos)
------------------------------------------------------------------------
Este script NAO limpa nada. Ele le os 3 CSVs de data/raw/ (tudo como texto) e conta quantos
registros sofrem de cada problema. O resultado vai para reports/auditoria.md e alimenta o
"dicionario das inconsistencias" do README.

Ele roda ANTES da limpeza e nao depende de src/limpeza.py.

Como rodar (na raiz do projeto):    python -m src.auditoria
"""

import re
from datetime import datetime

import pandas as pd

from src import config

# ---------------------------------------------------------------------------------------------
# Constantes (as mesmas ideias do src/limpeza.py, para a auditoria olhar o que a limpeza vai tratar)
# ---------------------------------------------------------------------------------------------
NULOS = {"N/A", "NULL", "NONE", "NAN", "-", "SEM INFORMAÇÃO", "SEM INFORMACAO",
         "NÃO INFORMADO", "NAO INFORMADO", "NÃO SE APLICA", "NAO SE APLICA"}   # o "0" e tratado a parte
FORMATOS_DATA = ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%Y/%m/%d", "%Y%m%d"]
INVISIVEIS = ["\u200b", "\u200c", "\u200d", "\ufeff"]      # caracteres de largura zero
NBSP = "\u00a0"                                            # espaco "sem quebra"

COLUNAS_NUMERICAS = [                                      # colunas de dinheiro e quantidade
    ("compras", "valor_total_estimado"), ("compras", "valor_total_homologado"),
    ("itens", "quantidade"), ("itens", "valor_unitario_estimado"), ("itens", "valor_total_estimado"),
    ("resultados", "quantidade_homologada"), ("resultados", "valor_unitario_homologado"),
    ("resultados", "valor_total_homologado"),
]
COLUNAS_DATA = [
    ("compras", "data_publicacao"), ("compras", "data_abertura_proposta"),
    ("compras", "data_encerramento_proposta"),
    ("resultados", "data_resultado"), ("resultados", "data_cancelamento"),
]
PADROES_DATA = [                                           # como cada data aparece escrita
    ("AAAA-MM-DD com hora (2025-01-06T11:51:06)", r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?"),
    ("AAAA-MM-DD (2025-10-31)", r"\d{4}-\d{2}-\d{2}"),
    ("DD/MM/AAAA, com ou sem hora (02/01/2025 09:03)", r"\d{1,2}/\d{1,2}/\d{4}( \d{1,2}:\d{2}(:\d{2})?)?"),
    ("DD.MM.AAAA (06.03.2025)", r"\d{1,2}\.\d{1,2}\.\d{4}"),
    ("DD-MM-AAAA (06-03-2025)", r"\d{1,2}-\d{1,2}-\d{4}"),
    ("AAAA/MM/DD (2025/03/06)", r"\d{4}/\d{1,2}/\d{1,2}"),
    ("AAAAMMDD (20250102)", r"\d{8}"),
]
PADROES_NUMERO = [                                         # como cada numero aparece escrito (sem R$ e sem sinal)
    ("inteiro (1234)", r"\d+"),
    ("ponto decimal (1234.56)", r"\d+\.\d+"),
    ("virgula decimal (1234,56)", r"\d+,\d+"),
    ("formato BR com milhar (1.234.567,89)", r"\d{1,3}(\.\d{3})+,\d+"),
    ("formato US com milhar (1,234,567.89)", r"\d{1,3}(,\d{3})+\.\d+"),
    ("milhar so com ponto (1.234.567)", r"\d{1,3}(\.\d{3}){2,}"),
    ("milhar so com virgula (1,234,567)", r"\d{1,3}(,\d{3}){2,}"),
]


# ---------------------------------------------------------------------------------------------
# Funcoes de apoio
# ---------------------------------------------------------------------------------------------
def ler(nome):
    """Le um CSV bruto como texto puro (nada de converter tipos agora)."""
    return pd.read_csv(config.PASTA_RAW / f"{nome}.csv", dtype=str, keep_default_na=False)


def sem_invisiveis(texto):
    """Troca o espaco 'sem quebra' por espaco comum e apaga os caracteres de largura zero."""
    texto = texto.replace(NBSP, " ")
    for c in INVISIVEIS:
        texto = texto.replace(c, "")
    return texto


def esta_preenchido(texto):
    return sem_invisiveis(texto).strip() != ""


def acento_quebrado(texto):
    """True se o texto e UTF-8 lido como Latin-1 ('AquisiÃ§Ã£o'). Mesma ideia do consertar_acento."""
    if "Ã" not in texto and "Â" not in texto:
        return False
    try:
        return texto.encode("latin-1").decode("utf-8") != texto
    except (UnicodeEncodeError, UnicodeDecodeError):
        return False


def normalizar_nome(texto):
    """Maiusculas, sem espacos repetidos e com o acento consertado (para comparar grafias)."""
    texto = sem_invisiveis(texto)
    try:
        texto = texto.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    return " ".join(texto.split()).upper()


def so_digitos(texto):
    return re.sub(r"\D", "", texto)


def converter_data(texto):
    """Mesma regra do kit: olha os 10 primeiros caracteres e aceita anos de 2000 a 2030."""
    texto = sem_invisiveis(texto).strip()[:10]
    for formato in FORMATOS_DATA:
        try:
            data = datetime.strptime(texto, formato).date()
        except ValueError:
            continue
        return data if 2000 <= data.year <= 2030 else None
    return None


def formato_data(texto):
    texto = sem_invisiveis(texto).strip()
    for nome, padrao in PADROES_DATA:
        if re.fullmatch(padrao, texto):
            return nome
    return "outro formato"


def analisar_numero(texto):
    """Devolve (formato, tem_rs, tem_nbsp, negativo, parece_milhar) de um numero escrito como texto."""
    tem_nbsp = NBSP in texto or any(c in texto for c in INVISIVEIS)
    t = sem_invisiveis(texto).strip()
    tem_rs = "R$" in t
    t = t.replace("R$", "").replace(" ", "")
    negativo = t.startswith("(") or t.startswith("-") or t.endswith("-")
    t = t.strip("()-")
    formato = "outro formato"
    for nome, padrao in PADROES_NUMERO:
        if re.fullmatch(padrao, t):
            formato = nome
            break
    parece_milhar = bool(re.fullmatch(r"\d{1,3}[.,]\d{3}", t))   # 746.815 ou 746,815: e DECIMAL nesta base
    return formato, tem_rs, tem_nbsp, negativo, parece_milhar


def n(valor):
    """Formata inteiro com ponto de milhar (1234 -> 1.234)."""
    return f"{int(valor):,}".replace(",", ".")


def tabela(cabecalho, linhas):
    """Monta uma tabela em Markdown."""
    saida = ["| " + " | ".join(cabecalho) + " |", "|" + "|".join(["---"] * len(cabecalho)) + "|"]
    for linha in linhas:
        saida.append("| " + " | ".join(str(c) for c in linha) + " |")
    return "\n".join(saida)


# ---------------------------------------------------------------------------------------------
# Auditorias (cada uma devolve texto Markdown e anota os achados do resumo)
# ---------------------------------------------------------------------------------------------
def auditar_visao_geral(arquivos):
    chaves = {"compras": ["numero_controle_pncp"],
              "itens": ["numero_controle_pncp", "numero_item"],
              "resultados": ["numero_controle_pncp", "numero_item", "sequencial_resultado"]}
    linhas = []
    for nome, df in arquivos.items():
        repetidas = df.duplicated(chaves[nome]).sum()
        linhas.append([f"{nome}.csv", n(len(df)), len(df.columns), " + ".join(chaves[nome]), n(repetidas)])
    compras, itens, resultados = arquivos["compras"], arquivos["itens"], arquivos["resultados"]
    chave_item = lambda df: df["numero_controle_pncp"] + "|" + df["numero_item"]
    relacoes = [
        ["itens sem contratação correspondente em compras", n((~itens["numero_controle_pncp"].isin(compras["numero_controle_pncp"])).sum())],
        ["resultados sem item correspondente em itens", n((~chave_item(resultados).isin(chave_item(itens))).sum())],
        ["contratações de compras sem nenhum item", n((~compras["numero_controle_pncp"].isin(itens["numero_controle_pncp"])).sum())],
    ]
    return (tabela(["Arquivo", "Linhas", "Colunas", "Chave", "Chaves repetidas"], linhas)
            + "\n\n" + tabela(["Verificação de relacionamento", "Ocorrências"], relacoes))


def auditar_documentos(arquivos, achados):
    compras, resultados = arquivos["compras"], arquivos["resultados"]
    texto = []

    # --- CNPJ do orgao (compras) ---
    bruto = compras["cnpj_orgao"]
    digitos = bruto.map(so_digitos)
    mascara = bruto.str.contains(r"[./-]").sum()
    perdidos = (digitos.str.len() < 14).sum()
    ok = (digitos.str.len() == 14).sum()
    maior = (digitos.str.len() > 14).sum()
    antes, depois = bruto.str.strip().nunique(), digitos.str.zfill(14).nunique()
    texto.append("**compras.cnpj_orgao** (a limpeza deixa só dígitos e completa para 14 com zeros à esquerda)\n\n" + tabela(
        ["Linhas", "Com máscara (pontos, barra, traço)", "Zero à esquerda perdido (menos de 14 dígitos)",
         "Com 14 dígitos", "Com mais de 14", "CNPJs distintos antes → depois"],
        [[n(len(bruto)), n(mascara), n(perdidos), n(ok), n(maior), f"{n(antes)} → {n(depois)}"]]))
    achados.append(("Máscara no CNPJ do órgão", "compras.cnpj_orgao", f"{n(mascara)} linhas",
                    "limpar_documento: manter só os dígitos (desafio 1)"))
    achados.append(("Zero à esquerda perdido no CNPJ do órgão", "compras.cnpj_orgao", f"{n(perdidos)} linhas",
                    "limpar_documento: completar com zeros até 14 dígitos (desafio 1)"))

    # --- CPF/CNPJ do fornecedor (resultados), por tipo de pessoa ---
    tamanhos = {"PJ": 14, "PF": 11}
    linhas, total_mascara, total_perdido = [], 0, 0
    for tipo in sorted(resultados["tipo_pessoa"].unique()):
        parte = resultados[resultados["tipo_pessoa"] == tipo]["ni_fornecedor"]
        if tipo in tamanhos:
            dig = parte.map(so_digitos)
            tam = tamanhos[tipo]
            masc = parte.str.contains(r"[./-]").sum()
            perd = (dig.str.len() < tam).sum()
            linhas.append([tipo, n(len(parte)), n(masc), n(perd), n((dig.str.len() == tam).sum()),
                           n((dig.str.len() > tam).sum()), f"{n(parte.str.strip().nunique())} → {n(dig.str.zfill(tam).nunique())}"])
            total_mascara += masc
            total_perdido += perd
        else:
            linhas.append([tipo + " (estrangeiro)", n(len(parte)), "-", "-", "-", "-",
                           f"{n(parte.str.strip().nunique())} (sem padrão: mantido como veio)"])
    texto.append("**resultados.ni_fornecedor** por tipo de pessoa (PJ = 14 dígitos, PF = 11; PE não tem formato fixo)\n\n"
                 + tabela(["tipo_pessoa", "Linhas", "Com máscara", "Zero à esquerda perdido", "Tamanho correto",
                           "Maior que o esperado", "Documentos distintos antes → depois"], linhas))
    achados.append(("Máscara no CPF/CNPJ do fornecedor", "resultados.ni_fornecedor", f"{n(total_mascara)} linhas",
                    "limpar_documento: manter só os dígitos (desafio 1)"))
    achados.append(("Zero à esquerda perdido no CPF/CNPJ do fornecedor", "resultados.ni_fornecedor",
                    f"{n(total_perdido)} linhas", "limpar_documento: zeros até 14 (PJ) ou 11 (PF) dígitos (desafio 1)"))
    return "\n\n".join(texto)


def auditar_numeros(arquivos, achados):
    linhas = []
    totais = {"rs": 0, "nbsp": 0, "neg": 0, "br": 0, "us": 0, "milhar": 0, "outro": 0}
    for arquivo, coluna in COLUNAS_NUMERICAS:
        serie = arquivos[arquivo][coluna]
        serie = serie[serie.map(esta_preenchido)]
        contagem, rs, nbsp, neg, milhar = {}, 0, 0, 0, 0
        for valor in serie:
            formato, tem_rs, tem_nbsp, negativo, parece = analisar_numero(valor)
            contagem[formato] = contagem.get(formato, 0) + 1
            rs += tem_rs
            nbsp += tem_nbsp
            neg += negativo
            milhar += parece
        formatos = "; ".join(f"{k}: {n(v)}" for k, v in sorted(contagem.items(), key=lambda x: -x[1]))
        linhas.append([f"{arquivo}.{coluna}", n(len(serie)), n(rs), n(nbsp), n(neg), n(milhar), formatos])
        totais["rs"] += rs
        totais["nbsp"] += nbsp
        totais["neg"] += neg
        totais["milhar"] += milhar
        totais["br"] += contagem.get("formato BR com milhar (1.234.567,89)", 0) + contagem.get("virgula decimal (1234,56)", 0)
        totais["us"] += contagem.get("formato US com milhar (1,234,567.89)", 0)
        totais["outro"] += contagem.get("outro formato", 0)
    achados.append(('Valores com "R$"', "colunas de dinheiro e quantidade", f"{n(totais['rs'])} células",
                    "converter_numero: tirar o R$ antes de converter (desafio 2)"))
    achados.append(("Espaço sem quebra ou invisível dentro de números", "colunas de dinheiro e quantidade",
                    f"{n(totais['nbsp'])} células", "converter_numero: ignorar qualquer espaço (desafio 2)"))
    achados.append(("Números negativos (sinal ou parênteses)", "colunas de dinheiro e quantidade",
                    f"{n(totais['neg'])} células", "converter_numero: aplicar o sinal depois de converter (desafio 2)"))
    achados.append(("Vírgula como decimal (formato brasileiro)", "colunas de dinheiro e quantidade",
                    f"{n(totais['br'])} células", "converter_numero: ponto de milhar sai, vírgula vira ponto (regra 12)"))
    achados.append(("Vírgula como milhar (formato americano)", "colunas de dinheiro e quantidade",
                    f"{n(totais['us'])} células", "converter_numero: vírgula de milhar sai (regra 12)"))
    achados.append(("Ponto ou vírgula sozinho com 3 casas (parece milhar, mas é decimal)",
                    "colunas de dinheiro e quantidade", f"{n(totais['milhar'])} células",
                    "converter_numero: separador sozinho é sempre decimal (regra 12)"))
    cab = ["Coluna", "Preenchidos", 'Com "R$"', "Espaço invisível", "Negativos", "3 casas (parece milhar)", "Formatos encontrados"]
    nota = ("\n\nRegra desta base (regra 12): um ponto ou uma vírgula **sozinho** é sempre o decimal "
            "(`746.815` vale 746,815). Só o separador repetido (`1.234.567`) é milhar; quando aparecem os dois "
            "símbolos, o último é o decimal.")
    return tabela(cab, linhas) + nota


def auditar_datas(arquivos, achados):
    linhas, nao_padrao, nao_convertiveis = [], 0, 0
    for arquivo, coluna in COLUNAS_DATA:
        serie = arquivos[arquivo][coluna]
        serie = serie[serie.map(esta_preenchido)]
        formatos = serie.map(formato_data).value_counts()
        invalidas = serie.map(converter_data).isna().sum()
        nao_padrao += int((serie.map(formato_data) != "AAAA-MM-DD (2025-10-31)").sum())
        nao_convertiveis += int(invalidas)
        detalhe = "; ".join(f"{k}: {n(v)}" for k, v in formatos.items())
        linhas.append([f"{arquivo}.{coluna}", n(len(serie)), n(len(formatos)), n(invalidas), detalhe])
    achados.append(("Datas escritas em vários formatos", "5 colunas de data", f"{n(nao_padrao)} células fora do AAAA-MM-DD simples (hora ou outro formato)",
                    "converter_data: testa cada formato da lista FORMATOS_DATA (desafio 3)"))
    achados.append(("Datas com ano impossível (2034 a 9999), que não viram data válida", "data_encerramento_proposta",
                    f"{n(nao_convertiveis)} células",
                    "converter_data: devolve vazio (None) quando o ano está fora de 2000–2030 (coluna fora do modelo)"))
    texto = tabela(["Coluna", "Preenchidas", "Formatos distintos", "Não convertíveis", "Formatos encontrados"], linhas)

    # --- cronologia: homologacao antes da publicacao ---
    compras, resultados = arquivos["compras"], arquivos["resultados"]
    publicacao = compras.set_index("numero_controle_pncp")["data_publicacao"].map(converter_data)
    resultado = resultados["data_resultado"].map(converter_data)
    pub_do_resultado = resultados["numero_controle_pncp"].map(publicacao)
    ambas = resultado.notna() & pub_do_resultado.notna()
    antes = int((ambas & (pd.to_datetime(resultado, errors="coerce") < pd.to_datetime(pub_do_resultado, errors="coerce"))).sum())
    sem_data = int((~resultados["data_resultado"].map(esta_preenchido)).sum())
    em_2026 = int(resultado.map(lambda d: d is not None and d.year == 2026).sum())
    fora_2025 = int(publicacao.map(lambda d: d is not None and d.year != 2025).sum())
    cron = tabela(["Cronologia", "Ocorrências"], [
        ["resultados com data_resultado ANTERIOR à data_publicacao da contratação", f"{n(antes)} linhas"],
        ["resultados sem data_resultado", f"{n(sem_data)} linhas"],
        ["resultados homologados em 2026 (o Calendário precisa cobrir 2025 e 2026)", f"{n(em_2026)} linhas"],
        ["contratações com data_publicacao fora de 2025", f"{n(fora_2025)} contratações"],
    ])
    achados.append(("Homologação anterior à publicação (impossível)", "resultados.data_resultado × compras.data_publicacao",
                    f"{n(antes)} linhas de resultado", "montar_tabelas, regra 7: anular data de homologação e ciclo; o item continua na fato"))
    return texto + "\n\n" + cron


def auditar_nulos(arquivos, achados):
    numericas = {c for _, c in COLUNAS_NUMERICAS}
    linhas, total_disf, total_zero = [], 0, 0
    for arquivo, df in arquivos.items():
        for coluna in df.columns:
            serie = df[coluna]
            vazio = int((~serie.map(esta_preenchido)).sum())
            limpo = serie.map(lambda t: sem_invisiveis(t).strip().upper())
            disfarcado = int(limpo.isin(NULOS).sum())
            zero = int((limpo == "0").sum())
            if vazio or disfarcado or zero:
                eh_numero = coluna in numericas
                linhas.append([f"{arquivo}.{coluna}", n(vazio), n(disfarcado), n(zero),
                               "não (0 é um número)" if eh_numero else "sim (campo de texto)"])
                total_disf += disfarcado
                total_zero += 0 if eh_numero else zero
    achados.append(("Nulos disfarçados (N/A, NULL, -, SEM INFORMAÇÃO, NÃO SE APLICA...)", "todas as colunas",
                    f"{n(total_disf)} células", "eh_nulo / limpar_texto: viram vazio (None) (desafio 4)"))
    achados.append(('"0" usado como nulo em campo de texto', "colunas de texto", f"{n(total_zero)} células",
                    "limpar_texto(zero_eh_nulo=True); em quantidade e valores o 0 continua sendo número (desafio 4)"))
    return tabela(["Coluna", "Vazios", "Nulos disfarçados (N/A, -, SEM INFORMAÇÃO...)", 'Valor "0"', '"0" é nulo?'], linhas)


def auditar_texto(arquivos, achados):
    linhas = []
    tot = {"acento": 0, "nbsp_inv": 0, "espacos": 0}
    for arquivo, df in arquivos.items():
        for coluna in df.columns:
            s = df[coluna]
            acento = int(s.map(acento_quebrado).sum())
            nbsp = int(s.str.contains(NBSP, regex=False).sum())
            inv = int(s.map(lambda t: any(c in t for c in INVISIVEIS)).sum())
            pontas = int(s.str.contains(r"^\s|\s$").sum())
            repetidos = int(s.str.contains(r"\s{2,}").sum())
            if acento or nbsp or inv or pontas or repetidos:
                linhas.append([f"{arquivo}.{coluna}", n(acento), n(nbsp), n(inv), n(pontas), n(repetidos)])
                if (arquivo, coluna) not in COLUNAS_NUMERICAS:      # os numeros ja foram contados na secao 3
                    tot["acento"] += acento
                    tot["nbsp_inv"] += int(s.map(lambda t: NBSP in t or any(c in t for c in INVISIVEIS)).sum())
                    tot["espacos"] += int(s.str.contains(r"^\s|\s$|\s{2,}").sum())
    achados.append(("Acento quebrado (AquisiÃ§Ã£o)", "colunas de texto", f"{n(tot['acento'])} células",
                    "consertar_acento: refaz a leitura Latin-1 → UTF-8 (desafio 5)"))
    achados.append(("Espaço sem quebra ou caractere invisível", "colunas de texto e de documento",
                    f"{n(tot['nbsp_inv'])} células", "remover_invisiveis + tirar_espacos (desafio 5)"))
    achados.append(("Espaços nas pontas ou repetidos", "colunas de texto e de documento", f"{n(tot['espacos'])} células",
                    "tirar_espacos: uma palavra por vez, um espaço entre elas (desafio 5)"))
    return tabela(["Coluna", "Acento quebrado", "Espaço sem quebra", "Invisível (largura zero)",
                   "Espaço nas pontas", "Espaços repetidos"], linhas)


def auditar_nomes(arquivos, achados):
    compras, resultados, itens = arquivos["compras"], arquivos["resultados"], arquivos["itens"]
    texto = []

    # --- orgaos ---
    cnpj = compras["cnpj_orgao"].map(so_digitos).str.zfill(14)
    nomes_brutos = compras["razao_social_orgao"].str.strip()
    nomes_norm = compras["razao_social_orgao"].map(normalizar_nome)
    grafias_bruto = int((pd.DataFrame({"c": cnpj, "n": nomes_brutos}).groupby("c")["n"].nunique() > 1).sum())
    grafias_norm = int((pd.DataFrame({"c": cnpj, "n": nomes_norm}).groupby("c")["n"].nunique() > 1).sum())
    linhas = [
        ["CNPJs de órgão distintos (depois de limpar a máscara e os zeros)", n(cnpj.nunique())],
        ["nomes de órgão distintos, como vieram", n(nomes_brutos.nunique())],
        ["nomes de órgão distintos, depois de maiúsculas, espaços e acento", n(nomes_norm.nunique())],
        ["CNPJs com mais de uma grafia de nome, como vieram", n(grafias_bruto)],
        ["CNPJs com mais de um nome depois de padronizar", n(grafias_norm)],
    ]
    texto.append("**Órgãos** (o mesmo órgão tem várias unidades, com CNPJ diferente, e nomes escritos de jeitos diferentes)\n\n"
                 + tabela(["Verificação", "Quantidade"], linhas))
    achados.append(("Mesmo CNPJ de órgão com o nome escrito de jeitos diferentes", "compras.razao_social_orgao",
                    f"{n(grafias_bruto)} CNPJs com mais de uma grafia → {n(grafias_norm)} depois de padronizar",
                    "padronizar_nome: maiúsculas, acento e espaços; o ranking agrupa pelo nome padronizado (regra 10)"))

    # --- fornecedores ---
    tipo = resultados["tipo_pessoa"]
    doc = [(re.sub(r"\D", "", v).zfill(14 if t == "PJ" else 11) if t in ("PJ", "PF") else v.strip().upper())
           for v, t in zip(resultados["ni_fornecedor"], tipo)]
    def porte_limpo(texto):                         # nulo disfarcado e "0" contam como porte em branco
        t = sem_invisiveis(texto).strip().upper()
        return "" if (t == "" or t in NULOS or t == "0") else t

    df_f = pd.DataFrame({"doc": doc, "nome_bruto": resultados["nome_fornecedor"].str.strip(),
                         "nome_norm": resultados["nome_fornecedor"].map(normalizar_nome),
                         "porte": resultados["porte"].map(porte_limpo)})
    preenchido = df_f[df_f["porte"] != ""]
    docs_bruto = int((df_f.groupby("doc")["nome_bruto"].nunique() > 1).sum())
    docs_norm = int((df_f.groupby("doc")["nome_norm"].nunique() > 1).sum())
    docs_conflito = int((preenchido.groupby("doc")["porte"].nunique() > 1).sum())
    tem_branco = df_f.assign(v=df_f["porte"] == "").groupby("doc")["v"].any()
    tem_valor = df_f.assign(v=df_f["porte"] != "").groupby("doc")["v"].any()
    docs_completar = int((tem_branco & tem_valor).sum())
    docs_sem_porte = int((~tem_valor).sum())
    linhas = [
        ["fornecedores distintos (documento limpo)", n(df_f["doc"].nunique())],
        ["documentos com mais de uma grafia de nome, como vieram", n(docs_bruto)],
        ["documentos com mais de um nome depois de padronizar", n(docs_norm)],
        ["documentos com portes preenchidos DIFERENTES entre si (conflito real)", n(docs_conflito)],
        ["documentos com porte em branco em algumas linhas e preenchido em outras", n(docs_completar)],
        ["documentos sem nenhum porte preenchido ('Não informado' ou vazio)", n(docs_sem_porte)],
    ]
    texto.append("**Fornecedores**\n\n" + tabela(["Verificação", "Quantidade"], linhas))
    achados.append(("Mesmo fornecedor com portes diferentes ou porte em branco em algumas linhas", "resultados.porte",
                    f"{n(docs_conflito)} documentos com conflito; {n(docs_completar)} com porte a completar",
                    "montar_tabelas: uma linha por documento, com o porte mais frequente entre os preenchidos"))
    achados.append(("Mesmo fornecedor com nomes diferentes depois de padronizar", "resultados.nome_fornecedor",
                    f"{n(docs_norm)} documentos", "montar_tabelas: uma linha por documento, com o nome mais frequente"))

    # --- unidade de medida ---
    brutas = itens["unidade_medida"].str.strip()
    norm = itens["unidade_medida"].map(normalizar_nome)
    texto.append("**itens.unidade_medida** (grafias variadas e valores estranhos como `UNIDADE 0,00`; "
                 "a coluna não entra no modelo, então fica só registrada)\n\n"
                 + tabela(["Verificação", "Quantidade"], [["valores distintos, como vieram", n(brutas.nunique())],
                                                          ["valores distintos depois de maiúsculas e espaços", n(norm.nunique())]]))
    return "\n\n".join(texto)


def auditar_regras(arquivos, achados):
    compras, itens, resultados = arquivos["compras"], arquivos["itens"], arquivos["resultados"]
    chave = lambda df: df["numero_controle_pncp"] + "|" + df["numero_item"]
    itens_k = chave(itens)
    cancelado = resultados["data_cancelamento"].map(esta_preenchido)
    ativos = resultados[~cancelado].copy()
    ativos["chave"] = chave(ativos)
    itens_com_ativo = set(ativos["chave"])
    sem_ativo = ~itens_k.isin(itens_com_ativo)
    so_cancelados = sem_ativo & itens_k.isin(set(chave(resultados[cancelado])))
    marcado = itens["tem_resultado"].str.strip().str.lower() == "true"

    # empates na melhor posicao (vazio vale 1)
    ativos["ordem"] = pd.to_numeric(ativos["ordem_classificacao_srp"], errors="coerce").fillna(1)
    melhor = ativos.groupby("chave")["ordem"].transform("min")
    candidatos = ativos[ativos["ordem"] == melhor]
    com_empate = int((candidatos.groupby("chave").size() > 1).sum())
    varios = int((ativos.groupby("chave").size() > 1).sum())
    ordem_vazia = int((~resultados["ordem_classificacao_srp"].map(esta_preenchido)).sum())
    sequencial = pd.to_numeric(resultados["sequencial_resultado"], errors="coerce")
    credenc = itens_k.str.split("|").str[0].isin(compras.loc[compras["modalidade_id"].str.strip() == "12", "numero_controle_pncp"])

    linhas = [
        ["resultados cancelados (data_cancelamento preenchida)", f"{n(cancelado.sum())} linhas"],
        ["itens sem nenhum resultado válido (descartados pela regra 3)", f"{n(sem_ativo.sum())} itens"],
        ["... dos quais a flag tem_resultado diz True (só têm resultados cancelados)", f"{n((sem_ativo & marcado).sum())} itens"],
        ["... dos quais a flag tem_resultado diz False", f"{n((sem_ativo & ~marcado).sum())} itens"],
        ["itens marcados tem_resultado = False, mas com resultado válido", f"{n(((~marcado) & ~sem_ativo).sum())} itens"],
        ["itens com mais de um classificado válido (Registro de Preços)", f"{n(varios)} itens"],
        ["itens com empate na melhor posição (precisa do menor sequencial_resultado)", f"{n(com_empate)} itens"],
        ["resultados com ordem_classificacao_srp vazia (vale 1)", f"{n(ordem_vazia)} linhas"],
        ["resultados com sequencial_resultado de 10 ou mais (a ordem tem que ser numérica)", f"{n((sequencial >= 10).sum())} linhas"],
        ["itens de contratações em Credenciamento (modalidade 12; fora da economia)", f"{n(credenc.sum())} itens"],
        ["itens com orçamento sigiloso (sigiloso = True)", f"{n((itens['sigiloso'].str.strip().str.lower() == 'true').sum())} itens"],
        ["valores de modalidade_nome por modalidade_id (se > 1, o nome varia)", f"{n(compras.groupby('modalidade_id')['modalidade_nome'].nunique().max())} no máximo"],
    ]
    achados.append(("Resultados cancelados no meio dos classificados", "resultados.data_cancelamento", f"{n(cancelado.sum())} linhas",
                    "montar_tabelas, regra 2: descartar os cancelados ANTES de escolher o 1º colocado"))
    achados.append(("Itens sem resultado homologado", "itens × resultados", f"{n(sem_ativo.sum())} itens",
                    "montar_tabelas, regra 3: ficam fora da fato (não contam como rejeitados)"))
    achados.append(("Empate na melhor posição (Credenciamento e outros)", "resultados.ordem_classificacao_srp",
                    f"{n(com_empate)} itens", "montar_tabelas, regra 2: vale o menor sequencial_resultado, lido como número"))
    return tabela(["Verificação", "Ocorrências"], linhas)


# ---------------------------------------------------------------------------------------------
# Relatorio
# ---------------------------------------------------------------------------------------------
def main():
    arquivos = {nome: ler(nome) for nome in ["compras", "itens", "resultados"]}
    achados = []        # cada item: (problema, onde, ocorrencias, tratamento)

    secoes = [
        ("1. Visão geral e relacionamento entre os arquivos", auditar_visao_geral(arquivos)),
        ("2. Documentos (CNPJ/CPF): máscara e zeros perdidos", auditar_documentos(arquivos, achados)),
        ("3. Dinheiro e quantidades: formatos de número", auditar_numeros(arquivos, achados)),
        ("4. Datas: formatos e cronologia", auditar_datas(arquivos, achados)),
        ("5. Nulos disfarçados e zeros", auditar_nulos(arquivos, achados)),
        ("6. Texto: acento quebrado e espaços", auditar_texto(arquivos, achados)),
        ("7. Nomes: órgãos, fornecedores e unidades", auditar_nomes(arquivos, achados)),
        ("8. Armadilhas das regras de negócio", auditar_regras(arquivos, achados)),
    ]

    resumo = tabela(["#", "Inconsistência", "Onde", "Ocorrências", "Como será tratada"],
                    [[i, *a] for i, a in enumerate(achados, start=1)])
    partes = [
        "# Auditoria dos dados brutos (Sprint 1)\n",
        "Relatório gerado por `python -m src.auditoria`, lendo `data/raw/` sem alterar nada. "
        "\"Linhas\" são linhas do arquivo; \"células\" são valores individuais (uma linha pode ter vários).\n",
        "## Resumo: dicionário das inconsistências\n",
        resumo + "\n",
    ]
    for titulo, corpo in secoes:
        partes.append(f"## {titulo}\n")
        partes.append(corpo + "\n")

    config.PASTA_REPORTS.mkdir(exist_ok=True)
    destino = config.PASTA_REPORTS / "auditoria.md"
    destino.write_text("\n".join(partes), encoding="utf-8", newline="\n")

    print(f"Auditoria concluída: {len(achados)} tipos de problema contados.")
    print(f"Relatório gravado em: {destino}")


if __name__ == "__main__":
    main()