# job-finder

`job-finder` coleta vagas públicas que correspondem ao perfil configurado no Kali. Ele roda como uma tarefa curta, normaliza os resultados e os envia para a API do projeto. O banco de dados e as credenciais do usuário não ficam neste repositório.

A primeira fonte implementada usa issues públicas de comunidades brasileiras no GitHub. Não há automação de LinkedIn, Indeed ou de qualquer plataforma que não ofereça uma forma permitida e estável de acesso.

## Fluxo

1. O GitHub Actions inicia uma execução no `kali-backend`.
2. A API devolve os critérios atuais e os cursores das fontes.
3. O coletor consulta as comunidades, classifica e remove resultados incompatíveis.
4. As vagas são enviadas em lotes idempotentes.
5. A execução é concluída com contagens e novos cursores.

O workflow agendado roda a cada quatro horas. Também pode ser iniciado manualmente na aba **Actions**.

## Requisitos

- Python 3.13
- uma API Kali com as rotas internas do monitor de vagas
- token do worker compartilhado com a API
- token do GitHub para execuções locais

## Execução local

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
cp .env.example .env
python -m job_finder --trigger manual
```

No PowerShell, ative o ambiente com `.venv\Scripts\Activate.ps1`.

## Qualidade

```bash
python -m pip install -e . pytest pytest-cov ruff mypy
ruff check .
mypy src
pytest
```

## Configuração no GitHub

Crie a variável `KALI_API_URL` e o secret `KALI_JOB_FINDER_TOKEN`. O workflow usa o `GITHUB_TOKEN` fornecido pelo próprio Actions.

Não salve tokens em `.env.example`, fixtures, logs ou arquivos de workflow.

## Documentação

- [Arquitetura](docs/architecture.md)
- [Adicionar uma fonte](docs/adding-a-source.md)
- [Operação](docs/operations.md)
- [Fontes avaliadas](docs/sources.md)

## Licença

MIT.
