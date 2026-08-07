# Log de iterações

English: [ITERATION_LOG.md](ITERATION_LOG.md)

Dia mais recente primeiro. Uma seção por dia civil. Redija bullets neste arquivo e em
`ITERATION_LOG.md`, mostre o preview ao usuário e só então acrescente sob o cabeçalho
de hoje após confirmação (crie o dia no topo se ainda não existir). Veja `.cursor/rules/commit-hygiene.mdc`.

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
