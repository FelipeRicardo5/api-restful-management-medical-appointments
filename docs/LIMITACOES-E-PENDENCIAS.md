# Limitacoes, pendencias e melhorias futuras

Esta pagina existe para separar com clareza **o que esta pronto e verificavel**
do **que nao esta** — e, no segundo caso, dizer por que e qual seria o caminho.
Nada aqui esta apresentado como funcionando sem ter sido executado.

## 1. Estado real de cada entrega

| Entrega | Status | Evidencia |
|---|---|---|
| API REST (profissionais, consultas, JWT, filtros, paginacao, OpenAPI) | **Pronto e testado** | 39 testes, 100% de cobertura |
| Suite automatizada + relatorio de cobertura | **Pronto e executado** | [COBERTURA-DE-TESTES.md](COBERTURA-DE-TESTES.md) |
| Docker / docker-compose | **Pronto e executado** | build e `docker compose up` verificados localmente |
| Pipeline CI (lint + testes + cobertura) | **Pronto**, executado no GitHub Actions | execucoes do workflow `CI` |
| Pipeline CD (build, push ECR, deploy ECS, smoke test) | **Escrito, nunca executado contra AWS** | ver secao 2 |
| Terraform (VPC/SG, ECR, RDS, ECS Fargate, ALB, Secrets Manager, SSM) | **Escrito e validado, nunca aplicado** | `terraform validate` e `terraform fmt -check` passam; `terraform apply` **nao** foi executado |
| Ambientes staging e producao no ar | **Nao existem** | ver secao 2 |
| Health check / observabilidade da aplicacao | **Pronto e testado** | endpoints e logs verificados localmente ([OBSERVABILIDADE.md](OBSERVABILIDADE.md)) |
| Alarmes e dashboards CloudWatch | **Nao implementados** | recomendacao documentada, sem codigo |
| HTTPS/TLS | **Nao implementado** | ver secao 3 |

## 2. Por que nao ha ambientes AWS no ar

**Nao houve conta AWS com credenciais disponiveis para este desafio.** Isso e
uma limitacao de recursos declarada, nao um item esquecido. Duas consequencias
diretas e honestas:

1. **Nao existe link de staging nem de producao para apresentar.** Nenhum DNS de
   ALB foi gerado porque nenhum ALB foi criado.
2. **O CD nunca rodou de ponta a ponta.** O workflow esta escrito e e coerente
   com o Terraform (nomes de cluster, servico e repositorio ECR conferidos um a
   um), mas *coerente no papel* nao e o mesmo que *executado*. Um primeiro
   `apply` real quase certamente exporia ajustes de permissao IAM que so
   aparecem em execucao.

### Custo, que e a razao pratica

Provisionar os dois ambientes como estao especificados custa, em `us-east-1`,
on-demand (estimativa):

| Recurso | Staging | Producao |
|---|---|---|
| Application Load Balancer | ~US$ 17 | ~US$ 17 |
| ECS Fargate (0,5 vCPU / 1 GB) | 1 task, ~US$ 18 | 2 tasks, ~US$ 36 |
| RDS Postgres + 20 GB gp3 | `db.t3.micro` single-AZ, ~US$ 15 | `db.t3.small` **Multi-AZ**, ~US$ 55 |
| IPv4 publico (tasks + ALB) | ~US$ 11 | ~US$ 14 |
| Secrets Manager (3 segredos) | ~US$ 1 | ~US$ 1 |
| CloudWatch / ECR / S3 / DynamoDB | ~US$ 2 | ~US$ 3 |
| **Total/mes** | **~US$ 65** | **~US$ 130** |

**O free tier nao cobre esta arquitetura:** o Fargate nao tem free tier em
nenhum momento; o free tier de RDS cobre `db.t3.micro` **single-AZ** (serve para
staging, nao para a producao Multi-AZ); e o ALB so e gratuito nos 12 primeiros
meses da conta, para um unico balanceador — aqui sao dois.

### Como as evidencias podem ser produzidas

Rodar os dois ambientes por ~4 horas custa **menos de US$ 2**. O roteiro para
gerar as evidencias que faltam sem manter custo recorrente:

1. `terraform apply` em staging e producao (ordem importa — ver
   [DEPLOY-E-ROLLBACK.md](DEPLOY-E-ROLLBACK.md), secao 3).
2. Deixar o CD rodar: build, push, deploy, smoke test.
3. Capturar: DNS do ALB respondendo, `curl` nos health checks, execucao do
   pipeline verde, logs no CloudWatch, e **uma execucao real de rollback** pelo
   Caminho A.
4. `terraform destroy` nos dois ambientes.

O que fica registrado como pendente ate la: links vivos, print de pipeline verde
contra AWS real e registro de rollback executado.

## 3. Pendencias tecnicas conhecidas

### Infraestrutura

| Pendencia | Situacao | Encaminhamento |
|---|---|---|
| **TLS/HTTPS** | ALB so tem listener HTTP:80. JWT trafega em texto claro | Exige dominio registrado. Emitir certificado no ACM, adicionar listener 443 com redirect de 80, e so entao ligar `SECURE_SSL_REDIRECT=True` (liga-lo antes criaria loop de redirect) |
| **VPC default, subnets publicas** | Decisao de custo (evita NAT Gateway, ~US$ 32/mes por AZ). Isolamento vem do security group | VPC dedicada com subnets privadas para ECS e RDS |
| **`publicly_accessible` do RDS implicito** | Depende do default do provider | Declarar `publicly_accessible = false` em `infra/modules/rds/main.tf` |
| **Sem VPC endpoints** | Egress aberto para ECR/Secrets Manager/CloudWatch | Endpoints de interface para os tres servicos |
| **Sem alarmes/dashboards** | Metricas existem, ninguem e avisado | Alarmes do CloudWatch -> SNS (lista em [OBSERVABILIDADE.md](OBSERVABILIDADE.md), secao 4) |
| **Sem auto scaling** | `desired_count` fixo (1 staging / 2 producao) | Application Auto Scaling por `CPUUtilization` ou `RequestCountPerTarget` |
| **Bootstrap do backend manual** | O Terraform nao gerencia o proprio bucket de state | Inerente ao problema do ovo e da galinha; procedimento documentado |
| **`ALLOWED_HOSTS` amplo** | `*.elb.amazonaws.com` | Com dominio proprio, fixar o host exato |

### Aplicacao

| Pendencia | Situacao | Encaminhamento |
|---|---|---|
| **Rate limiting** | Ausente em `/api/token/` | Throttling do DRF ou `django-ratelimit` |
| **Papeis/permissoes** | Usuario autenticado tem CRUD total; nao ha distincao profissional vs. administrativo | Permission classes dedicadas por perfil |
| **MFA** | Ausente | Fora do escopo |
| **Migrations no entrypoint** | Com 2 tasks, ambas rodam `migrate` no deploy. O lock do Postgres evita corrupcao, mas e frageis | Passo dedicado no pipeline (ECS `run-task` one-off antes do rollout) |
| **Admin publico** | `/admin/` exposto no ALB | IP allowlist, VPN, ou remover da rota publica |
| **Sem APM** | So CloudWatch | Sentry como primeira adicao |

O detalhamento de risco de cada item de seguranca esta em
[SEGURANCA.md](SEGURANCA.md), secao 8.

### Correcoes feitas durante esta revisao

Tres defeitos reais encontrados e corrigidos — registrados aqui porque
explicam diferencas em relacao a entrega anterior:

1. **Blacklist de JWT era um no-op.** `BLACKLIST_AFTER_ROTATION = True` sem o app
   `rest_framework_simplejwt.token_blacklist` em `INSTALLED_APPS`: o SimpleJWT
   engole a chamada num `except AttributeError: pass`, e o refresh token
   rotacionado continuava valido pelos 7 dias. App instalado + teste de
   regressao que faz replay do token antigo.
2. **Nomes do CD nao batiam com o Terraform.** O workflow usava
   `ECR_REPOSITORY: medical-appointments-api` (Terraform cria `medapp-api`) e
   `ECS_CLUSTER: medapp-cluster` (Terraform cria `medapp-staging-cluster` e
   `medapp-production-cluster`). **O deploy teria falhado na primeira execucao.**
   Corrigido nos dois pontos.
3. **Health check apontava para rota inexistente como probe.** O target group
   usava `/api/schema/` — a rota do OpenAPI, que responde 200 sem dizer nada
   sobre a saude do servico e carrega o gerador de schema a cada 30s. Endpoints
   dedicados implementados.

## 4. Melhorias futuras de regras de negocio

O modelo atual (`Appointment` com `data` + `profissional`) atende ao escopo
pedido, mas e deliberadamente minimo. As regras abaixo sao as que um sistema
real de agendamento exige, na ordem em que eu as implementaria.

### 4.1 Prevencao de conflito de horario (prioridade mais alta)

**Hoje:** nada impede criar duas consultas para o mesmo profissional no mesmo
horario. E o defeito funcional mais relevante do dominio.

**Implementacao em duas camadas — ambas necessarias:**

1. **Validacao no serializer**, para a mensagem de erro util:

```python
def validate(self, attrs):
    inicio = attrs["data"]
    fim = inicio + attrs.get("duracao", DURACAO_PADRAO)
    conflito = Appointment.objects.filter(
        profissional=attrs["profissional"],
        status__in=[Status.AGENDADA, Status.CONFIRMADA],
        data__lt=fim,
    ).exclude(pk=self.instance.pk if self.instance else None)
    # sobreposicao real: inicio_existente < fim_novo AND fim_existente > inicio_novo
    if any(c.data + c.duracao > inicio for c in conflito):
        raise serializers.ValidationError(
            {"data": "Ja existe consulta para este profissional neste horario."}
        )
    return attrs
```

2. **Constraint no banco**, porque validacao em serializer perde a corrida
   quando duas requisicoes chegam juntas. Com `btree_gist` no Postgres:

```python
class Meta:
    constraints = [
        ExclusionConstraint(
            name="sem_sobreposicao_por_profissional",
            expressions=[
                (F("profissional"), RangeOperators.EQUAL),
                (TsTzRange("data", End("data", "duracao")), RangeOperators.OVERLAPS),
            ],
            condition=Q(status__in=["agendada", "confirmada"]),
        )
    ]
```

A condicao importa: consulta cancelada nao deve bloquear o horario.

### 4.2 Padronizacao de timezone

**Hoje:** `USE_TZ = True` e `TIME_ZONE = "America/Sao_Paulo"`. O banco armazena
UTC corretamente, mas o DRF serializa convertendo para o fuso do servidor — a
API responde com offset `-03:00`.

**Problema:** o cliente precisa saber qual fuso o servidor assume, e o horario de
verao (se voltar a existir) muda o offset sem aviso.

**Encaminhamento:** fixar a fronteira da API em **UTC/ISO 8601 com `Z`**
(`DATETIME_FORMAT` e `TIME_ZONE = "UTC"` no `REST_FRAMEWORK`), deixando a
localizacao para o cliente. Se a agenda passar a considerar horario comercial do
profissional, adicionar `timezone` por profissional — um profissional em Manaus
tem expediente diferente de um em Sao Paulo, e isso e dado do profissional, nao
do servidor.

### 4.3 Duracao da consulta

**Hoje:** consulta e um instante, nao um intervalo. Sem duracao, "conflito de
horario" nao tem definicao precisa.

**Encaminhamento:** `duracao = models.DurationField(default=timedelta(minutes=30))`,
com `duracao_padrao` por profissional (uma sessao de psicologia raramente dura o
mesmo que uma consulta clinica). Um `data_fim` como propriedade calculada evita
denormalizar. Esta e **pre-condicao** de 4.1 — a constraint de exclusao precisa
de um intervalo.

### 4.4 Status da consulta

**Hoje:** consulta existe ou e deletada. Nao ha como registrar cancelamento,
falta do paciente ou conclusao — e deletar perde o historico, que num contexto de
saude tem valor clinico e administrativo.

**Encaminhamento:** `TextChoices` com `AGENDADA`, `CONFIRMADA`, `REALIZADA`,
`CANCELADA`, `NAO_COMPARECEU`, com transicoes validadas (de `REALIZADA` nao se
volta para `AGENDADA`). O `DELETE` passa a ser soft delete via status, mantendo
o historico. Integra com 4.1: so status ativos ocupam horario.

### 4.5 Outras regras de dominio

| Regra | Motivo |
|---|---|
| Agenda/disponibilidade do profissional | Impedir agendamento fora do expediente ou em dia nao atendido |
| Antecedencia minima | Bloquear agendamento para daqui a 5 minutos |
| Janela maxima | Impedir agendamento com 3 anos de antecedencia |
| Limite de consultas por dia | Evitar overbooking mesmo sem conflito direto |
| Entidade paciente | Hoje a consulta so aponta para o profissional; nao ha quem e atendido |
| Historico de alteracoes | Auditoria de quem remarcou/cancelou e quando — relevante em saude |
| Notificacao/lembrete | Reduz falta, mas exige fila assincrona (Celery/SQS) |

### 4.6 Integracao de pagamentos (Asaas)

Ja descrita no README como proposta de arquitetura: `asaas_wallet_id` por
profissional, split no `POST /v3/payments` ao confirmar consulta paga, webhook
`POST /api/webhooks/asaas/` validado por assinatura, e a API key da Asaas no
Secrets Manager seguindo o mesmo padrao de `SECRET_KEY`/JWT. Depende de 4.4:
so faz sentido cobrar consulta com status definido.
