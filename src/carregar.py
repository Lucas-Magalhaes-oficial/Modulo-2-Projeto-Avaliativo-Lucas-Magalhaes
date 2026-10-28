"""
carregar.py  -  CARGA NO POSTGRESQL   (voce completa os trechos com ____)
=========================================================================
Passos:  1) recria o banco e as tabelas (banco.recriar_banco + sql/01_criar_banco.sql)
         2) carrega as 4 DIMENSOES   3) carrega a FATO (as dimensoes vem primeiro!)   4) confere as contagens
Usa so o que o kit ja traz: src/config.py e src/banco.py (recriar_banco, conectar, executar_script, inserir_em_lote, consultar).
O sql/01_criar_banco.sql e o SEU script (veja a secao 4.3 do enunciado): crie esse arquivo antes de rodar a carga.
Ele so cria as tabelas: o banco em si e recriado por banco.recriar_banco().
Dica: veja a carga em lote do 1_extrair.py do Desafio Transparencia (banco.inserir_em_lote).

COMO RODAR (depois do montar_tabelas):   python -m src.carregar

CONTROLE DE FALHAS (acrescentado ao kit):
  - validar(): confere os arquivos de data/processed ANTES de mexer no banco (chaves unicas, sem vazios,
    nenhuma FK solta). Se algo estiver errado, nada e enviado ao banco.
  - Carga em UMA transacao: as 5 tabelas entram tudo-ou-nada. Qualquer erro dispara rollback e o programa
    termina com mensagem clara (codigo de saida 1).
  - conferir(): antes do commit, compara o banco com os arquivos, procura FK solta e confere as somas em R$.
"""

import sys

import pandas as pd
import psycopg2

from src import banco, config

# (tabela, chave substituta, chave natural, colunas na ordem do CSV).  A chave substituta tem o mesmo nome na fato.
DIMENSOES = [("dim_orgao", "sk_orgao", "cnpj_orgao", ["sk_orgao", "cnpj_orgao", "nome_orgao", "poder"]),
             ("dim_fornecedor", "sk_fornecedor", "ni_fornecedor", ["sk_fornecedor", "ni_fornecedor", "nome_fornecedor", "tipo_pessoa", "porte"]),
             ("dim_modalidade", "sk_modalidade", "modalidade_id", ["sk_modalidade", "modalidade_id", "nome_modalidade"]),
             ("dim_localidade", "sk_localidade", "uf_sigla", ["sk_localidade", "uf_sigla", "uf_nome", "regiao"])]

COLUNAS_FATO = ["numero_controle_pncp", "numero_item", "sk_orgao", "sk_fornecedor", "sk_modalidade", "sk_localidade",
                "data_publicacao", "data_homologacao", "descricao_item", "perfil_gasto", "quantidade",
                "valor_unitario_estimado", "valor_total_estimado", "valor_unitario_homologado", "valor_total_homologado",
                "comparavel", "economia_valor", "dias_ciclo"]

# prova real (anexo 8): linhas esperadas em cada tabela (a linha de excecao sk = -1 nao conta)
ESPERADO = {"fato_item_contratado": 6126, "dim_orgao": 363, "dim_fornecedor": 2652, "dim_modalidade": 7, "dim_localidade": 27}
ESPERADO_HOMOLOGADO = 8044498805.74      # soma do valor total homologado (anexo 8); poucos centavos de diferenca sao normais


def ler(nome, **opcoes):
    """PRONTA. Le um CSV de data/processed. Campo vazio vira NaN (que mais abaixo vira None = NULL no banco)."""
    return pd.read_csv(config.PASTA_PROCESSED / f"{nome}.csv", keep_default_na=False, na_values=[""], **opcoes)


def tuplas(tabela, colunas):
    """PRONTA. Transforma o DataFrame em uma lista de tuplas simples, que e o que o banco entende.
    Valor vazio (NaN) vira None, que o banco grava como NULL."""
    dados = tabela[colunas].astype(object)
    dados = dados.where(dados.notna(), None)
    return [tuple(linha) for linha in dados.itertuples(index=False, name=None)]


def inserir(con, tabela, colunas, dados):
    """Monta o INSERT INTO ... VALUES (%s, %s, ...) e envia todas as linhas de uma vez."""
    # Um %s para cada coluna. COMPLETE: monte uma lista com "%s" repetido len(colunas) vezes:  ["%s"] * len(colunas)
    marcadores = ", ".join(["%s"] * len(colunas))
    sql = f"INSERT INTO {tabela} ({', '.join(colunas)}) VALUES ({marcadores})"
    # COMPLETE: envie em lote com banco.inserir_em_lote(conexao, sql, linhas)
    # commit=False: a transacao fica aberta ate o main() confirmar que tudo deu certo
    banco.inserir_em_lote(con, sql, tuplas(dados, colunas), commit=False)
    print(f"   {tabela}: {len(dados)} linhas")


def brl(valor):
    """Formata em reais no padrao brasileiro (8.044.498.805,74)."""
    return f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def validar(dimensoes, fato):
    """Confere os arquivos ANTES de tocar no banco. Se algo estiver errado, levanta ValueError."""
    problemas = []
    for nome, sk, natural, colunas in DIMENSOES:
        tabela = dimensoes[nome]
        faltando = [c for c in colunas if c not in tabela.columns]
        if faltando:
            problemas.append(f"{nome}: faltam as colunas {faltando}")
            continue
        if tabela[sk].isna().any() or tabela[natural].isna().any():
            problemas.append(f"{nome}: chave substituta ou natural vazia")
        if tabela[sk].duplicated().any():
            problemas.append(f"{nome}: chave substituta {sk} repetida")
        if tabela[natural].duplicated().any():
            problemas.append(f"{nome}: chave natural {natural} repetida")
        if (pd.to_numeric(tabela[sk], errors="coerce") <= 0).any():
            problemas.append(f"{nome}: {sk} precisa ser maior que 0 (o -1 e reservado para 'Nao informado')")
    faltando = [c for c in COLUNAS_FATO if c not in fato.columns]
    if faltando:
        problemas.append(f"fato_item_contratado: faltam as colunas {faltando}")
    else:
        if fato.empty:
            problemas.append("fato_item_contratado: arquivo sem linhas")
        if fato.duplicated(["numero_controle_pncp", "numero_item"]).any():
            problemas.append("fato_item_contratado: (numero_controle_pncp, numero_item) repetido")
        for nome, sk, _, _ in DIMENSOES:
            if fato[sk].isna().any():
                problemas.append(f"fato_item_contratado: {sk} vazia (FK sem destino)")
                continue
            soltas = (~fato[sk].astype(int).isin(pd.to_numeric(dimensoes[nome][sk]).astype(int))).sum()
            if soltas:
                problemas.append(f"fato_item_contratado: {soltas} linhas com {sk} que nao existe em {nome} (FK solta)")
    if problemas:
        raise ValueError("Os arquivos de data/processed tem problemas. NADA foi enviado ao banco:\n   - " + "\n   - ".join(problemas))


def conferir(con, dimensoes, fato):
    """Roda ANTES do commit. Se algo nao bater com os arquivos, levanta ValueError (e o main faz rollback)."""
    erros = []
    arquivos = {nome: len(dimensoes[nome]) for nome, *_ in DIMENSOES}
    arquivos["fato_item_contratado"] = len(fato)
    sks = {nome: sk for nome, sk, *_ in DIMENSOES}

    print("Conferencia:")
    for tabela, esperado in ESPERADO.items():
        filtro = f" WHERE {sks[tabela]} > 0" if tabela in sks else ""          # a linha -1 nao conta
        # COMPLETE: conte as linhas da tabela com SELECT COUNT(*)
        n = banco.consultar(con, f"SELECT COUNT(*) FROM {tabela}{filtro}")[0][0]
        print(f"   {tabela}: {n} (esperado {esperado}) -> {'OK' if n == esperado else 'DIVERGENTE'}")
        if n != arquivos[tabela]:
            erros.append(f"{tabela}: o banco tem {n} linhas e o arquivo tem {arquivos[tabela]}")

    soltas = sum(banco.consultar(con, f"SELECT COUNT(*) FROM fato_item_contratado f WHERE NOT EXISTS "
                                      f"(SELECT 1 FROM {nome} d WHERE d.{sk} = f.{sk})")[0][0]
                 for nome, sk, *_ in DIMENSOES)
    em_excecao = sum(banco.consultar(con, f"SELECT COUNT(*) FROM fato_item_contratado WHERE {sk} = -1")[0][0]
                     for _, sk, *_ in DIMENSOES)
    print(f"   FKs soltas na fato: {soltas} -> {'OK' if soltas == 0 else 'ERRO'}")
    print(f"   chaves da fato apontando para 'Nao informado' (sk = -1): {em_excecao}")
    if soltas:
        erros.append(f"{soltas} chaves estrangeiras soltas na fato")

    homologado, estimado, economia = banco.consultar(
        con, "SELECT SUM(valor_total_homologado), SUM(valor_total_estimado), SUM(economia_valor) FROM fato_item_contratado")[0]
    for nome, no_banco, no_arquivo in [("valor_total_homologado", homologado, fato["valor_total_homologado"].sum()),
                                       ("valor_total_estimado", estimado, fato["valor_total_estimado"].sum()),
                                       ("economia_valor", economia, fato["economia_valor"].sum())]:
        if abs(float(no_banco) - float(no_arquivo)) > 0.05:
            erros.append(f"soma de {nome}: banco R$ {brl(float(no_banco))} x arquivo R$ {brl(float(no_arquivo))}")
    ok = abs(float(homologado) - ESPERADO_HOMOLOGADO) <= 1.00
    print(f"   volume homologado no banco: R$ {brl(float(homologado))} (anexo 8: R$ {brl(ESPERADO_HOMOLOGADO)}) -> {'OK' if ok else 'DIVERGENTE'}")
    if erros:
        raise ValueError("A conferencia do banco falhou:\n   - " + "\n   - ".join(erros))


def main():
    con = None
    try:
        # 0) Le e valida os arquivos ANTES de mexer no banco
        dimensoes = {nome: ler(nome, dtype=str) for nome, *_ in DIMENSOES}      # dtype=str: o CNPJ nao pode perder o zero da esquerda
        fato = ler("fato_item_contratado")
        # dias_ciclo vem como 48.0 (decimal) porque tem vazios; o banco quer inteiro. COMPLETE: converta para o tipo "Int64"
        fato["dias_ciclo"] = fato["dias_ciclo"].astype("Int64")
        validar(dimensoes, fato)

        # 1) Banco (o recriar_banco apaga e cria de novo) e tabelas
        banco.recriar_banco()
        con = banco.conectar()
        # COMPLETE: execute o arquivo SQL de criacao: banco.executar_script(conexao, caminho_do_arquivo)
        banco.executar_script(con, config.PASTA_SQL / "01_criar_banco.sql")

        # 2) Dimensoes PRIMEIRO: a fato tem chave estrangeira para elas, entao elas precisam existir antes.
        #    Dimensoes e fato entram na MESMA transacao: ou entra tudo, ou nada.
        print("Carga:")
        for nome, _, _, colunas in DIMENSOES:
            inserir(con, nome, colunas, dimensoes[nome])

        # 3) Fato (depois das dimensoes)
        # COMPLETE: o nome da tabela da fato
        inserir(con, "fato_item_contratado", COLUNAS_FATO, fato)

        # 4) Conferencia: o que esta no banco tem que bater com os arquivos e com a prova real (anexo 8 do enunciado)
        conferir(con, dimensoes, fato)
        con.commit()
        print("Carga concluida e confirmada (commit).")
    except (psycopg2.Error, RuntimeError, ValueError, FileNotFoundError) as erro:
        if con is not None:
            con.rollback()
        print(f"\nERRO NA CARGA: {erro}")
        if con is not None:
            print("Rollback executado: nenhuma linha das dimensoes ou da fato foi gravada.")
        sys.exit(1)
    finally:
        if con is not None:
            con.close()


if __name__ == "__main__":
    main()