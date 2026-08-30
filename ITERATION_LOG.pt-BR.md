# Log de iterações

English: [ITERATION_LOG.md](ITERATION_LOG.md)

Dia mais recente primeiro. Uma seção por dia civil. Redija bullets neste arquivo e em
`ITERATION_LOG.md`, mostre o preview ao usuário e só então acrescente sob o cabeçalho
de hoje após confirmação (crie o dia no topo se ainda não existir). Veja `.cursor/rules/commit-hygiene.mdc`.

## 2026-08-30

- **Adicionar IPCA e SELIC ao raw e staging** — `csv_datasets` para CSVs IBGE/BACEN do Kaggle → `raw.ipca` / `raw.selic`; `stg_ipca` / `stg_selic` com slugify ciente de CamelCase, casts, testes de grain, fixtures de unit test dbt, seed de CI e docs. Verificar: `uv run pytest`, `uv run python scripts/ingest_raw.py`, `DBT_PROFILES_DIR=. dbt run -s stg_ipca stg_selic`, `dbt test -s stg_ipca stg_selic`

## 2026-08-29

- **Usar `dbt_project.yml` para views de staging** — remover `{{ config(materialized='view') }}` redundante de `stg_itbi` / `stg_cep_aberto`; corrigir unit tests no Fusion com fixtures nos cabeçalhos portugueses do raw e `select_slugified_columns` real. Verificar: `DBT_PROFILES_DIR=. dbt test -s stg_itbi stg_cep_aberto`
- **Documentar por que a ingestão via landing é usada em vez de `dbt seed`** — modeling + README (EN/pt-BR) registram que fontes grandes e gitignored de ITBI/CEP usam `ingest_raw.py` / `seed_ci_raw.py`; voz passiva no texto relacionado.
- **Adicionar CEP Aberto ao raw e staging** — estender a ingestão com `csv_datasets` para dumps de CEP de SP → `raw.cep_aberto`; adicionar `stg_cep_aberto` com CEP no mesmo formato do ITBI e testes de grain; seed de CI + docs citam [cepaberto.com](https://www.cepaberto.com/) e o enriquecimento do `bairro` bagunçado do ITBI via CEP. Verificar: `uv run pytest`, `uv run python scripts/ingest_raw.py`, `DBT_PROFILES_DIR=. dbt run -s stg_cep_aberto`, `dbt test -s stg_cep_aberto`
- **Forçar tipos de identificadores em stg_itbi** — cast de `n_cadastro_sql`/`uso_iptu` para varchar, `numero`/`matricula_imovel` para integer, e normalizar CEP para string de 8 dígitos com zero à esquerda; documentar CEP no `schema.yml`; ignorar SQL local em `analyses/*`.
- **Adicionar unit tests nativos do dbt para casts** — fixtures SQL em `tests/fixtures/` mais `test_stg_itbi_cast_fixtures` / `test_stg_itbi_cep_invalid_becomes_null`; pin `dbt-core>=1.12.3`. Verificar: `DBT_PROFILES_DIR=. dbt test --select "test_type:unit"`
- **Endurecer casts e filtros de lixo em stg_itbi** — expandir SQL em notação científica; remover sufixos float do Excel em `uso_iptu`/`padrao_iptu`; anular `proporcao_transmitida` fora de `[0, 100]`; remover linhas que ecoam cabeçalhos; ampliar fixtures de unit test. Verificar: `DBT_PROFILES_DIR=. dbt test --select "test_type:unit"`, `dbt run -s stg_itbi`, `dbt test`

## 2026-08-07

- **Adicionar camada de staging ITBI** — `stg_itbi` une `raw.itbi_YYYY` com slugify Jinja (stop words removidas), coerção de tipos e guards de schema; `schema.yml` + testes singulares; docs e `configure-itbi-landing` atualizados para `vars.itbi_years`. Verificar: `DBT_PROFILES_DIR=. dbt run -s stg_itbi`, `dbt test`
- **Adicionar dbt ao CI** — seed sintético de `raw.itbi_YYYY` via `scripts/seed_ci_raw.py`, depois `dbt run -s stg_itbi` e `dbt test` no GitHub Actions; notas de CI no README atualizadas

## 2026-08-06

- **Adicionar docs pt-BR e condensar log de iterações** — TOC no README; `README.pt-BR.md`, `docs/modeling.pt-BR.md` e `ITERATION_LOG.pt-BR.md`; uma seção por dia nos dois logs; higiene de commit exibe preview EN/pt-BR e só committa após confirmação
- **Documentar consulta ao DuckDB** — README: como listar/consultar tabelas `raw` via Python, DuckDB CLI, DBeaver e Cursor/VS Code
- **Adicionar ingestão raw** — ingestão ITBI multi-aba orientada por config (`config/ingest_landing.yml` → `raw.itbi_YYYY` + outras abas com sufixo do ano); skill `configure-itbi-landing`; docs citam o portal da Prefeitura. Verificar: `uv run pytest`, `uv run python scripts/ingest_raw.py`
- **Corrigir trigger de push do CI para o branch padrão** — apontar o trigger de push do workflow e a documentação para `master` (padrão do repo), não `main`
- **Adicionar CI de lint e testes unitários** — GitHub Actions roda Ruff e pytest em PRs e pushes; README nota que CI de ingest/`dbt run`/`dbt test` virá quando houver transforms. Verificar: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest`

## 2026-08-03

- **Bootstrap da ferramenta do projeto** — uv + Python 3.12, dbt-duckdb, DuckDB, Ruff, pytest; script de ingestão landing XLSX → raw; scaffold dbt staging/intermediate/marts; regras Cursor de modelagem, data-TDD e higiene de commit
- **Decisão de aprendizado: fatos incrementais** — documentar formato da fonte (XLSX anual, abas mensais, raw com full-replace); manter stg/int como views, dim como tables; aprender **merge** incremental só em `fct_*`; adicionado `docs/modeling.md`
- **Falhar em colisões de nome de tabela na ingestão** — levantar erro quando arquivos de landing distintos sanitizam para o mesmo nome de tabela `raw`; cobrir colisões hífen/underscore e maiúsculas/espaços nos testes unitários. Verificar: `uv run pytest tests/unit/test_ingest_raw.py`
