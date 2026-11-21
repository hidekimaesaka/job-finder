# Arquitetura

## Responsabilidades

O `job-finder` consulta e normaliza fontes independentes. Ele não conhece o banco Neon, não serve páginas e não armazena estado local entre execuções.

O `kali-backend` autentica o worker, entrega os critérios, persiste vagas e execuções e resolve idempotência. O frontend apenas lê e altera dados por essa API.

```text
GitHub Actions -> job-finder -> kali-backend (Render) -> Neon
                                  ^
Kali static site -----------------+
```

## Execução

Uma execução começa com `POST /api/internal/v1/job-finder/runs`. A resposta contém um identificador, o perfil de busca e os cursores confirmados pela última execução bem-sucedida.

Cada adaptador devolve vagas normalizadas, cursores e estatísticas. Os lotes usam a chave `(source, external_id)`, portanto reenviar a mesma vaga atualiza o registro existente. O cursor só avança na conclusão; uma falha não cria uma lacuna silenciosa.

GitHub, Gupy e LinkedIn falham de forma independente. Se pelo menos uma fonte concluir, os dados válidos são enviados e a execução fica `partial`; nenhuma fonte pode impedir silenciosamente o avanço das demais.

## Falhas

- timeouts e respostas transitórias usam tentativas com backoff;
- uma fonte com erro produz execução parcial quando outras fontes funcionam;
- falha total encerra a execução sem apagar dados anteriores;
- execuções que permanecem abertas por mais de 15 minutos são abandonadas pelo backend;
- nenhum erro enviado à API inclui token ou corpo integral de resposta.

## Segurança

O worker envia um Bearer token aleatório. O GitHub guarda o valor e o Render guarda somente seu SHA-256. O token dá acesso apenas às rotas internas do monitor de vagas.

O repositório público contém nomes de variáveis e exemplos, nunca valores reais. A conexão do Neon permanece exclusiva do `kali-backend`.
