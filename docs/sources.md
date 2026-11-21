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

O coletor consulta apenas os cartões públicos de vagas brasileiras publicados nos últimos sete dias. Cada combinação de tecnologia e senioridade gera uma consulta; não há login, cookies persistentes, acesso a perfis ou páginas de candidatos. Há um intervalo mínimo de três segundos entre consultas. Respostas `429` ou `999` usam retentativas com espera progressiva; se o bloqueio persistir, as outras fontes ainda são salvas e a execução fica marcada como parcial.

O LinkedIn não oferece uma API pública geral de busca de vagas. A manutenção desta integração pressupõe a autorização informada pelo mantenedor e deve ser desativada se essa autorização for revogada.

## Regra geográfica

- remoto: qualquer cidade;
- híbrido ou presencial: São Paulo, Guarulhos, Osasco, Barueri, Carapicuíba, Cotia, Taboão da Serra, Santana de Parnaíba, Santo André, São Bernardo do Campo, São Caetano do Sul, Diadema, Mauá, Mogi das Cruzes, Campinas, Valinhos, Vinhedo, Indaiatuba, Jundiaí, Itupeva, Louveira e Sorocaba;
- também são aceitos `Grande São Paulo`, `ABC Paulista`, `Alphaville`, `Região Metropolitana de São Paulo` e `Região Metropolitana de Campinas`, inclusive os equivalentes em inglês retornados pelas fontes;
- nomes como `Campinas e Região` são aceitos quando a cidade-base está na lista.
