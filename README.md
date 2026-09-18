# API de Gerenciamento de Consultas Medicas

API RESTful para cadastro de profissionais de saude e consultas medicas, construida com Django + Django REST Framework como desafio tecnico (Lacrei Saude). Prioriza seguranca dos dados, boas praticas de desenvolvimento e preparacao para producao.

## Documentacao

Detalhamento por tema, em `docs/`:

| Documento | Conteudo |
|---|---|
| [Configuracao](docs/CONFIGURACAO.md) | Secrets, variaveis e configuracoes necessarias por ambiente, e onde cada uma vive |
| [Seguranca](docs/SEGURANCA.md) | Checklist por ambiente: DEBUG, CORS, autenticacao, gestao de secrets, exposicao do banco, producao |
| [Observabilidade](docs/OBSERVABILIDADE.md) | Logs, health checks, metricas, monitoramento e como consultar na AWS |
| [Deploy e rollback](docs/DEPLOY-E-ROLLBACK.md) | Pipelines, onde ficam as evidencias e rollback passo a passo |
| [Cobertura de testes](docs/COBERTURA-DE-TESTES.md) | Relatorio de cobertura e o que cada teste verifica |
| [Limitacoes e pendencias](docs/LIMITACOES-E-PENDENCIAS.md) | O que nao esta pronto, por que, e melhorias futuras de regras de negocio |
| [Deploy de demonstracao](docs/DEPLOY-DEMO-CLOUD-RUN.md) | Ambiente publico gratuito (Cloud Run + Neon), com HTTPS, para demonstrar a API rodando |

> **Estado dos ambientes AWS:** o Terraform foi validado mas **nao aplicado**, e
> nao ha staging nem producao no ar — nao houve conta AWS disponivel para este
> desafio. O que isso implica (e o que custaria para produzir as evidencias)
> esta detalhado em [Limitacoes e pendencias](docs/LIMITACOES-E-PENDENCIAS.md).

## Stack

- Python 3.12, Django 5.1, Django REST Framework
- PostgreSQL 16
- Poetry (dependencias)
- Docker / docker-compose
- JWT (djangorestframework-simplejwt)
- GitHub Actions (CI/CD)
- Terraform (infraestrutura AWS, pronta para aplicar)

## Setup local (sem Docker)

Requisitos: Python 3.12, Poetry, um PostgreSQL acessivel.

```bash
poetry install
cp .env.example .env
# edite .env: aponte DATABASE_URL para o seu Postgres local
poetry run python manage.py migrate
poetry run python manage.py createsuperuser   # opcional, para /admin
poetry run python manage.py runserver
```

A API fica disponivel em `http://localhost:8000/api/`.

## Setup com Docker

Requisitos: Docker e Docker Compose.

```bash
cp .env.example .env
docker compose up --build
```

Isso sobe `db` (Postgres) e `web` (Django via gunicorn, com `collectstatic` e `migrate` executados automaticamente no entrypoint). A API fica em `http://localhost:8000/api/`.

> Nota: se voce ja tiver um PostgreSQL local ocupando a porta 5432, ajuste o mapeamento de porta do servico `db` em `docker-compose.yml` (ex.: `5433:5432`) e o `DATABASE_URL` do seu `.env` local de acordo — a rede interna do compose (`db:5432`, usada pelo container `web`) nao e afetada por essa mudanca.

## Autenticacao

A API usa JWT (`djangorestframework-simplejwt`). Todos os endpoints de negocio exigem um token valido.

```bash
# obter token
curl -X POST http://localhost:8000/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "seu_usuario", "password": "sua_senha"}'

# usar o token
curl http://localhost:8000/api/professionals/ -H "Authorization: Bearer <access_token>"

# renovar o token
curl -X POST http://localhost:8000/api/token/refresh/ \
  -H "Content-Type: application/json" -d '{"refresh": "<refresh_token>"}'
```

Crie um usuario com `manage.py createsuperuser` ou `manage.py shell` (`User.objects.create_user(...)`) — a API nao expõe endpoint de auto-registro de usuarios administrativos.

## Endpoints principais

| Metodo | Rota | Descricao |
|---|---|---|
| GET/POST | `/api/professionals/` | listar / criar profissionais |
| GET/PUT/PATCH/DELETE | `/api/professionals/{id}/` | detalhe / editar / excluir |
| GET | `/api/professionals/{id}/appointments/` | consultas de um profissional |
| GET/POST | `/api/appointments/` | listar (com `?profissional=<id>`) / criar consultas |
| GET/PUT/PATCH/DELETE | `/api/appointments/{id}/` | detalhe / editar / excluir |
| POST | `/api/token/`, `/api/token/refresh/` | obter / renovar JWT |
| GET | `/api/docs/`, `/api/redoc/` | documentacao interativa (Swagger/Redoc) |
| GET | `/api/health/` | liveness (publico) - usado pelo health check do ALB |
| GET | `/api/health/ready/` | readiness (publico) - verifica conexao com o banco; `503` se indisponivel |

Excluir um profissional que possui consultas vinculadas retorna `409 Conflict` (protegido via `on_delete=PROTECT`).

## Testes

```bash
poetry run python manage.py test
# com cobertura (configuracao em [tool.coverage.*] no pyproject.toml):
poetry run coverage run manage.py test
poetry run coverage report -m
poetry run coverage html   # relatorio navegavel em htmlcov/
```

**39 testes (`APITestCase`), 100% de cobertura de linhas e branches.** Cobrem CRUD de profissionais e consultas, autenticacao JWT (obtencao/renovacao/rejeicao/blacklist na rotacao), health checks, tratamento de erro 5xx, busca de consultas por profissional, e casos de erro (payload invalido, IDs inexistentes, exclusao bloqueada por integridade referencial). Os testes rodam contra um Postgres real (nunca SQLite/mocks), tanto localmente quanto no CI, para manter paridade com producao.

Relatorio completo e o que cada teste verifica: [docs/COBERTURA-DE-TESTES.md](docs/COBERTURA-DE-TESTES.md).

## CI/CD

- **`.github/workflows/ci.yml`** — roda em todo PR e push para `develop`/`main`: `lint` (ruff + black --check) seguido de `test` (suite completa contra um container `postgres:16` de servico, mais relatorio de cobertura).
- **`.github/workflows/cd-cloudrun.yml`** — **o pipeline de deploy que roda de ponta a ponta hoje.** Implanta no ambiente de demonstracao (Cloud Run) a cada push na `main`, com autenticacao via Workload Identity Federation (OIDC, sem chave estatica), smoke test pos-deploy em `/api/health/ready/` e rollback por revision via `workflow_dispatch`. Setup em [docs/DEPLOY-DEMO-CLOUD-RUN.md](docs/DEPLOY-DEMO-CLOUD-RUN.md).
- **`.github/workflows/cd.yml`** — build da imagem, push para ECR, e deploy no ECS Fargate. `workflow_dispatch` com escolha de ambiente, ou `image_tag` especifico para reimplantar uma imagem ja publicada (usado no rollback). **O gatilho por push esta desligado de proposito:** a infra Terraform nunca foi aplicada, entao disparar a cada push apenas reportaria build vermelho num pipeline correto que nao tem onde implantar. Basta restaurar o bloco `push` comentado no arquivo quando houver conta AWS — ai `develop` implanta em staging e `main` em producao, atras de um GitHub Environment com aprovacao manual.

Secrets/variaveis necessarios no repositorio GitHub: `GCP_WIF_PROVIDER`, `GCP_SERVICE_ACCOUNT` e `GCP_PROJECT_ID` para o pipeline do Cloud Run; `AWS_DEPLOY_ROLE_ARN` (role assumida via OIDC — evita chaves de acesso longas-vividas). A lista completa de secrets, variaveis e permissoes IAM minimas esta em [docs/CONFIGURACAO.md](docs/CONFIGURACAO.md).

Onde encontrar as evidencias de cada execucao (relatorio de cobertura, tag publicada, revisao da task definition, smoke test pos-deploy, aprovacao de producao): [docs/DEPLOY-E-ROLLBACK.md](docs/DEPLOY-E-ROLLBACK.md).

## Deploy (AWS)

**Importante:** a infraestrutura Terraform em `infra/` esta pronta para ser aplicada (`terraform validate` passa em ambos os ambientes), mas **nao foi aplicada** neste exercicio — nao ha credenciais AWS disponiveis no ambiente onde este desafio foi desenvolvido. O fluxo abaixo descreve como aplicar-la com uma conta real.

### Arquitetura

ECS Fargate reaproveitando a VPC default da conta (sem VPC/NAT customizados, para reduzir custo e complexidade). Cada ambiente (staging/production) tem seu proprio cluster ECS, servico, Application Load Balancer e instancia RDS Postgres — isolamento total entre ambientes, inclusive de estado Terraform. Segredos (`SECRET_KEY`, senha do banco, chave de assinatura JWT) ficam no AWS Secrets Manager e sao injetados na task definition via bloco `secrets` (nunca como variavel de ambiente em texto puro); configuracao nao sensivel fica no SSM Parameter Store.

```
infra/
  modules/{network,ecr,rds,ecs-service,secrets}/   # recursos reutilizaveis
  envs/{staging,production}/                        # composicao por ambiente + backend S3 proprio
```

### Aplicando pela primeira vez

```bash
# 1. bootstrap do backend remoto (uma vez, fora do Terraform)
aws s3api create-bucket --bucket medical-appointments-api-tfstate --region us-east-1
aws dynamodb create-table --table-name terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST

# 2. staging primeiro (cria o repositorio ECR compartilhado)
cd infra/envs/staging
terraform init
terraform apply -var-file=staging.tfvars

# 3. producao
cd ../production
terraform init
terraform apply -var-file=production.tfvars
```

O primeiro apply sobe cada servico com uma imagem placeholder (`nginx`); o primeiro push do pipeline `cd.yml` substitui isso por uma nova revisao de task definition apontando para a imagem real.

### Rollback

Duas formas, ambas documentadas para uso imediato em incidentes:

1. **Rapida (linha de comando)** — reverter o servico ECS para a revisao anterior da task definition:
   ```bash
   aws ecs update-service --cluster medapp-production-cluster \
     --service medapp-production --task-definition medapp-production:<revisao-anterior>
   ```
2. **Auditavel (via GitHub Actions)** — reexecutar o workflow de deploy apontando para uma tag de imagem ja publicada anteriormente:
   ```bash
   gh workflow run cd.yml -f environment=production -f image_tag=production-<sha-anterior>
   ```
   Fica registrado no historico de Actions quem disparou o rollback e quando.

Como as tags do ECR sao imutaveis (`image_tag_mutability = "IMMUTABLE"`), reimplantar uma tag anterior e deterministico — nao ha rebuild, a mesma imagem volta ao ar.

Procedimento completo, com os comandos de cada passo, validacao pos-rollback, tempos esperados e o que o rollback de imagem **nao** desfaz (migrations de banco): [docs/DEPLOY-E-ROLLBACK.md](docs/DEPLOY-E-ROLLBACK.md).

## Justificativas tecnicas

- **JWT em vez de API Key/token simples**: suporta expiracao curta de access token + refresh, revogacao via blacklist, e e o padrao de fato para APIs REST publicas — mais defensavel como "producao-ready" que um header de API Key estatico.
- **Um unico `settings.py` orientado a variaveis de ambiente** (via `django-environ`) em vez de `settings/local.py`, `settings/production.py`, etc.: o mesmo artefato de imagem Docker roda em local/staging/producao sem rebuild, apenas variando env vars — reduz o risco classico de "funciona em staging, quebra em producao" por divergencia de codigo entre settings.
- **PostgreSQL tambem em testes/CI** (nunca SQLite): evita falsos positivos por diferencas de comportamento entre engines (constraints, tipos, `ON DELETE PROTECT`).
- **`on_delete=PROTECT` em `Appointment.profissional`**: exclusao de profissional com consultas vinculadas retorna erro (409) em vez de apagar ou desvincular consultas silenciosamente — perda de dados clinicos e considerada inaceitavel por padrao.
- **Apenas ORM do Django, sem `.raw()`/`.extra()`**: toda query e parametrizada automaticamente, eliminando a superficie de SQL Injection por construcao.
- **ECS Fargate em vez de Elastic Beanstalk/App Runner**: sem servidores para corrigir, suporte de primeira classe no provider Terraform da AWS, rollback natural via revisao de task definition — bom equilibrio entre simplicidade e controle para demonstrar IaC.
- **Um cluster/estado Terraform por ambiente** (em vez de um cluster único compartilhado entre dois estados): isolamento total evita que uma alteracao em staging arrisque producao, e cada ambiente pode ser destruido/recriado independentemente.

## Proposta de integracao com a Asaas (split de pagamento)

Nao implementada em codigo neste desafio — proposta arquitetural:

1. Cada `HealthProfessional` ganharia um `asaas_wallet_id` (subconta/carteira Asaas do profissional), cadastrado no onboarding.
2. Ao confirmar uma `Appointment` como paga, a API criaria uma cobranca via `POST /v3/payments` da Asaas com `split` apontando um percentual/valor fixo para o `wallet_id` do profissional e o restante retido pela plataforma (comissao).
3. Um endpoint `POST /api/webhooks/asaas/` receberia notificacoes assincronas da Asaas (`PAYMENT_RECEIVED`, `PAYMENT_CONFIRMED`) para atualizar o status financeiro da consulta — validado por assinatura/token compartilhado, nunca confiando apenas no payload.
4. Segredos da Asaas (API key) seguiriam o mesmo padrao ja usado para `SECRET_KEY`/JWT: AWS Secrets Manager, nunca em variavel de ambiente plana ou versionada.

## Decisoes, limitacoes e melhorias futuras

- Terraform em `infra/` foi validado (`terraform validate`, `fmt`) mas **nao aplicado**, e o CD **nunca foi executado contra uma conta AWS real** — nao havia conta/credenciais AWS disponiveis neste desafio. Nao ha, portanto, link de staging nem de producao para apresentar. O estado item a item, o custo estimado dos ambientes e o roteiro para produzir as evidencias estao em [docs/LIMITACOES-E-PENDENCIAS.md](docs/LIMITACOES-E-PENDENCIAS.md).
- Pendencias de seguranca declaradas (principalmente **ausencia de TLS/HTTPS no ALB** e de rate limiting): [docs/SEGURANCA.md](docs/SEGURANCA.md).
- Melhorias futuras de regras de negocio (conflito de horario, timezone, duracao e status da consulta): [docs/LIMITACOES-E-PENDENCIAS.md](docs/LIMITACOES-E-PENDENCIAS.md), secao 4.
- `django-environ` com um unico `settings.py` foi escolhido por simplicidade; em um time maior, `settings/base.py` + overrides por ambiente pode ser preferivel para configuracoes que divergem estruturalmente (nao so por valor) entre ambientes.
- Nao ha rate limiting nem MFA na autenticacao — razoavel para o escopo do desafio, mas seria a proxima adicao de seguranca antes de um lancamento real (`django-ratelimit` ou throttling nativo do DRF).
- A busca de consultas por profissional esta disponivel tanto como filtro (`?profissional=<id>`) quanto como rota aninhada (`/professionals/{id}/appointments/`) — redundante de proposito, para cobrir tanto integradores que preferem query params quanto os que preferem rotas RESTful aninhadas.
- O usuario autenticado via JWT e um `django.contrib.auth.User` generico (sem papel/role); um proximo passo natural seria diferenciar "profissional" de "administrativo" com permissoes DRF dedicadas.
