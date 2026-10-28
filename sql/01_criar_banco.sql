-- =====================================================================================================
-- 01_criar_banco.sql  
-- =====================================================================================================
-- Rodado pelo src/carregar.py logo depois de banco.recriar_banco(): o banco em si e criado pelo Python,
-- aqui ficam so as tabelas, as chaves e as restricoes.
--
-- Modelo:   dim_orgao  dim_fornecedor  dim_modalidade  dim_localidade   --->   fato_item_contratado
-- (o tempo e a tabela Calendario, criada em DAX no Power BI)
--
-- Decisoes:
--  * Chave substituta (sk_) em toda tabela: a fato aponta para as dimensoes por ela. A chave natural
--    (CNPJ, documento, id, sigla) fica na dimensao como UNIQUE NOT NULL.
--  * Tipos: dinheiro = DECIMAL (nunca FLOAT, que erra centavos), datas = DATE, textos longos = TEXT.
--  * Banco como segunda barreira: CHECK recusa quantidade <= 0, valor negativo, ciclo negativo e
--    homologacao anterior a publicacao, mesmo que o Python deixe passar.
--  * Linha de excecao (sk = -1, "Nao informado") em cada dimensao: valor fora da sequencia 1, 2, 3...
--    das chaves automaticas, entao nunca colide com elas. Serve para uma FK sem destino ter onde apontar.
--    Ela nao conta nas linhas esperadas (363, 2652, 7 e 27).
-- =====================================================================================================


-- ----------------------------------------------------------------------------------------------
-- DIMENSAO: quem comprou
-- ----------------------------------------------------------------------------------------------
CREATE TABLE dim_orgao (
    sk_orgao    INTEGER      NOT NULL,
    cnpj_orgao  VARCHAR(14)  NOT NULL,
    nome_orgao  VARCHAR(255) NOT NULL,
    poder       VARCHAR(20)  NOT NULL,
    CONSTRAINT pk_dim_orgao        PRIMARY KEY (sk_orgao),
    CONSTRAINT uq_dim_orgao_cnpj   UNIQUE (cnpj_orgao),
    CONSTRAINT ck_dim_orgao_poder  CHECK (poder IN ('Executivo', 'Legislativo', 'Judiciário', 'Não informado'))
);

-- ----------------------------------------------------------------------------------------------
-- DIMENSAO: quem vendeu
-- ----------------------------------------------------------------------------------------------
CREATE TABLE dim_fornecedor (
    sk_fornecedor    INTEGER      NOT NULL,
    ni_fornecedor    VARCHAR(20)  NOT NULL,
    nome_fornecedor  VARCHAR(255) NOT NULL,
    tipo_pessoa      VARCHAR(2)   NOT NULL,
    porte            VARCHAR(20),
    CONSTRAINT pk_dim_fornecedor       PRIMARY KEY (sk_fornecedor),
    CONSTRAINT uq_dim_fornecedor_ni    UNIQUE (ni_fornecedor),
    CONSTRAINT ck_dim_fornecedor_tipo  CHECK (tipo_pessoa IN ('PJ', 'PF', 'PE', 'NI'))
);

-- ----------------------------------------------------------------------------------------------
-- DIMENSAO: como comprou
-- ----------------------------------------------------------------------------------------------
CREATE TABLE dim_modalidade (
    sk_modalidade    INTEGER      NOT NULL,
    modalidade_id    INTEGER      NOT NULL,
    nome_modalidade  VARCHAR(60)  NOT NULL,
    CONSTRAINT pk_dim_modalidade     PRIMARY KEY (sk_modalidade),
    CONSTRAINT uq_dim_modalidade_id  UNIQUE (modalidade_id)
);

-- ----------------------------------------------------------------------------------------------
-- DIMENSAO: onde
-- ----------------------------------------------------------------------------------------------
CREATE TABLE dim_localidade (
    sk_localidade  INTEGER      NOT NULL,
    uf_sigla       VARCHAR(2)   NOT NULL,
    uf_nome        VARCHAR(30)  NOT NULL,
    regiao         VARCHAR(20)  NOT NULL,
    CONSTRAINT pk_dim_localidade      PRIMARY KEY (sk_localidade),
    CONSTRAINT uq_dim_localidade_uf   UNIQUE (uf_sigla),
    CONSTRAINT ck_dim_localidade_reg  CHECK (regiao IN ('Norte', 'Nordeste', 'Centro-Oeste', 'Sudeste', 'Sul', 'Não informado'))
);

-- ----------------------------------------------------------------------------------------------
-- FATO: o que foi comprado (uma linha por item de contratacao, com o fornecedor vencedor)
-- ----------------------------------------------------------------------------------------------
CREATE TABLE fato_item_contratado (
    sk_fato                    INTEGER GENERATED ALWAYS AS IDENTITY,
    numero_controle_pncp       VARCHAR(60)    NOT NULL,
    numero_item                INTEGER        NOT NULL,
    sk_orgao                   INTEGER        NOT NULL,
    sk_fornecedor              INTEGER        NOT NULL,
    sk_modalidade              INTEGER        NOT NULL,
    sk_localidade              INTEGER        NOT NULL,
    data_publicacao            DATE           NOT NULL,
    data_homologacao           DATE,                          -- vazia quando a regra 7 anula a homologacao
    descricao_item             TEXT           NOT NULL,
    perfil_gasto               VARCHAR(20)    NOT NULL,
    quantidade                 DECIMAL(18,4)  NOT NULL,
    valor_unitario_estimado    DECIMAL(18,4)  NOT NULL,
    valor_total_estimado       DECIMAL(18,2)  NOT NULL,
    valor_unitario_homologado  DECIMAL(18,4)  NOT NULL,
    valor_total_homologado     DECIMAL(18,2)  NOT NULL,
    comparavel                 SMALLINT       NOT NULL,
    economia_valor             DECIMAL(18,2),                 -- estimado - homologado (so faz sentido nos comparaveis)
    dias_ciclo                 INTEGER,                       -- vazio quando nao ha homologacao valida
    CONSTRAINT pk_fato_item_contratado  PRIMARY KEY (sk_fato),
    CONSTRAINT uq_fato_item             UNIQUE (numero_controle_pncp, numero_item),
    CONSTRAINT fk_fato_orgao            FOREIGN KEY (sk_orgao)       REFERENCES dim_orgao (sk_orgao),
    CONSTRAINT fk_fato_fornecedor       FOREIGN KEY (sk_fornecedor)  REFERENCES dim_fornecedor (sk_fornecedor),
    CONSTRAINT fk_fato_modalidade       FOREIGN KEY (sk_modalidade)  REFERENCES dim_modalidade (sk_modalidade),
    CONSTRAINT fk_fato_localidade       FOREIGN KEY (sk_localidade)  REFERENCES dim_localidade (sk_localidade),
    CONSTRAINT ck_fato_quantidade       CHECK (quantidade > 0),
    CONSTRAINT ck_fato_valores_unit     CHECK (valor_unitario_estimado > 0 AND valor_unitario_homologado > 0),
    CONSTRAINT ck_fato_valores_total    CHECK (valor_total_estimado >= 0 AND valor_total_homologado >= 0),
    CONSTRAINT ck_fato_perfil           CHECK (perfil_gasto IN ('Bens', 'Serviços', 'Obras e engenharia')),
    CONSTRAINT ck_fato_comparavel       CHECK (comparavel IN (0, 1)),
    CONSTRAINT ck_fato_ciclo            CHECK (dias_ciclo IS NULL OR dias_ciclo >= 0),
    CONSTRAINT ck_fato_cronologia       CHECK (data_homologacao IS NULL OR data_homologacao >= data_publicacao),
    CONSTRAINT ck_fato_ciclo_coerente   CHECK ((data_homologacao IS NULL) = (dias_ciclo IS NULL))
);

-- Indices nas chaves estrangeiras: aceleram os JOINs das perguntas de negocio
CREATE INDEX ix_fato_orgao       ON fato_item_contratado (sk_orgao);
CREATE INDEX ix_fato_fornecedor  ON fato_item_contratado (sk_fornecedor);
CREATE INDEX ix_fato_modalidade  ON fato_item_contratado (sk_modalidade);
CREATE INDEX ix_fato_localidade  ON fato_item_contratado (sk_localidade);


-- ----------------------------------------------------------------------------------------------
-- LINHAS DE EXCECAO (sk = -1, "Nao informado")
-- A chave natural de cada uma e um valor que nao existe nas outras linhas.
-- ----------------------------------------------------------------------------------------------
INSERT INTO dim_orgao        (sk_orgao,       cnpj_orgao,      nome_orgao,      poder)
VALUES                       (-1,             'NAO-INFORMADO', 'NÃO INFORMADO', 'Não informado');

INSERT INTO dim_fornecedor   (sk_fornecedor,  ni_fornecedor,   nome_fornecedor, tipo_pessoa, porte)
VALUES                       (-1,             'NAO-INFORMADO', 'NÃO INFORMADO', 'NI',        NULL);

INSERT INTO dim_modalidade   (sk_modalidade,  modalidade_id,   nome_modalidade)
VALUES                       (-1,             -1,              'NÃO INFORMADO');

INSERT INTO dim_localidade   (sk_localidade,  uf_sigla,        uf_nome,         regiao)
VALUES                       (-1,             'NI',            'NÃO INFORMADO', 'Não informado');