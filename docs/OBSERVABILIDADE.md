# Observabilidade

Cobre logs, health checks, metricas, monitoramento e como consultar tudo isso na
AWS. O que esta implementado esta marcado com o arquivo; o que depende de
configuracao no console esta marcado como **a configurar**.

## 1. Health checks

Dois endpoints publicos (`apps/core/views.py`, rotas em `apps/core/urls.py`):

| Endpoint | Verifica | Resposta | Consumidor |
|---|---|---|---|
| `GET /api/health/` | so o processo | `200 {"status": "ok"}` | **Target group do ALB** |
| `GET /api/health/ready/` | processo + banco (`SELECT 1`) | `200 {"status":"ok","database":"ok"}` ou `503 {"status":"error","database":"error"}` | Smoke test do CD, diagnostico manual |

Ambos usam `AllowAny` e `authentication_classes = []` — o ALB nao tem credencial
para apresentar.

### Por que dois endpoints, e nao um

O health check do ALB aponta para o **liveness**, que nao toca em dependencia
externa. Se ele checasse o banco, um failover do RDS Multi-AZ (que dura alguns
segundos e e um evento *esperado*) marcaria **todas** as tasks como unhealthy
ao mesmo tempo; o ALB drenaria o servico inteiro e transformaria uma
indisponibilidade recuperavel de segundos numa queda total.

A conectividade com o banco continua sendo verificada — pelo `readiness`, chamado
como smoke test pos-deploy, onde falhar e exatamente o comportamento desejado
(ver [DEPLOY-E-ROLLBACK.md](DEPLOY-E-ROLLBACK.md)).

Configuracao do target group (`infra/modules/ecs-service/main.tf`):
`path = "/api/health/"`, `matcher = 200`, intervalo 30s, timeout 5s,
2 checks para saudavel, 3 para nao saudavel.

### Verificacao local

```bash
docker compose up -d
curl -i http://localhost:8000/api/health/
curl -i http://localhost:8000/api/health/ready/
```

Os tres cenarios (liveness, readiness OK e readiness com banco fora, via mock)
estao cobertos por teste em `apps/core/tests.py::HealthCheckTests`.

## 2. Logs

### Formato e destino

`config/settings.py` configura **apenas handler de console**. Isso e deliberado:
em container, `stdout`/`stderr` sao capturados pelo runtime e enviados ao
CloudWatch pelo log driver — handler de arquivo dentro do container geraria log
que morre junto com a task e exigiria rotacao manual.

Formato: `%(asctime)s %(levelname)s %(name)s %(message)s`.

| Logger | Nivel | O que emite |
|---|---|---|
| `apps.core.access` | INFO | 1 linha por requisicao: metodo, path, status, duracao em ms (`apps/core/middleware.py`) |
| `apps.core.exceptions` | ERROR | Toda resposta 5xx; excecao nao tratada sai com stacktrace completo |
| `apps.core.health` | ERROR | Falha do readiness check (banco inalcancavel) |
| `django` | `DJANGO_LOG_LEVEL` (default INFO) | Log do framework |
| `django.request` | ERROR | Erros de requisicao do Django |
| raiz | INFO | Resto |

Exemplo de linha de acesso (saida real da suite de testes):

```
2026-09-18 10:41:32,681 INFO apps.core.access GET /api/professionals/ 200 15.0ms
```

### Onde ficam na AWS

Log group por ambiente, criado pelo Terraform
(`infra/modules/ecs-service/main.tf`):

| Ambiente | Log group | Retencao |
|---|---|---|
| staging | `/ecs/medapp-staging` | 14 dias |
| producao | `/ecs/medapp-production` | 14 dias |

Stream prefix `api`, um stream por task (`api/api/<task-id>`).

### Consultar os logs

```bash
# Seguir em tempo real
aws logs tail /ecs/medapp-production --follow

# Ultima hora, so erros
aws logs tail /ecs/medapp-production --since 1h --filter-pattern "ERROR"

# Requisicoes que retornaram 5xx
aws logs tail /ecs/medapp-production --since 1h --filter-pattern "\" 50\""

# Listar os streams (um por task) mais recentes
aws logs describe-log-streams \
  --log-group-name /ecs/medapp-production \
  --order-by LastEventTime --descending --max-items 5
```

CloudWatch Logs Insights — latencia e volume por status, a partir da linha de
acesso do middleware:

```
fields @timestamp, @message
| filter @message like /apps.core.access/
| parse @message "* * apps.core.access * * * *ms" as ts, lvl, method, path, code, dur
| stats count(*) as reqs, avg(dur) as avg_ms, pct(dur, 95) as p95_ms by code
| sort reqs desc
```

Endpoints mais lentos:

```
fields @timestamp, @message
| filter @message like /apps.core.access/
| parse @message "* * apps.core.access * * * *ms" as ts, lvl, method, path, code, dur
| stats avg(dur) as avg_ms, max(dur) as max_ms, count(*) as reqs by method, path
| sort avg_ms desc
| limit 20
```

No console: **CloudWatch > Log groups > `/ecs/medapp-production`**, ou
**CloudWatch > Logs Insights** para as queries acima.

## 3. Metricas

### Ja coletadas automaticamente (sem custo adicional)

| Origem | Metricas uteis | Namespace |
|---|---|---|
| **ALB** | `RequestCount`, `TargetResponseTime`, `HTTPCode_Target_5XX_Count`, `HTTPCode_Target_4XX_Count`, `HealthyHostCount`, `UnHealthyHostCount` | `AWS/ApplicationELB` |
| **ECS** | `CPUUtilization`, `MemoryUtilization`, `RunningTaskCount` | `AWS/ECS` |
| **RDS** | `CPUUtilization`, `DatabaseConnections`, `FreeStorageSpace`, `FreeableMemory`, `ReadLatency`, `WriteLatency` | `AWS/RDS` |

Consulta por CLI:

```bash
# p95 de latencia do ALB na ultima hora
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApplicationELB \
  --metric-name TargetResponseTime \
  --dimensions Name=LoadBalancer,Value=<app/medapp-production-alb/xxxx> \
  --start-time "$(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ)" \
  --end-time "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --period 300 --extended-statistics p95

# Hosts saudaveis agora (0 = servico fora)
aws cloudwatch get-metric-statistics \
  --namespace AWS/ApplicationELB --metric-name HealthyHostCount \
  --dimensions Name=TargetGroup,Value=<targetgroup/medapp-production-tg/xxxx> \
  --start-time "$(date -u -d '10 minutes ago' +%Y-%m-%dT%H:%M:%SZ)" \
  --end-time "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --period 60 --statistics Minimum
```

### Latencia por endpoint na aplicacao

O `RequestLoggingMiddleware` mede a duracao de **toda** requisicao e emite no
log. Isso cobre o caso que `TargetResponseTime` do ALB nao separa: latencia por
rota. As queries do Logs Insights na secao 2 extraem media, p95 e maximo por
`method`/`path` sem nenhuma instrumentacao adicional.

### A configurar (nao implementado)

- **Metricas de negocio** (consultas criadas por dia, profissionais ativos):
  exigiriam `EMF`/`put-metric-data` ou um exporter — nao implementado.
- **Prometheus/OpenTelemetry**: `django-prometheus` expondo `/metrics`, ou
  OTel com AWS Distro. Fora do escopo do desafio.
- **Tracing distribuido** (X-Ray): so agrega com mais de um servico; hoje ha
  um unico servico + banco.

## 4. Alarmes e monitoramento

**Nao implementados no Terraform.** Estao listados aqui como a configuracao
minima recomendada, para que a ausencia seja explicita e nao passe por
esquecimento:

| Alarme | Condicao sugerida | Por que importa |
|---|---|---|
| Servico fora do ar | `HealthyHostCount < 1` por 2 periodos de 1 min | Sinal mais direto de indisponibilidade |
| Taxa de erro | `HTTPCode_Target_5XX_Count > 5` em 5 min | Deploy ruim ou dependencia quebrada |
| Latencia | `TargetResponseTime` p95 > 1s por 5 min | Degradacao antes de virar queda |
| CPU do ECS | `CPUUtilization > 80%` por 10 min | Precisa escalar |
| Memoria do ECS | `MemoryUtilization > 85%` por 10 min | Risco de OOM kill da task |
| Espaco do RDS | `FreeStorageSpace < 2 GB` | Banco cheio derruba escrita |
| Conexoes do RDS | `DatabaseConnections` proximo do maximo da classe | Esgotamento de pool |

Destino: SNS topic -> e-mail/Slack. Um dashboard do CloudWatch reunindo
`RequestCount`, `TargetResponseTime`, `HTTPCode_Target_5XX_Count`,
`HealthyHostCount`, CPU/memoria do ECS e CPU/conexoes do RDS da a visao de uma
tela por ambiente.

Nao ha APM (Datadog/New Relic/Sentry) — para o escopo do desafio, CloudWatch
cobre logs e metricas sem custo extra de ferramenta. **Sentry seria a primeira
adicao real**, por agrupar excecoes e notificar por regressao em vez de por
volume de log.

## 5. Diagnostico rapido: "a API caiu"

```bash
ENV=production   # ou staging

# 1. O ALB enxerga alguma task saudavel?
aws elbv2 describe-target-health \
  --target-group-arn "$(aws elbv2 describe-target-groups \
      --names medapp-$ENV-tg --query 'TargetGroups[0].TargetGroupArn' --output text)"

# 2. Quantas tasks estao rodando vs. desejadas?
aws ecs describe-services --cluster medapp-$ENV-cluster --services medapp-$ENV \
  --query 'services[0].{desired:desiredCount,running:runningCount,pending:pendingCount}'

# 3. Por que a ultima task parou? (motivo de OOM, exit code, falha de pull)
aws ecs list-tasks --cluster medapp-$ENV-cluster --desired-status STOPPED --max-items 1

# 4. O que o app logou?
aws logs tail /ecs/medapp-$ENV --since 30m --filter-pattern "ERROR"

# 5. O app consegue falar com o banco?
DNS=$(aws elbv2 describe-load-balancers --names medapp-$ENV-alb \
        --query 'LoadBalancers[0].DNSName' --output text)
curl -i "http://$DNS/api/health/ready/"
```

O passo 5 separa as duas causas mais comuns: `200` indica que app e banco estao
de pe (problema esta no ALB/rede); `503` aponta direto para o banco.
