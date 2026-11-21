# Adicionar uma fonte

Uma fonte nova precisa ter uma API, feed ou autorização de coleta compatível com este uso. HTML público, sozinho, não é autorização para scraping.

## Checklist

1. Registrar em `docs/sources.md` a forma de acesso e os limites conhecidos.
2. Confirmar termos, `robots.txt` e política de armazenamento.
3. Definir um identificador externo estável e uma URL original.
4. Implementar o contrato `JobSource` sem dependência do backend.
5. Converter os dados para `NormalizedJob`; não enviar HTML nem descrições completas.
6. Tratar paginação, fechamento de vagas, rate limit e cursor incremental.
7. Adicionar fixtures sanitizadas para sucesso, página vazia, resposta inválida e limite excedido.
8. Garantir que uma falha nessa fonte não interrompa fontes independentes.

O matching de tecnologia e senioridade é compartilhado. Regras específicas da plataforma devem ficar no adaptador, não no runner.
