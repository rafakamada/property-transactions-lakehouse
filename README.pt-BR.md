# property-transactions-lakehouse

English: [README.md](README.md)

Projeto para aprender DuckDB e dbt analisando dados de transações imobiliárias.

**Fontes de dados públicas:**
- [Dados das Transações Imobiliárias com recolhimento de ITBI — Prefeitura de São Paulo](https://prefeitura.sp.gov.br/web/fazenda/w/acesso_a_informacao/31501) (downloads anuais em Excel/ODS).
- [CEP Aberto](https://www.cepaberto.com/) (dump colaborativo de CEP; usado para corrigir o `bairro` bagunçado do ITBI via join pelo CEP).
- Séries IBGE IPCA e BACEN SELIC de [Brazil Interest Rate History (SELIC) no Kaggle](https://www.kaggle.com/datasets/hssiqueira/brazil-interest-rate-history-selic/data) (CSVs com cabeçalho em `data/landing/ipca/` e `data/landing/selic/`).

Pipeline: XLSX anual em landing (abas = meses + abas de referência) mais CSVs do CEP Aberto / IPCA / SELIC → DuckDB `raw` (substituição completa, orientada por config) → dbt staging → intermediate → marts.

Modelagem e decisões de incremental: [docs/modeling.pt-BR.md](docs/modeling.pt-BR.md).  
Contrato de ingestão: [config/ingest_landing.yml](config/ingest_landing.yml).  
Log de progresso: [ITERATION_LOG.pt-BR.md](ITERATION_LOG.pt-BR.md) ([EN](ITERATION_LOG.md)).

## Conteúdo

- [Configuração](#configuração)
- [Ingerir landing no raw](#ingerir-landing-no-raw)
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

## Ingerir landing no raw

### ITBI (XLSX)

1. Baixe o arquivo do ano no [portal da Prefeitura](https://prefeitura.sp.gov.br/web/fazenda/w/acesso_a_informacao/31501).
2. Renomeie/copie para `data/landing/YYYY.xlsx` (os nomes dos downloads são pouco confiáveis).
3. Declare as abas em [config/ingest_landing.yml](config/ingest_landing.yml):
   - **Abas de mês** (`MON-YYYY`) → união em `raw.itbi_YYYY`
   - **Outras abas** (LEGENDA, EXPLICAÇÕES, usos, padrões, …) → uma tabela cada, com sufixo do ano
4. Registre as novas tabelas em `models/staging/_sources.yml`.

### CEP Aberto (CSV)

1. Baixe o dump de São Paulo em [CEP Aberto](https://www.cepaberto.com/) e coloque as partes em `data/landing/cep_aberto/` (ex.: `sp.cepaberto_parte_*.csv`).
2. As partes já estão declaradas em `csv_datasets.cep_aberto` em [config/ingest_landing.yml](config/ingest_landing.yml) → união em `raw.cep_aberto`.
3. O `bairro` do ITBI é bagunçado; o CEP Aberto oferece um bairro mais limpo para enriquecimento posterior pelo `cep` normalizado.

### IPCA e SELIC (CSV)

1. Baixe em [Brazil Interest Rate History (SELIC) no Kaggle](https://www.kaggle.com/datasets/hssiqueira/brazil-interest-rate-history-selic/data); coloque `IBGE_IPCA.csv` em `data/landing/ipca/` e `BACEN_SELIC.csv` em `data/landing/selic/`.
2. Ambos estão declarados em `csv_datasets` em [config/ingest_landing.yml](config/ingest_landing.yml) (`header: true`) → `raw.ipca` e `raw.selic`.
3. O staging (`stg_ipca`, `stg_selic`) slugifica os cabeçalhos como no ITBI e coerção de datas/taxas.

### Rodar a ingestão

```bash
uv run python scripts/ingest_raw.py
```

Substitua o arquivo do ano quando ele for atualizado ou corrigido; a ingestão troca as tabelas `raw` correspondentes àquele arquivo. Rodar de novo também atualiza os datasets CSV (`cep_aberto`, `ipca`, `selic`) a partir do landing.

[`dbt seed`](https://docs.getdbt.com/reference/commands/seed) **não** é usado para ITBI, CEP Aberto, IPCA nem SELIC (arquivos de landing gitignored + contrato YAML). Veja [docs/modeling.pt-BR.md](docs/modeling.pt-BR.md#por-que-não-dbt-seed).

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

Pull requests e pushes para `master` rodam Ruff (check + format), pytest, depois um
seed mínimo do DuckDB raw (`scripts/seed_ci_raw.py`) mais
`dbt run -s stg_itbi stg_cep_aberto` e `dbt test` via GitHub Actions
(`.github/workflows/ci.yml`). Os XLSX/CSV de landing não estão no git; o CI semeia
linhas sintéticas em `raw.itbi_YYYY` e `raw.cep_aberto` via `scripts/seed_ci_raw.py`
em vez da ingestão completa ou de `dbt seed`.
