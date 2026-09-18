# Relatorio de cobertura dos testes automatizados

**39 testes · 100% de cobertura de linhas e de branches · 0 falhas.**

Executado em 18/09/2026 contra PostgreSQL 16, mesma configuracao usada no CI.

## 1. Relatorio

Saida literal de `coverage report -m` (arquivo bruto em
[coverage-report.txt](coverage-report.txt)):

```
Name                                Stmts   Miss Branch BrPart  Cover   Missing
-------------------------------------------------------------------------------
apps/appointments/admin.py              6      0      0      0   100%
apps/appointments/models.py            11      0      0      0   100%
apps/appointments/serializers.py       13      0      2      0   100%
apps/appointments/urls.py               5      0      0      0   100%
apps/appointments/views.py              7      0      0      0   100%
apps/core/admin.py                      0      0      0      0   100%
apps/core/exceptions.py                13      0      4      0   100%
apps/core/middleware.py                12      0      0      0   100%
apps/core/models.py                     0      0      0      0   100%
apps/core/pagination.py                 5      0      0      0   100%
apps/core/urls.py                       3      0      0      0   100%
apps/core/views.py                     27      0      0      0   100%
apps/professionals/admin.py             6      0      0      0   100%
apps/professionals/models.py           12      0      0      0   100%
apps/professionals/serializers.py       7      0      0      0   100%
apps/professionals/urls.py              5      0      0      0   100%
apps/professionals/views.py            22      0      0      0   100%
-------------------------------------------------------------------------------
TOTAL                                 154      0      6      0   100%
```

`branch = true` esta ligado: os 6 branches da coluna `Branch` sao caminhos
condicionais (validacoes e o handler de excecao), e `BrPart 0` significa que
**os dois lados** de cada condicional foram exercitados — nao apenas a linha
executada uma vez.

## 2. Como reproduzir

```bash
docker compose up -d db
poetry install

poetry run coverage run manage.py test --verbosity 2
poetry run coverage report -m      # tabela acima
poetry run coverage html           # relatorio navegavel em htmlcov/index.html
```

Configuracao em `[tool.coverage.*]` no `pyproject.toml`: mede `apps/`, com
branch coverage, omitindo `migrations/` (codigo gerado), `tests.py` (medir o
proprio teste infla o numero sem dizer nada) e `apps.py`/`__init__.py` (boilerplate).

No CI, um unico comando gera tudo (`.github/workflows/ci.yml`), e o resultado
aparece em tres lugares na execucao do GitHub Actions:

- a tabela no **Summary** da execucao;
- o relatorio HTML + `coverage.xml` no artefato `coverage-report` (30 dias);
- falha do job se a cobertura cair abaixo do portao.

## 3. Portao de cobertura

`fail_under = 95` no `pyproject.toml`. O valor real e 100%, e o portao esta em
95 de proposito: um portao em 100% faz qualquer linha defensiva nova quebrar o
build e cria pressao para escrever teste artificial so para fechar o numero.
95 preserva a margem sem permitir regressao silenciosa. **O valor sobe conforme
a cobertura cresce; nunca desce para fazer o CI passar.**

## 4. O que os 39 testes cobrem

| Modulo | Testes | Classes |
|---|---|---|
| `apps/core` | 12 | `JWTAuthFlowTests`, `HealthCheckTests`, `ExceptionHandlerTests` |
| `apps/professionals` | 14 | `HealthProfessionalCRUDTests`, `HealthProfessionalValidationTests`, `HealthProfessionalAuthTests`, `HealthProfessionalModelTests` |
| `apps/appointments` | 13 | `AppointmentCRUDTests`, `AppointmentValidationTests`, `AppointmentAuthTests`, `AppointmentModelTests` |

Lista nominal completa em [test-list.txt](test-list.txt).

Por area:

| Area | Cenarios verificados |
|---|---|
| **Autenticacao JWT** | obtencao com credencial valida e invalida; acesso a rota protegida com token valido, sem token e com token invalido; refresh; **replay de refresh token rotacionado retorna 401** |
| **Health checks** | liveness sem autenticacao; readiness com banco disponivel; readiness retornando 503 com o banco fora (via mock) |
| **Tratamento de erro** | excecao nao tratada retorna JSON 500 (e nao HTML do Django) e e logada; resposta 5xx do DRF e logada |
| **CRUD de profissionais** | listar, criar, detalhar, atualizar, excluir; 409 ao excluir profissional com consultas vinculadas |
| **Validacao de profissionais** | campos obrigatorios; campos em branco (`"   "`) rejeitados em `nome_social`, `profissao` e `contato`; espacos nas bordas sao removidos na criacao |
| **CRUD de consultas** | listar, criar, detalhar, atualizar, excluir |
| **Validacao de consultas** | profissional inexistente; data no passado rejeitada |
| **Busca por profissional** | rota aninhada `/professionals/{id}/appointments/` e filtro `?profissional=<id>` |
| **Autorizacao** | endpoints de negocio retornam 401 sem token |

## 5. Mudancas feitas para chegar a 100%

O ponto de partida desta revisao era **92%**. As lacunas nao foram fechadas com
teste artificial — em dois casos a linha descoberta apontava codigo morto, e a
correcao foi remover o codigo:

| Lacuna original | Diagnostico | Acao |
|---|---|---|
| `professionals/serializers.py` — 3 branches | Os validadores `validate_nome_social/profissao/contato` eram **inalcancaveis**: o `CharField` do DRF ja aplica `trim_whitespace=True` e rejeita branco antes de chamar validador de campo (com mensagem em pt-BR, dado `LANGUAGE_CODE="pt-br"`) | Validadores removidos. Comportamento identico, verificado pelos testes de validacao que continuam passando |
| `professionals/views.py` — 1 branch | `if page is not None` com fallback nao paginado: `paginate_queryset` so retorna `None` sem paginador, e ha paginador global | Branch removido |
| `core/exceptions.py` — 3 linhas | Handler de 500 nunca exercitado | Testes reais adicionados (`ExceptionHandlerTests`), nao `pragma: no cover` |
| `models.py` — `__str__` | Sem cobertura | Testes adicionados |
| `core/views.py` | Arquivo vazio — health check nao existia | Endpoints implementados e testados (ver [OBSERVABILIDADE.md](OBSERVABILIDADE.md)) |

## 6. O que a cobertura nao mede

100% de linhas significa que **toda linha roda em algum teste**, nao que todo
comportamento esta correto. Nao ha teste automatizado hoje para:

- **Integracao real com a AWS** — deploy, health check atras do ALB, leitura de
  secrets do Secrets Manager. O smoke test do CD cobre isso em tempo de deploy,
  nao na suite.
- **Carga e concorrencia** — nenhum teste de performance ou de corrida.
- **Migrations** — aplicadas na criacao do banco de teste, mas sem teste de
  reversibilidade nem de compatibilidade com a versao anterior do codigo (ponto
  relevante para rollback: ver [DEPLOY-E-ROLLBACK.md](DEPLOY-E-ROLLBACK.md)).
- **Regras de negocio ainda nao implementadas** — conflito de horario, duracao e
  status de consulta. Ver [LIMITACOES-E-PENDENCIAS.md](LIMITACOES-E-PENDENCIAS.md).
