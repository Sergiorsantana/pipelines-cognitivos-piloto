# -*- coding: utf-8 -*-
"""
Gerador de dados sintéticos para o experimento da Seção 5.2.

Gera, a cada execução, um dataset "fonte" com 7 campos canônicos, onde:
  - os NOMES das colunas podem sofrer "schema drift" (sinônimos usados por
    diferentes sistemas de origem);
  - os VALORES podem vir em formatos distintos (datas BR/US/ISO, separador
    decimal '.' ou ',', espaços/maiúsculas inconsistentes).

Isso cria um cenário realista onde um mapeamento FIXO (ETL/ELT tradicionais)
falha parcialmente quando o esquema de origem muda, enquanto um mapeamento
SEMÂNTICO (arquitetura cognitiva) consegue se adaptar.
"""
import random
import datetime as dt

CANONICAL_FIELDS = [
    "customer_id", "full_name", "email",
    "purchase_date", "amount", "category", "country",
]

# Sinônimos possíveis para cada campo canônico (ordem 0 = nome "contratado"
# no momento do desenho do pipeline ETL/ELT, usado no mapeamento fixo)
SYNONYMS = {
    "customer_id":   ["customer_id", "cust_id", "id_cliente", "clientid", "cod_cliente"],
    "full_name":     ["full_name", "client_name", "nome_completo", "nm_cliente", "name"],
    "email":         ["email", "e_mail", "mail", "endereco_email"],
    "purchase_date": ["purchase_date", "order_date", "data_compra", "dt_compra"],
    "amount":        ["amount", "value", "valor", "vl_total", "total"],
    "category":      ["category", "categoria", "tipo_produto", "type"],
    "country":       ["country", "pais", "nation", "cod_pais"],
}

# Nome/descrição canônica usada pelo matcher semântico (simula a "definição
# de negócio" que um agente cognitivo teria acesso via RAG/dicionário de dados)
FIELD_DESCRIPTIONS = {
    "customer_id":   "customer identifier unique client id code",
    "full_name":     "full name of the client customer person",
    "email":         "email address electronic mail contact",
    "purchase_date": "date of the purchase order transaction timestamp",
    "amount":        "total amount value price paid monetary",
    "category":      "product category type classification",
    "country":       "country nation location of the customer",
}

FIRST_NAMES = ["Maria", "Joao", "Ana", "Pedro", "Carla", "Lucas", "Fernanda",
               "Rafael", "Juliana", "Bruno", "Camila", "Diego", "Larissa", "Tiago"]
LAST_NAMES = ["Silva", "Santos", "Oliveira", "Souza", "Costa", "Pereira",
              "Almeida", "Nascimento", "Carvalho", "Araujo", "Ribeiro"]
CATEGORIES = ["eletronicos", "moda", "alimentos", "servicos", "livros", "saude"]
COUNTRIES = ["BR", "US", "PT", "AR", "CL"]


def _rand_date(rng):
    start = dt.date(2023, 1, 1)
    delta = rng.randint(0, 900)
    return start + dt.timedelta(days=delta)


def _format_date(d, fmt):
    if fmt == "iso":
        return d.strftime("%Y-%m-%d")
    if fmt == "br":
        return d.strftime("%d/%m/%Y")
    if fmt == "us":
        return d.strftime("%m/%d/%Y")
    return d.isoformat()


def _format_amount(v, decimal_sep):
    s = f"{v:.2f}"
    if decimal_sep == ",":
        s = s.replace(".", ",")
    return s


def generate_source_dataset(n_records, drift_prob, malformed_prob, seed):
    """
    Gera um dataset "de origem" com n_records linhas.

    drift_prob: probabilidade (0-1) de CADA campo usar um sinônimo diferente
                do nome "contratado" (índice 0) no mapeamento fixo.
    malformed_prob: probabilidade de um valor (data/valor) vir em formato
                     não-canônico (BR/US ao invés de ISO; vírgula decimal).

    Retorna:
      rows: lista de dicts (linhas), com nomes de coluna já "derivados"
      column_map: dict {nome_de_coluna_usado -> campo_canonico} (gabarito)
      used_names: dict {campo_canonico -> nome_de_coluna_usado}
    """
    rng = random.Random(seed)

    used_names = {}
    for field, syns in SYNONYMS.items():
        if rng.random() < drift_prob:
            used_names[field] = rng.choice(syns[1:])  # sinônimo != contratado
        else:
            used_names[field] = syns[0]

    column_map = {v: k for k, v in used_names.items()}

    rows = []
    for i in range(n_records):
        d = _rand_date(rng)
        date_fmt = rng.choice(["br", "us"]) if rng.random() < malformed_prob else "iso"
        amount_val = round(rng.uniform(10, 5000), 2)
        dec_sep = "," if rng.random() < malformed_prob else "."

        name = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
        email = name.lower().replace(" ", ".") + f"{i}@example.com"
        if rng.random() < malformed_prob:
            email = f"  {email.upper()}  "  # ruído de formatação

        row = {
            used_names["customer_id"]:   100000 + i,
            used_names["full_name"]:     name,
            used_names["email"]:         email,
            used_names["purchase_date"]: _format_date(d, date_fmt),
            used_names["amount"]:        _format_amount(amount_val, dec_sep),
            used_names["category"]:      rng.choice(CATEGORIES),
            used_names["country"]:       rng.choice(COUNTRIES),
        }
        rows.append(row)

    return rows, column_map, used_names
