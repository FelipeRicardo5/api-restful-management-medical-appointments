# Configuracao: secrets, variaveis e onde cada uma vive

Nenhum valor sensivel real aparece neste repositorio. Esta pagina lista **quais**
chaves existem, **onde** cada uma e armazenada por ambiente e **como** chega no
processo Django — os valores ficam no AWS Secrets Manager / SSM Parameter Store
(nuvem) ou em `.env` local (ignorado pelo git).

## 1. Variaveis lidas pela aplicacao

Fonte da verdade: `config/settings.py` (via `django-environ`).

| Variavel | Sensivel | Default no codigo | Para que serve |
|---|---|---|---|
| `SECRET_KEY` | **Sim** | `django-insecure-change-me-in-env-file` | Assinatura de sessoes/CSRF do Django |
| `JWT_SIGNING_KEY` | **Sim** | cai para `SECRET_KEY` | Assinatura dos tokens JWT (separada de proposito: rotacionar JWT nao invalida sessoes admin) |
| `DATABASE_URL` | **Sim** (embute a senha) | `postgres://postgres:postgres@localhost:5432/medical_appointments` | Conexao Postgres, formato 12-factor |
| `DEBUG` | Nao | `False` | Nunca `True` fora do local |
| `ALLOWED_HOSTS` | Nao | `localhost,127.0.0.1` | Hosts aceitos pelo Django |
| `CORS_ALLOWED_ORIGINS` | Nao | `[]` (vazio = nenhuma origem cross-site) | Allowlist de origens do browser |
| `DJANGO_LOG_LEVEL` | Nao | `INFO` | Nivel do logger `django` |
| `JWT_ACCESS_TOKEN_MINUTES` | Nao | `15` | Validade do access token |
| `JWT_REFRESH_TOKEN_DAYS` | Nao | `7` | Validade do refresh token |
| `SECURE_SSL_REDIRECT` | Nao | `False` | Redireciona HTTP -> HTTPS |
| `SESSION_COOKIE_SECURE` | Nao | `not DEBUG` | Cookie de sessao so sobre HTTPS |
| `CSRF_COOKIE_SECURE` | Nao | `not DEBUG` | Cookie CSRF so sobre HTTPS |

> Os defaults de `SECRET_KEY` e `DATABASE_URL` existem apenas para o
> desenvolvimento local nao exigir setup. Em staging/producao ambos sao
> **sempre** sobrescritos pelo Secrets Manager (ver secao 3).

## 2. Ambiente local

```bash
cp .env.example .env   # preencher com valores de desenvolvimento
docker compose up -d db
```

`.env` esta em `.gitignore` e nunca e versionado. `.env.example` e o contrato:
contem todas as chaves com placeholders, nenhum valor real.

## 3. Staging e producao (AWS)

Criados por `infra/modules/secrets/main.tf`. Os valores de `SECRET_KEY`,
`JWT_SIGNING_KEY` e senha do banco sao gerados pelo proprio Terraform
(`random_password`) — **ninguem digita nem ve esses valores**, e eles nao
transitam pelo GitHub Actions.

### 3.1 AWS Secrets Manager (sensiveis)

| Secret | Injetado como | Origem do valor |
|---|---|---|
| `medapp/<env>/django-secret-key` | `SECRET_KEY` | `random_password`, 50 chars |
| `medapp/<env>/jwt-signing-key` | `JWT_SIGNING_KEY` | `random_password`, 50 chars |
| `medapp/<env>/db-password` | (nao injetado direto) | `random_password`, 32 chars |
| `medapp/<env>/database-url` | `DATABASE_URL` | URL montada com a senha acima |

`<env>` = `staging` ou `production`. Cada ambiente tem seu proprio conjunto:
o segredo de staging nao abre producao.

Entram no container pelo bloco `secrets` da task definition ECS — o valor e
resolvido pelo agente do ECS no momento do start e **nunca** aparece em
`aws ecs describe-task-definition`, em log de deploy ou em variavel de
ambiente em texto puro no Terraform state de superficie.

### 3.2 SSM Parameter Store (nao sensiveis)

`/medapp/<env>/DEBUG`, `/medapp/<env>/ALLOWED_HOSTS`,
`/medapp/<env>/CORS_ALLOWED_ORIGINS`, `/medapp/<env>/DJANGO_LOG_LEVEL`.

Ficam no Parameter Store para serem centralizados e auditaveis sem pagar o
custo por segredo do Secrets Manager. Os mesmos quatro valores tambem vao no
bloco `environment` da task definition.

### 3.3 Variaveis por ambiente (`infra/envs/*/*.tfvars`)

| Variavel Terraform | staging | production |
|---|---|---|
| `aws_region` | `us-east-1` | `us-east-1` |
| `environment` | `staging` | `production` |
| `db_instance_class` | `db.t3.micro` | `db.t3.small` |
| `desired_count` (tasks ECS) | `1` | `2` |
| `multi_az` (RDS) | `false` | `true` |
| `allowed_hosts` | `*.elb.amazonaws.com` | `*.elb.amazonaws.com` |
| `cors_allowed_origins` | vazio | vazio |

## 4. GitHub Actions

### 4.1 Repository secrets

| Secret | Obrigatorio | Conteudo |
|---|---|---|
| `AWS_DEPLOY_ROLE_ARN` | Sim | ARN da role IAM assumida via OIDC. **Nao ha access key nem secret key no repositorio** — a autenticacao usa `permissions: id-token: write` + `aws-actions/configure-aws-credentials@v4`, com credenciais temporarias por execucao |

Para o pipeline do Cloud Run (`cd-cloudrun.yml`), que e o que roda de ponta a
ponta hoje:

| Secret | Obrigatorio | Conteudo |
|---|---|---|
| `GCP_WIF_PROVIDER` | Sim | Provider do Workload Identity Federation, no formato `projects/<numero>/locations/global/workloadIdentityPools/github/providers/github-provider` |
| `GCP_SERVICE_ACCOUNT` | Sim | E-mail da service account de deploy (`github-deployer@<projeto>.iam.gserviceaccount.com`) |
| `GCP_PROJECT_ID` | Sim | ID do projeto GCP |

Tambem OIDC, sem chave JSON de service account no repositorio. O provider e
preso a **este** repositorio por `attribute-condition`, equivalente a restricao
do `sub` na trust policy do lado AWS. Comandos de criacao em
[DEPLOY-DEMO-CLOUD-RUN.md](DEPLOY-DEMO-CLOUD-RUN.md), secao "CI/CD".

### 4.2 GitHub Environments

| Environment | Usado por | Configuracao recomendada |
|---|---|---|
| `staging` | job `deploy-staging` | sem aprovacao manual |
| `production` | job `deploy-production` | **required reviewers** ligado — e o portao de aprovacao manual antes de producao |

### 4.3 Permissoes minimas da role de deploy

A role em `AWS_DEPLOY_ROLE_ARN` precisa de:

- `ecr:GetAuthorizationToken`, `ecr:BatchCheckLayerAvailability`,
  `ecr:InitiateLayerUpload`, `ecr:UploadLayerPart`, `ecr:CompleteLayerUpload`,
  `ecr:PutImage`, `ecr:DescribeRepositories` — build/push da imagem
- `ecs:DescribeTaskDefinition`, `ecs:RegisterTaskDefinition`,
  `ecs:UpdateService`, `ecs:DescribeServices` — deploy
- `iam:PassRole` restrito as roles `medapp-<env>-ecs-execution` e
  `medapp-<env>-ecs-task`
- `elasticloadbalancing:DescribeLoadBalancers` — resolver o DNS do ALB no
  smoke test pos-deploy

A trust policy deve restringir o `sub` do OIDC a este repositorio e aos branches
`main`/`develop`, para que outro repositorio nao consiga assumir a role.

### 4.4 Variaveis nao secretas do pipeline

Definidas direto em `.github/workflows/cd.yml` — precisam bater com o Terraform:

| Variavel | Valor | Recurso Terraform correspondente |
|---|---|---|
| `AWS_REGION` | `us-east-1` | `var.aws_region` |
| `ECR_REPOSITORY` | `medapp-api` | `modules/ecr` `repository_name = "${var.project}-api"` |
| cluster | `medapp-<env>-cluster` | `aws_ecs_cluster.this.name` |
| service | `medapp-<env>` | `aws_ecs_service.this.name` |

As credenciais do job de teste do CI (`SECRET_KEY: ci-test-secret-key`, etc.)
sao literais descartaveis de um Postgres efemero de service container — nao sao
secrets e nao dao acesso a nada.

## 5. Backend do Terraform

Precisa existir **antes** do primeiro `terraform init` (bootstrap manual, uma vez):

| Recurso | Nome | Funcao |
|---|---|---|
| Bucket S3 | `medical-appointments-api-tfstate` | Estado remoto, versionado e criptografado |
| Tabela DynamoDB | `terraform-locks` | Lock de estado (evita apply concorrente) |

O state contem valores sensiveis em texto puro (senha do RDS, chaves geradas).
Por isso: `encrypt = true`, bucket **privado**, versionamento ligado e acesso
restrito — nunca um bucket publico.
