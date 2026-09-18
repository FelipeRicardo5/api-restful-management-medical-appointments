# Checklist de seguranca por ambiente

Legenda: **OK** = implementado e verificavel no codigo · **Parcial** = implementado
com ressalva declarada · **Pendente** = nao implementado, com justificativa e
encaminhamento. Nada aqui esta marcado como pronto sem apontar o arquivo.

## 1. DEBUG

| Item | Local | Staging | Producao |
|---|---|---|---|
| `DEBUG` | `True` (via `.env`) | **`False`** | **`False`** |
| Origem do valor | `.env` (ignorado pelo git) | `environment` da task definition | `environment` da task definition |
| Default do codigo se a variavel sumir | `False` | `False` | `False` |

**OK.** `config/settings.py` declara `env.bool("DEBUG", default=False)` — o
default e o valor *seguro*, entao um erro de configuracao derruba para `False`,
nunca para `True`. `infra/envs/production/main.tf` e `infra/envs/staging/main.tf`
fixam `DEBUG = "False"` explicitamente no `plain_environment`.

Consequencia de `DEBUG=False` que vale registrar: paginas de erro nao vazam
stacktrace nem settings, e `ALLOWED_HOSTS` passa a ser efetivamente aplicado.

## 2. CORS

| Item | Local | Staging | Producao |
|---|---|---|---|
| `CORS_ALLOWED_ORIGINS` | `http://localhost:3000` | vazio | vazio |
| `CORS_ALLOW_ALL_ORIGINS` | nao usado | nao usado | nao usado |
| `CORS_ALLOW_CREDENTIALS` | `True` | `True` | `True` |

**OK, com ressalva.** Nao existe wildcard em lugar nenhum: a allowlist e
explicita (`config/settings.py`) e o default e lista **vazia** — sem origem
configurada, nenhuma origem cross-site e aceita. Hoje a API nao tem front-end
consumidor, por isso staging e producao estao com a lista vazia.

**Ressalva registrada:** `CORS_ALLOW_CREDENTIALS = True` so e seguro enquanto a
allowlist for explicita. A combinacao `CORS_ALLOW_CREDENTIALS = True` +
`CORS_ALLOW_ALL_ORIGINS = True` seria uma falha grave (qualquer site poderia
fazer requisicao autenticada em nome do usuario). Ao cadastrar o primeiro
front-end, preencher `cors_allowed_origins` no `.tfvars` do ambiente com o
dominio exato — **nunca** ligar o wildcard.

## 3. Autenticacao e autorizacao

| Item | Status | Onde |
|---|---|---|
| Todo endpoint de negocio exige JWT | **OK** | `DEFAULT_PERMISSION_CLASSES = IsAuthenticated` (global, opt-out explicito) |
| Health checks publicos por desenho | **OK** | `apps/core/views.py` — `AllowAny` + `authentication_classes = []`; o ALB nao tem credencial |
| Access token curto | **OK** | 15 min (`JWT_ACCESS_TOKEN_MINUTES`) |
| Refresh token | **OK** | 7 dias, com rotacao a cada uso |
| Rotacao invalida o token antigo | **OK** (corrigido) | ver abaixo |
| Chave do JWT separada da `SECRET_KEY` | **OK** | `JWT_SIGNING_KEY` proprio, secret distinto por ambiente |
| Validadores de senha do Django | **OK** | 4 validadores ativos |
| Rate limiting / throttling | **Pendente** | ver secao 8 |
| MFA | **Pendente** | ver secao 8 |
| Papeis/roles (profissional vs. administrativo) | **Pendente** | ver secao 8 |

**Falha encontrada e corrigida durante esta revisao:** `BLACKLIST_AFTER_ROTATION`
estava `True`, mas o app `rest_framework_simplejwt.token_blacklist` **nao estava**
em `INSTALLED_APPS`. O SimpleJWT so adiciona o comportamento de blacklist quando
esse app esta instalado e, quando nao esta, o `refresh.blacklist()` cai num
`except AttributeError: pass` — silenciosamente. Na pratica, um refresh token
roubado continuava valido pelos 7 dias inteiros mesmo depois de rotacionado.

Corrigido em `config/settings.py` (app instalado) e travado por teste de
regressao em `apps/core/tests.py`
(`JWTAuthFlowTests::test_rotated_refresh_token_is_blacklisted`), que faz o replay
do token antigo e exige `401`. O teste falha se o app for removido.

## 4. Gestao de secrets

| Item | Status | Onde |
|---|---|---|
| Nenhum secret versionado no git | **OK** | `.env` em `.gitignore`; `.env.example` so tem placeholders |
| Secrets em cofre gerenciado | **OK** | AWS Secrets Manager (`infra/modules/secrets/main.tf`) |
| Secrets nunca como env var em texto puro | **OK** | bloco `secrets` da task definition; resolvido pelo agente ECS no start |
| Secret por ambiente (sem reuso) | **OK** | namespace `medapp/<env>/...` — staging nao abre producao |
| Valores nunca vistos por humanos | **OK** | `random_password` do Terraform gera e grava direto no cofre |
| Sem access key estatica no CI | **OK** | OIDC + `id-token: write`, credencial temporaria por execucao |
| IAM de leitura restrito aos ARNs do proprio ambiente | **OK** | `data.aws_iam_policy_document.secrets_access` lista ARNs explicitos, sem `Resource: "*"` |
| Config nao sensivel separada dos secrets | **OK** | SSM Parameter Store |
| State do Terraform criptografado e privado | **Parcial** | `encrypt = true` no backend S3; **o bucket precisa ser criado privado e versionado no bootstrap manual** — o Terraform nao gerencia o proprio backend |
| Rotacao automatica de secrets | **Pendente** | ver secao 8 |

O detalhamento completo (nomes, destino, quem consome) esta em
[CONFIGURACAO.md](CONFIGURACAO.md).

## 5. Exposicao do banco de dados

| Item | Staging | Producao | Onde |
|---|---|---|---|
| Porta 5432 aberta para a internet | **Nao** | **Nao** | SG do RDS so aceita ingress do **security group das tasks ECS**, nao de CIDR |
| `publicly_accessible` | `false` (default) | `false` (default) | **Parcial** — e o default do provider, mas nao esta explicito no codigo |
| Criptografia em repouso | **OK** | **OK** | `storage_encrypted = true` |
| Backup automatico | 1 dia | **7 dias** | `backup_retention_period` |
| Multi-AZ | nao | **sim** | `multi_az` |
| Protecao contra delete acidental | nao | **sim** | `deletion_protection = true` |
| Snapshot final no destroy | nao (`skip_final_snapshot`) | **sim** | intencional: staging e descartavel |
| Credencial do banco | secret dedicado | secret dedicado | `medapp/<env>/db-password` |

**Ressalva registrada (2 itens):**

1. `publicly_accessible` depende do default do provider em vez de estar
   declarado. Deve ser fixado como `publicly_accessible = false` em
   `infra/modules/rds/main.tf` — configuracao de seguranca nao deve depender de
   default implicito, que pode mudar entre versoes do provider.
2. O RDS vive nas **subnets publicas da VPC default** (decisao de custo,
   documentada em `infra/modules/network/main.tf`: evita NAT Gateway). O
   isolamento efetivo vem do security group, nao da topologia de rede. Numa
   implantacao real com orcamento, o caminho correto e VPC dedicada com subnets
   privadas para RDS e ECS — ver [LIMITACOES-E-PENDENCIAS.md](LIMITACOES-E-PENDENCIAS.md).

## 6. Configuracoes de producao

| Item | Status | Onde / ressalva |
|---|---|---|
| `SECRET_KEY` forte e unica por ambiente | **OK** | 50 chars aleatorios por ambiente |
| `ALLOWED_HOSTS` restrito | **Parcial** | `*.elb.amazonaws.com` — restringe ao dominio da AWS, mas nao ao ALB especifico. Com dominio proprio, trocar pelo host exato |
| Container roda como usuario nao-root | **OK** | `Dockerfile` cria e usa `USER app` |
| Imagem base enxuta | **OK** | `python:3.12-slim`, multi-stage, sem Poetry no runtime |
| Scan de vulnerabilidade na imagem | **OK** | ECR `scan_on_push = true` |
| Tags de imagem imutaveis | **OK** | ECR `IMMUTABLE` — impede sobrescrever uma tag ja publicada; e o que torna o rollback por tag deterministico |
| Static files servidos com hash e compressao | **OK** | WhiteNoise `CompressedManifestStaticFilesStorage` |
| Erro 500 nao vaza stacktrace | **OK** | `apps/core/exceptions.py` retorna JSON generico e loga o detalhe |
| Aprovacao manual antes de producao | **OK** | GitHub Environment `production` com required reviewers |
| Migrations aplicadas no start | **OK, com ressalva** | `docker-entrypoint.sh`; ver secao 8 |
| **HTTPS/TLS** | **Pendente — principal lacuna** | ver abaixo |

### HTTPS e cookies seguros — lacuna conhecida

O ALB tem **apenas listener HTTP na porta 80**
(`infra/modules/ecs-service/main.tf`). Nao ha certificado ACM nem listener 443.
Em consequencia:

- `SECURE_SSL_REDIRECT` fica `False` — ligar redirect sem um listener HTTPS
  criaria um loop de redirecionamento, entao o valor esta **correto para a
  infra atual** e errado para uma producao real.
- `SESSION_COOKIE_SECURE` e `CSRF_COOKIE_SECURE` derivam de `not DEBUG`, ou seja,
  ja sao `True` em producao. Eles protegem os cookies, mas o **token JWT viaja
  em header sobre HTTP** e nao e coberto por isso.

**Isto e uma pendencia consciente, nao um descuido:** TLS exige um dominio
registrado para validar o certificado no ACM, e o desafio nao previa um. O
encaminhamento esta em [LIMITACOES-E-PENDENCIAS.md](LIMITACOES-E-PENDENCIAS.md)
com os passos exatos. **Nenhum dado real deve trafegar nesta infra antes disso.**

### Verificacao automatizada: `manage.py check --deploy`

O Django tem um check de seguranca proprio para deploy. Rodado com **a
configuracao de producao** (nao com o `.env` local), a saida completa esta em
[check-deploy.txt](check-deploy.txt) e reporta **2 warnings**:

| Warning | Causa | Situacao |
|---|---|---|
| `security.W008` — `SECURE_SSL_REDIRECT` nao e `True` | Nao ha listener HTTPS no ALB | Pendencia de TLS acima |
| `security.W004` — `SECURE_HSTS_SECONDS` nao definido | HSTS so faz sentido com HTTPS | Ligar junto com o TLS |

Ambos sao a **mesma** pendencia. Nenhum outro warning sobra: `DEBUG`,
`SECRET_KEY`, `ALLOWED_HOSTS` e os cookies seguros passam.

Reproduzir:

```bash
DEBUG=False   SECRET_KEY="$(python -c 'import secrets;print(secrets.token_urlsafe(50))')"   JWT_SIGNING_KEY="$(python -c 'import secrets;print(secrets.token_urlsafe(50))')"   ALLOWED_HOSTS="*.elb.amazonaws.com"   SESSION_COOKIE_SECURE=True CSRF_COOKIE_SECURE=True   python manage.py check --deploy
```

> Os cookies aparecem explicitos no comando apenas para neutralizar o `.env`
> local, que os fixa em `False` para desenvolvimento em HTTP. No container eles
> nao sao definidos — `.env` esta no `.dockerignore` — e caem no default
> `not DEBUG`, ou seja, `True` em producao.

### Django admin exposto

`/admin/` esta publicado no mesmo ALB publico (`config/urls.py`). Aceitavel no
escopo do desafio; em producao real deve ficar atras de IP allowlist, VPN, ou
ser removido da rota publica.

## 7. Rede

| Item | Status |
|---|---|
| ALB aceita 80 de `0.0.0.0/0` | **OK** (e o ponto de entrada publico por desenho) |
| Tasks ECS so aceitam trafego do SG do ALB | **OK** — ingress 8000 restrito ao `alb-sg`, nao a CIDR |
| RDS so aceita trafego do SG das tasks | **OK** |
| Tasks com IP publico | **Parcial** — `assign_public_ip = true`, necessario para puxar imagem do ECR sem NAT Gateway. O SG impede acesso direto de fora; o custo dessa economia e a task estar numa subnet publica |
| Egress irrestrito (`0.0.0.0/0`) | **Parcial** — necessario para ECR/Secrets Manager/CloudWatch sem VPC endpoints. Endurecer com VPC endpoints seria o proximo passo |

## 8. Pendencias de seguranca declaradas

Nenhuma destas esta implementada. Estao listadas para nao serem confundidas com
esquecimento:

| Pendencia | Risco atual | Encaminhamento |
|---|---|---|
| **TLS/HTTPS no ALB** | Trafego e JWT em texto claro | Registrar dominio, emitir certificado ACM, adicionar listener 443 + redirect 80->443, ligar `SECURE_SSL_REDIRECT=True` e `SECURE_HSTS_SECONDS` (os 2 unicos warnings de `check --deploy`) |
| **Rate limiting** | Forca bruta em `/api/token/` sem freio | Throttling nativo do DRF (`ScopedRateThrottle` no endpoint de token) ou `django-ratelimit` |
| **MFA** | Credencial unica protege tudo | Fora do escopo do desafio |
| **Roles/permissoes** | Todo usuario autenticado tem CRUD total | Diferenciar perfil profissional vs. administrativo com permission classes dedicadas |
| **Rotacao automatica de secrets** | Chave comprometida vale indefinidamente | Rotation lambda do Secrets Manager; `JWT_SIGNING_KEY` separado ja permite rotacionar JWT sem derrubar sessoes |
| **Migrations no entrypoint** | Com `desired_count > 1`, N tasks rodam `migrate` em paralelo no deploy | O lock do Postgres evita corrupcao, mas o correto e mover para um passo dedicado do pipeline (ECS run-task one-off antes do rollout) |
| **`publicly_accessible` implicito no RDS** | Depende do default do provider | Declarar `publicly_accessible = false` explicitamente |
| **Subnets publicas** | Isolamento depende so do SG | VPC dedicada com subnets privadas + NAT (tem custo) |
| **VPC endpoints** | Egress aberto para a internet | Endpoints para ECR, Secrets Manager, CloudWatch Logs |
| **Admin publico** | Superficie de ataque extra | IP allowlist / VPN / remover da rota publica |
