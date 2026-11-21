# Operação

## Agendamento

`Collect jobs` roda no minuto 17 a cada quatro horas. O minuto evita a concentração comum de workflows no início da hora.

Para uma execução manual, abra **Actions**, selecione **Collect jobs** e use **Run workflow**. A primeira execução deve ser manual, depois da configuração dos secrets.

## Estados

- `succeeded`: todas as fontes responderam;
- `partial`: pelo menos uma fonte falhou, mas houve progresso;
- `failed`: nenhuma coleta confiável foi concluída;
- `running`: execução aberta há menos de 15 minutos;
- `stale`: não há sucesso há mais de seis horas.

## Diagnóstico

Os logs são JSON e incluem fonte, quantidades e identificador da execução. Comece pelo primeiro registro com nível `ERROR`. Nunca copie um token para os logs ao reproduzir uma falha.

Repositórios públicos podem ter workflows agendados desativados após 60 dias sem atividade. Quando o Kali mostrar `Atrasado`, confirme se o workflow continua habilitado antes de investigar as fontes.

## Rotação do token

1. Gere um token aleatório novo.
2. Atualize seu SHA-256 no Render.
3. Aguarde o deploy saudável da API.
4. Atualize `KALI_JOB_FINDER_TOKEN` no GitHub.
5. Execute o workflow manualmente.

O token anterior deixa de funcionar assim que o backend recebe o novo hash.
