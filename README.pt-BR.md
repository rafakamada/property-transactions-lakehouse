# property-transactions-lakehouse

English: [README.md](README.md)

Aprender DuckDB e dbt analisando dados de transações imobiliárias.

**Fonte de dados pública:** [Dados das Transações Imobiliárias com recolhimento de ITBI — Prefeitura de São Paulo](https://prefeitura.sp.gov.br/web/fazenda/w/acesso_a_informacao/31501) (downloads anuais em Excel/ODS).

Pipeline: XLSX anual em landing (abas = meses + abas de referência) → DuckDB `raw` (substituição completa, orientada por config) → dbt staging → intermediate → marts.

Modelagem e decisões de incremental: [docs/modeling.pt-BR.md](docs/modeling.pt-BR.md).  
Contrato de ingestão: [config/ingest_landing.yml](config/ingest_landing.yml).  
Log de progresso: [ITERATION_LOG.pt-BR.md](ITERATION_LOG.pt-BR.md) ([EN](ITERATION_LOG.md)).

## Conteúdo

- [Configuração](#configuração)
- [Ingerir XLSX no raw](#ingerir-xlsx-no-raw)
- [Consultar DuckDB](#consultar-duckdb)
- [dbt](#dbt)
- [Formatação](#formatação)
- [Testes Python](#testes-python)
- [CI](#ci)

## Configuração

```bash
uv sync
source .venv/bin/activate
cp .env.example .env   # define DBT_PROFILES_DIR=.
```

Requer [uv](https://docs.astral.sh/uv/) e Python 3.12.

## Ingerir XLSX no raw

1. Baixe o arquivo do ano no [portal da Prefeitura](https://prefeitura.sp.gov.br/web/fazenda/w/acesso_a_informacao/31501).
2. Renomeie/copie para `data/landing/YYYY.xlsx` (os nomes dos downloads são pouco confiáveis).
3. Declare as abas em [config/ingest_landing.yml](config/ingest_landing.yml):
   - **Abas de mês** (`MON-YYYY`) → união em `raw.itbi_YYYY`
   - **Outras abas** (LEGENDA, EXPLICAÇÕES, usos, padrões, …) → uma tabela cada, com sufixo do ano
4. Registre as novas tabelas em `models/staging/_sources.yml`.
5. Execute:

```bash
uv run python scripts/ingest_raw.py
```

Substitua o arquivo do ano quando ele for atualizado ou corrigido; a ingestão troca as tabelas `raw` correspondentes àquele arquivo.

> **Dica:**  
> Ao adicionar ou atualizar a planilha de um ano, use a skill do projeto  
> **configure-itbi-landing** (`.cursor/skills/configure-itbi-landing/`) para copiar/renomear o arquivo, atualizar o YAML, registrar em `_sources.yml` e rodar a ingestão.  
> É opcional, mas ajuda a automatizar e simplificar o fluxo.

## Consultar DuckDB

Arquivo do banco local: [`data/dev.duckdb`](data/dev.duckdb). As tabelas ingeridas ficam no schema **`raw`** (por exemplo `raw.itbi_2026`).

O DuckDB permite um escritor por vez. Feche conexões de GUI antes de ingerir e prefira somente leitura quando for só explorar.

### Python (via uv)

```bash
uv run python -c "
import duckdb
con = duckdb.connect('data/dev.duckdb', read_only=True)
con.sql('SHOW TABLES FROM raw').show()
con.sql('SELECT count(*) FROM raw.itbi_2026').show()
"
```

Interativo:

```bash
uv run python
```

```python
import duckdb

con = duckdb.connect("data/dev.duckdb", read_only=True)
con.sql("SHOW TABLES FROM raw")
con.sql("SELECT * FROM raw.itbi_2026 LIMIT 5")
```

### DuckDB CLI

Se o binário [`duckdb`](https://duckdb.org/docs/stable/clients/cli) estiver instalado:

```bash
duckdb data/dev.duckdb -readonly
```

Depois:

```sql
SHOW TABLES FROM raw;
SELECT _reference_month, count(*) FROM raw.itbi_2026 GROUP BY 1 ORDER BY 1;
```

### DBeaver

1. Nova conexão → **DuckDB**.
2. Caminho: caminho absoluto de `data/dev.duckdb` neste repositório.
3. Navegue no schema `raw` e execute SQL.

### Cursor / VS Code

Instale uma extensão de banco compatível com DuckDB (por exemplo SQLTools com driver DuckDB, ou outro “Database Client” que liste DuckDB). Crie uma conexão apontando para `data/dev.duckdb` e consulte o schema `raw`.

## dbt

```bash
export DBT_PROFILES_DIR=.
dbt debug
dbt run
dbt test
```

- Staging / intermediate: **views** (não incrementais).
- Dimensões nos marts: **tables**.
- Fatos nos marts (`fct_*`): **incremental + merge** com `unique_key` — veja [docs/modeling.pt-BR.md](docs/modeling.pt-BR.md).
- Após mudar a lógica de um modelo incremental: `dbt run -s fct_... --full-refresh`.

## Formatação

```bash
uv run ruff format .
uv run ruff check --fix .
```

## Testes Python

```bash
uv run pytest
```

## CI

Pull requests e pushes para `master` rodam Ruff (check + format) e pytest via GitHub Actions (`.github/workflows/ci.yml`).

Quando houver modelos e transformações dbt, estenda o CI para ingestão de fixtures mais `dbt run` / `dbt test` — esse job ainda não está implementado.
