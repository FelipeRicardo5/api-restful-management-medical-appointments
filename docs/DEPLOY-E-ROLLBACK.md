# Deploy, evidencias do pipeline e rollback

## 1. Pipelines

### CI (`.github/workflows/ci.yml`)

Dispara em todo pull request e em push para `develop` e `main`.

| Job | Passos | Bloqueia o merge? |
|---|---|---|
| `lint` | `ruff check .`, `black --check .` | Sim |
| `test` | sobe Postgres 16 como service container, roda a suite sob `coverage`, gera `report -m`, `xml` e `html` | Sim |

O job `test` depende de `lint` (`needs: lint`) — nao gasta um Postgres se o
codigo nem passa no formatador.

**Onde ficam as evidencias do CI**, em cada execucao no GitHub Actions:

| Evidencia | Onde encontrar |
|---|---|
| Resultado dos 39 testes, um a um | log do passo *Run tests with coverage* (`--verbosity 2`) |
| Tabela de cobertura | **Summary** da execucao, secao "Cobertura de testes" |
| Relatorio HTML navegavel + `coverage.xml` | artefato `coverage-report` (retencao 30 dias) |
| Portao de cobertura | `fail_under = 95` no `pyproject.toml` — CI falha se cair abaixo |

Detalhes dos numeros em [COBERTURA-DE-TESTES.md](COBERTURA-DE-TESTES.md).

### CD (`.github/workflows/cd.yml`)

| Gatilho | Ambiente | Aprovacao manual |
|---|---|---|
| push em `develop` | staging | nao |
| push em `main` | producao | **sim** (GitHub Environment `production` com required reviewers) |
| `workflow_dispatch` | escolhido no formulario | conforme o environment |

Fluxo: `build-push` (build da imagem, push para o ECR com tag
`<env>-<sha-curto>`) -> `deploy-<env>` (baixa a task definition atual, troca so
a imagem, registra nova revisao, atualiza o servico com
`wait-for-service-stability`) -> **smoke test** (`GET /api/health/ready/` no DNS
do ALB, ate 10 tentativas com 10s de intervalo).

Autenticacao na AWS por **OIDC** (`permissions: id-token: write`), sem access key
estatica no repositorio.

**Onde ficam as evidencias do CD:**

| Evidencia | Onde encontrar |
|---|---|
| Tag da imagem publicada | saida `image_tag` do job `build-push` |
| Revisao da task definition registrada | log do passo *Deploy to ECS* |
| Servico estabilizado | o passo so conclui com `wait-for-service-stability: true` |
| Health check pos-deploy | log do passo *Smoke test*, com o codigo HTTP de cada tentativa |
| Aprovacao de producao | aba **Deployments** do repositorio: quem aprovou e quando |

> **Status atual:** o CD **nunca foi executado contra uma conta AWS real** — ver
> [LIMITACOES-E-PENDENCIAS.md](LIMITACOES-E-PENDENCIAS.md). Os passos acima
> descrevem o que o workflow faz e onde a evidencia aparece quando ele rodar.

## 2. Rollback

### Premissa que torna o rollback confiavel

O repositorio ECR usa `image_tag_mutability = "IMMUTABLE"`
(`infra/modules/ecr/main.tf`). Uma tag publicada **nao pode ser sobrescrita**.
Logo, `production-abc1234` sempre aponta para exatamente o mesmo binario — voltar
para essa tag e deterministico, e nao "provavelmente o codigo antigo".

A politica de ciclo de vida guarda as **10 ultimas imagens por prefixo de
ambiente**, entao ha sempre um conjunto de versoes anteriores disponivel.

### Caminho A — pelo pipeline (recomendado, deixa rastro)

Use quando o deploy ruim ja foi detectado e ha tempo para um ciclo de pipeline
(~3-5 min, sem rebuild).

**Passo 1 — descobrir para qual tag voltar.**

```bash
aws ecr describe-images --repository-name medapp-api \
  --query 'sort_by(imageDetails,&imagePushedAt)[-10:].{tag:imageTags[0],pushed:imagePushedAt}' \
  --output table
```

Escolha a ultima tag `production-*` anterior ao deploy problematico. Conferencia
cruzada: o SHA no fim da tag e o commit — `git log --oneline | grep <sha>`.

**Passo 2 — disparar o redeploy dessa tag.**

No GitHub: **Actions > CD > Run workflow**, preenchendo:

- `environment`: `production`
- `image_tag`: `production-abc1234` (a tag do passo 1)

Ou por CLI:

```bash
gh workflow run cd.yml \
  -f environment=production \
  -f image_tag=production-abc1234
```

Com `image_tag` preenchida, o job `build-push` e **pulado** (`if:` na definicao
do job) — nada e reconstruido, a imagem antiga ja existente no ECR e reimplantada
como esta. Isso elimina o risco de "rebuild do commit antigo sair diferente".

**Passo 3 — acompanhar.**

```bash
gh run watch
```

O passo *Deploy to ECS* espera a estabilizacao do servico e o *Smoke test*
confirma `200` em `/api/health/ready/`. Se o smoke test falhar, o job falha —
o rollback nao e dado como concluido em silencio.

**Passo 4 — confirmar manualmente.**

```bash
DNS=$(aws elbv2 describe-load-balancers --names medapp-production-alb \
        --query 'LoadBalancers[0].DNSName' --output text)
curl -i "http://$DNS/api/health/ready/"

aws ecs describe-services --cluster medapp-production-cluster \
  --services medapp-production \
  --query 'services[0].{taskDef:taskDefinition,running:runningCount,desired:desiredCount}'
```

### Caminho B — direto na AWS (emergencia, mais rapido)

Use quando o GitHub Actions esta indisponivel ou cada minuto conta. Volta para a
**revisao anterior da task definition**, sem passar pelo pipeline (~1-2 min).

**Passo 1 — ver a revisao atual e as anteriores.**

```bash
aws ecs describe-services --cluster medapp-production-cluster \
  --services medapp-production \
  --query 'services[0].taskDefinition' --output text
# ex.: arn:aws:ecs:us-east-1:123456789012:task-definition/medapp-production:42

aws ecs list-task-definitions --family-prefix medapp-production \
  --sort DESC --max-items 5 --query 'taskDefinitionArns' --output table
```

**Passo 2 — conferir qual imagem a revisao alvo usa** (antes de aplicar, nao
depois):

```bash
aws ecs describe-task-definition --task-definition medapp-production:41 \
  --query 'taskDefinition.containerDefinitions[0].image' --output text
```

**Passo 3 — apontar o servico para ela.**

```bash
aws ecs update-service \
  --cluster medapp-production-cluster \
  --service medapp-production \
  --task-definition medapp-production:41
```

**Passo 4 — esperar estabilizar e validar.**

```bash
aws ecs wait services-stable \
  --cluster medapp-production-cluster --services medapp-production

DNS=$(aws elbv2 describe-load-balancers --names medapp-production-alb \
        --query 'LoadBalancers[0].DNSName' --output text)
curl -i "http://$DNS/api/health/ready/"
```

**Passo 5 — reconciliar o repositorio.** O Caminho B deixa a AWS a frente do
git: o codigo em `main` continua sendo o que quebrou. Abrir `revert` do commit
problematico no mesmo dia, para que o proximo deploy de `main` nao reintroduza a
falha.

> O Terraform nao briga com nenhum dos dois caminhos: o `aws_ecs_service` tem
> `lifecycle { ignore_changes = [task_definition, desired_count] }` e a task
> definition tem `ignore_changes = [container_definitions]`. Um `terraform apply`
> depois do rollback **nao** reverte o rollback.

### O que o rollback de imagem NAO desfaz

**Migrations de banco.** O `docker-entrypoint.sh` roda `manage.py migrate` no
start de cada task. Voltar a imagem volta o codigo, **nao** o schema. Se o deploy
ruim aplicou uma migration destrutiva (drop de coluna, alteracao de tipo com
perda), o codigo antigo pode nao funcionar com o schema novo.

Regra operacional, por isso: **migrations devem ser sempre compativeis com a
versao anterior do codigo** (expand/contract — adicionar coluna nova nullable,
implantar, so entao remover a antiga num deploy seguinte). Migration destrutiva
e a unica situacao em que o rollback exige restaurar backup do RDS
(`backup_retention_period = 7` dias em producao), que e um procedimento de outra
ordem de grandeza — minutos a dezenas de minutos, com janela de indisponibilidade.

### Tempo esperado

| Caminho | Tempo tipico | Requer CI | Rastro de auditoria |
|---|---|---|---|
| A — pipeline com `image_tag` | 3-5 min | sim | completo (execucao + aprovacao) |
| B — `update-service` direto | 1-2 min | nao | CloudTrail apenas |
| Restore de backup do RDS | 10-40 min | nao | so em migration destrutiva |

### Como registrar a evidencia da execucao

Quando o rollback for exercitado numa conta real, o registro minimo esperado:

1. Link da execucao do CD com `image_tag` preenchida, mostrando `build-push` pulado.
2. Saida do passo *Smoke test* com `HTTP 200`.
3. `aws ecs describe-services ... --query 'services[0].deployments'` antes e
   depois, mostrando a troca de task definition.
4. Print do CloudWatch (`/ecs/medapp-production`) na janela do rollback.

## 3. Bootstrap (uma vez, antes do primeiro deploy)

```bash
# 1. Backend do Terraform (bucket privado e versionado + tabela de lock)
aws s3api create-bucket --bucket medical-appointments-api-tfstate --region us-east-1
aws s3api put-bucket-versioning --bucket medical-appointments-api-tfstate \
  --versioning-configuration Status=Enabled
aws s3api put-public-access-block --bucket medical-appointments-api-tfstate \
  --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
aws dynamodb create-table --table-name terraform-locks \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST

# 2. Staging primeiro: e o ambiente que cria o repositorio ECR compartilhado
cd infra/envs/staging && terraform init && terraform apply -var-file=staging.tfvars

# 3. Producao (le o ECR criado pelo staging)
cd ../production && terraform init && terraform apply -var-file=production.tfvars
```

A ordem importa: `infra/envs/production/main.tf` passa `create = false` ao modulo
ECR e faz `data` lookup do repositorio que o staging cria.

O primeiro `apply` sobe o servico com a imagem placeholder
(`public.ecr.aws/docker/library/nginx:latest`) — o ECR ainda esta vazio nesse
momento. A imagem real entra no primeiro deploy do CD, e a partir dai o
`ignore_changes = [container_definitions]` impede o Terraform de reverter para o
placeholder.
