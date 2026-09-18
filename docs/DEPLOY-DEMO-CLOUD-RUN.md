# Deploy do ambiente de demonstracao (Cloud Run + Neon) — sem custo

Ambiente publico e gratuito para demonstrar a API funcionando, com HTTPS real.

> **O que este ambiente comprova e o que nao comprova.** Comprova a aplicacao, a
> imagem Docker, as migrations e os health checks rodando em nuvem, com TLS.
> **Nao** comprova o Terraform nem o ECS — a infraestrutura AWS em `infra/`
> permanece validada e nao aplicada, como registrado em
> [LIMITACOES-E-PENDENCIAS.md](LIMITACOES-E-PENDENCIAS.md). Sao entregas
> distintas e devem ser apresentadas como tal.

Pre-requisitos: conta Google (para o Cloud Run) e conta Neon (Postgres gratuito).
O `gcloud` CLI precisa estar instalado — <https://cloud.google.com/sdk/docs/install>.

---

## Bloco 0 — Banco no Neon (navegador, ~2 min)

Unico passo que nao e linha de comando.

1. Acesse <https://neon.com> e crie uma conta.
2. **Create project** → nome `medapp`, regiao `AWS us-east-1` (ou a mais proxima).
3. Na tela do projeto, copie a **connection string** — formato:
   `postgresql://usuario:senha@ep-xxx.us-east-1.aws.neon.tech/neondb?sslmode=require`

Guarde essa string para o Bloco 1.

---

## Bloco 1 — Variaveis da sessao

Cole no terminal, **substituindo apenas as duas primeiras linhas**.

```bash
export NEON_URL="postgresql://COLE_AQUI_A_CONNECTION_STRING_DO_NEON"
export PROJECT_ID="medapp-demo-$RANDOM"

export REGION="us-east1"
export SERVICE="medapp-api"
export DJANGO_SECRET="$(python -c 'import secrets;print(secrets.token_urlsafe(50))')"
export JWT_SECRET="$(python -c 'import secrets;print(secrets.token_urlsafe(50))')"

echo "PROJECT_ID=$PROJECT_ID"
```

---

## Bloco 2 — Projeto e APIs no Google Cloud

```bash
gcloud auth login

gcloud projects create "$PROJECT_ID" --name="MedApp Demo"
gcloud config set project "$PROJECT_ID"
```

> Neste ponto o console pedira para **vincular uma conta de faturamento** ao
> projeto. E obrigatorio mesmo para uso gratuito, e serve so como verificacao —
> o free tier do Cloud Run (2 milhoes de requisicoes/mes, escala a zero) nao gera
> cobranca. Vincule em <https://console.cloud.google.com/billing> e siga.

```bash
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com
```

---

## Bloco 3 — Secrets no Secret Manager

Mesmo sendo um ambiente de demonstracao, os segredos nao vao como variavel de
ambiente em texto puro — mantendo a postura descrita em
[SEGURANCA.md](SEGURANCA.md).

```bash
printf '%s' "$DJANGO_SECRET" | gcloud secrets create medapp-secret-key --data-file=-
printf '%s' "$JWT_SECRET"    | gcloud secrets create medapp-jwt-key    --data-file=-
printf '%s' "$NEON_URL"      | gcloud secrets create medapp-database-url --data-file=-
```

Dar acesso de leitura a service account que o Cloud Run usa:

```bash
export PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
export RUNTIME_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

for SECRET in medapp-secret-key medapp-jwt-key medapp-database-url; do
  gcloud secrets add-iam-policy-binding "$SECRET" \
    --member="serviceAccount:${RUNTIME_SA}" \
    --role="roles/secretmanager.secretAccessor"
done
```

---

## Bloco 4 — Deploy

Constroi a imagem a partir do `Dockerfile` do repositorio e publica. Rode na
**raiz do projeto**.

```bash
gcloud run deploy "$SERVICE" \
  --source . \
  --region "$REGION" \
  --port 8000 \
  --allow-unauthenticated \
  --set-env-vars "DEBUG=False,ALLOWED_HOSTS=.run.app,USE_X_FORWARDED_PROTO=True,SECURE_SSL_REDIRECT=True,DJANGO_LOG_LEVEL=INFO" \
  --set-secrets "SECRET_KEY=medapp-secret-key:latest,JWT_SIGNING_KEY=medapp-jwt-key:latest,DATABASE_URL=medapp-database-url:latest"
```

O `docker-entrypoint.sh` roda `manage.py migrate` no start, entao o schema e
criado no Neon automaticamente no primeiro deploy.

Guardar a URL gerada:

```bash
export API_URL="$(gcloud run services describe "$SERVICE" --region "$REGION" --format='value(status.url)')"
echo "$API_URL"
```

---

## Bloco 5 — Verificacao

```bash
curl -i "$API_URL/api/health/"
curl -i "$API_URL/api/health/ready/"
```

Esperado: `200 {"status":"ok"}` e `200 {"status":"ok","database":"ok"}`.
O segundo confirma que a aplicacao alcanca o Neon.

Confirmar que rotas de negocio exigem autenticacao:

```bash
curl -i "$API_URL/api/professionals/"     # esperado: 401
```

Confirmar o redirect de HTTPS (o `-I` sobre http deve devolver 301):

```bash
curl -I "$(echo "$API_URL" | sed 's|https://|http://|')/api/health/"
```

---

## Bloco 6 — Usuario e teste ponta a ponta

Criar um superusuario dentro do container do Cloud Run nao e direto (nao ha
shell persistente). O caminho mais simples e criar o usuario a partir da sua
maquina, apontando para o mesmo banco Neon:

```bash
DATABASE_URL="$NEON_URL" DEBUG=False SECRET_KEY=tmp \
  python manage.py createsuperuser
```

Fluxo completo de autenticacao:

```bash
export TOKEN="$(curl -s -X POST "$API_URL/api/token/" \
  -H 'Content-Type: application/json' \
  -d '{"username":"SEU_USUARIO","password":"SUA_SENHA"}' \
  | python -c 'import sys,json;print(json.load(sys.stdin)["access"])')"

curl -s "$API_URL/api/professionals/" -H "Authorization: Bearer $TOKEN"

curl -s -X POST "$API_URL/api/professionals/" \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"nome_social":"Alex Souza","profissao":"Psicologia","endereco":"Rua das Flores, 100","contato":"alex@example.com"}'
```

Documentacao interativa: `$API_URL/api/docs/`

---

## Bloco 7 — Logs e monitoramento

```bash
# Ultimas 50 linhas
gcloud run services logs read "$SERVICE" --region "$REGION" --limit 50

# Acompanhar em tempo real
gcloud beta run services logs tail "$SERVICE" --region "$REGION"

# So erros
gcloud run services logs read "$SERVICE" --region "$REGION" --limit 100 \
  | grep ERROR
```

As linhas de acesso do `RequestLoggingMiddleware` (metodo, path, status,
duracao) aparecem aqui igual ao descrito em
[OBSERVABILIDADE.md](OBSERVABILIDADE.md) — o handler e de console, e o Cloud Run
captura stdout, exatamente como o ECS faria com o CloudWatch.

---

## Bloco 8 — Redeploy e rollback

Redeploy apos alterar codigo: repetir o Bloco 4.

O Cloud Run versiona automaticamente em **revisions**, entao o rollback tem o
mesmo formato do descrito para o ECS:

```bash
# Listar revisions
gcloud run revisions list --service "$SERVICE" --region "$REGION"

# Voltar 100% do trafego para uma revision anterior
gcloud run services update-traffic "$SERVICE" --region "$REGION" \
  --to-revisions medapp-api-00001-abc=100
```

---

## Bloco 9 — Remover tudo

```bash
gcloud run services delete "$SERVICE" --region "$REGION" --quiet
gcloud projects delete "$PROJECT_ID" --quiet
```

O projeto Neon se apaga pelo painel web.

---

## Custo

| Recurso | Free tier | Custo esperado |
|---|---|---|
| Cloud Run | 2M requisicoes/mes, 360k GB-s de memoria, escala a zero | US$ 0 |
| Cloud Build | 120 min de build/dia | US$ 0 |
| Artifact Registry | 0,5 GB | US$ 0 |
| Secret Manager | 6 secrets ativos, 10k acessos/mes | US$ 0 |
| Neon Postgres | 0,5 GB de storage | US$ 0 |

Com trafego de demonstracao, o total fica em **US$ 0/mes**. A conta de
faturamento e exigida como verificacao de identidade, nao por haver cobranca —
ainda assim, vale definir um **orcamento com alerta em US$ 1** em
<https://console.cloud.google.com/billing/budgets> para garantir que nenhuma
surpresa passe despercebida.

## Diferencas em relacao a arquitetura AWS

| Aspecto | AWS (Terraform, alvo) | Cloud Run (demonstracao) |
|---|---|---|
| Compute | ECS Fargate, 2 tasks fixas | Cloud Run, escala a zero |
| Banco | RDS Postgres Multi-AZ | Neon (Postgres gerenciado) |
| Entrada | ALB, **HTTP apenas** | HTTPS gerenciado, certificado automatico |
| Secrets | AWS Secrets Manager | GCP Secret Manager |
| Logs | CloudWatch Logs | Cloud Logging |
| IaC | Terraform versionado | comandos imperativos (ambiente descartavel) |
| Ambientes | staging + producao isolados | um unico ambiente |

A diferenca mais relevante e favoravel ao ambiente de demonstracao: **ele tem
HTTPS**, o que resolve na pratica a principal pendencia de seguranca registrada
para a infra AWS. Por isso `SECURE_SSL_REDIRECT=True` e
`USE_X_FORWARDED_PROTO=True` estao ligados no Bloco 4 — o Cloud Run termina o
TLS e encaminha em HTTP para o container, entao o Django precisa confiar no
cabecalho `X-Forwarded-Proto` para nao entrar em loop de redirecionamento.
Esse ajuste e opt-in por variavel de ambiente (`config/settings.py`): confiar no
cabecalho incondicionalmente permitiria a um cliente forjar HTTPS.
