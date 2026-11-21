# Fontes avaliadas

| Canal | Uso no projeto | Situação |
| --- | --- | --- |
| LinkedIn Jobs | busca pública brasileira | implementada com autorização confirmada pelo mantenedor; sem login ou dados de membros |
| Gupy | portal público brasileiro | implementada pela resposta pública renderizada pelo portal |
| Indeed Brasil | busca manual e alertas | sem coletor; integração depende de aprovação |
| ProgramaThor | vagas específicas para desenvolvimento | candidata a próxima integração |
| Comunidades do GitHub | issues públicas de vagas brasileiras | implementada com API oficial |
| Remotar | vagas remotas disponíveis no Brasil | candidata, dependendo de feed ou permissão |
| GeekHunter | matching entre profissionais e empresas | sem feed público confirmado |
| Vagas.com.br | vagas nacionais de várias áreas | depende de acesso permitido e estável |
| trampos | tecnologia e mercado digital | candidata, após validação de acesso |
| APInfo | vagas de tecnologia no Brasil | depende de acesso permitido e estável |

## Comunidades consultadas

- `backend-br/vagas`
- `frontendbr/vagas`
- `pydevbr/vagas`
- `soujava/vagas-java`
- `react-brasil/vagas`

A integração usa issues alteradas desde o cursor confirmado pelo backend. Pull requests são ignorados.

## Gupy

O coletor consulta uma busca por tecnologia, lê o `__NEXT_DATA__` entregue pelo próprio portal e limita a paginação por configuração. Não acessa candidaturas, currículos nem áreas autenticadas.

## LinkedIn

O coletor consulta apenas os cartões públicos de vagas brasileiras publicados nos últimos sete dias. Cada combinação de tecnologia e senioridade gera uma consulta; não há login, cookies persistentes, acesso a perfis ou páginas de candidatos. Respostas `429` ou `999` encerram a fonte como falha parcial, sem tentativa de contorno.

O LinkedIn não oferece uma API pública geral de busca de vagas. A manutenção desta integração pressupõe a autorização informada pelo mantenedor e deve ser desativada se essa autorização for revogada.

## Regra geográfica

- remoto: qualquer cidade;
- híbrido ou presencial: somente a cidade de São Paulo;
- `São Paulo e Região` não é considerado equivalente à cidade.
