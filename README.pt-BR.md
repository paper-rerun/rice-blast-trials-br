# Ensaios de manejo da brusone do arroz no Brasil

English version: [README.md](README.md)

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23649646.svg)](https://doi.org/10.5281/zenodo.23649646)

2.990 resultados de 55 ensaios sobre o manejo da brusone (*Pyricularia oryzae*, teleomorfo *Magnaporthe oryzae*) em arroz (*Oryza sativa*) de terras altas e irrigado no Brasil, tirados das tabelas de 20 publicações de acesso aberto da Embrapa: fungicida foliar, tratamento de sementes, cultivares e linhagens resistentes, silício, nitrogênio e potássio, época de semeadura, irrigação por sulcos e indução de resistência. Cada linha é um número exatamente como foi impresso, com a página e a tabela de onde saiu, e aponta para o ensaio a que pertence.

O arroz é alimento básico na maioria dos lares brasileiros. Boa parte dos dados de ensaios sobre como manter a brusone sob controle está em boletins regionais, artigos de periódicos e trabalhos de congresso, vários deles escaneados. Este dataset torna 20 deles pesquisáveis e comparáveis, de Roraima e do Amazonas ao Rio Grande do Sul.

Faz parte do [Paper Rerun](https://paper-rerun.github.io), na linha Open Tables. O trabalho foi feito por agentes de IA num computador doméstico e revisado por uma pessoa antes da publicação.

## O que tem

| | |
|---|---|
| Publicações | 20 (Alice e Infoteca-e, os repositórios abertos da Embrapa), 1983 a 2023 |
| Ensaios | 55 (51 de campo, 3 em casa de vegetação, 1 em laboratório), em Goiás, Tocantins, Rio Grande do Sul, Amazonas, Roraima, Pará e Maranhão |
| Registros | 2.990 (notas de brusone nas folhas e nas panículas, severidade e incidência, produtividade de grãos, rendimento de engenho, outras doenças, características da planta, dados econômicos e outros) |

Arquivos:
- `data/rice_blast_trials.csv`: o dataset, um registro por valor impresso, com `doc_id` e `trial_id`. As colunas estão descritas em `method/schema.json`.
- `data/rice_blast_trials_context.csv`: uma linha por ensaio (local, safra, data de semeadura, sistema de cultivo, cultivar, pressão de brusone, momento das aplicações, espaçamento, delineamento). Junte os dois arquivos por `doc_id` + `trial_id`; um campo de contexto vazio num registro significa que vale o valor do ensaio.
- `data/sources.csv`: as 20 publicações, com autores, link do registro e aviso de licença.
- `qa/decisions.csv`: cada divergência entre as duas transcrições independentes e como ela foi resolvida conferindo o PDF (3.544 decisões, com a página).
- `method/`: o schema, o script de comparação e o script de junção.

### Principais colunas

O arquivo está em UTF-8, com vírgula separando as colunas. Local, safra, sistema de cultivo, cultivar e delineamento de cada ensaio estão em `data/rice_blast_trials_context.csv`.

- `doc_id`: identificador da publicação de origem. Liga o registro a `data/sources.csv` e é também o nome do PDF, sem a extensão.
- `trial_id`: o ensaio a que o valor pertence, dentro da publicação. Com `doc_id`, liga o registro à sua linha no arquivo de contexto.
- `page`: página do PDF contada a partir de 1 (a primeira página do arquivo é 1), e não o número impresso na página. O rótulo da tabela está em `table_or_figure`, como impresso ("Tabela 3", "Quadro 1"), ou `text` quando o número está no corpo do texto.
- `treatment`: rótulo da linha ou da coluna exatamente como impresso (cultivar, código de linhagem, produto, dose, época de semeadura, "Testemunha", "Média"). Numa célula de fatorial, os níveis vêm unidos por " x ", na ordem da tabela.
- `biotic_target`: a doença que a variável mede: `blast` (brusone), `brown_spot` (mancha-parda), `grain_discoloration` (manchas de grãos), `leaf_scald` (escaldadura), `sheath_blight` (queima-das-bainhas), `narrow_brown_spot` (mancha-estreita) ou `multiple`, quando um valor cobre várias ("doenças foliares"). Em produtividade, grãos e planta, vale o alvo do ensaio; `none` só aparece quando o ensaio não maneja nenhuma doença.
- `variable`: variável medida, exatamente como no cabeçalho ou na legenda, com o momento quando ele faz parte do cabeçalho ("BF (%)", "Brusone nas panículas (%)", "AACPD", "Produtividade (kg ha-1)", "Nota (0-9)").
- `variable_standardized`: a mesma variável numa lista fechada. Alguns exemplos: `leaf_blast_score` e `leaf_blast_severity_pct` (brusone nas folhas, em nota ou em % de área foliar), `panicle_blast_score`, `panicle_blast_severity_pct` e `panicle_blast_incidence_pct` (brusone nas panículas ou no pescoço), `grain_yield_kg_ha` (produtividade de grãos em kg/ha), `milling_yield_pct` (rendimento de engenho e de grãos inteiros) e `other_disease_score` (nota de outra doença). A lista completa está em `method/schema.json`.
- `value_as_printed`: a célula exatamente como impressa, sem letras, marcas de rodapé ou termo de dispersão ("4.526", "12,5", "MR"). Quando `value_kind` é `class` (classe de reação) ou `illegible` (célula que não dá para ler com segurança), `value` fica vazio.
- `value`: o mesmo número pronto para cálculo, com ponto decimal e sem separador de milhar ("4.526" vira 4526, "12,5" vira 12.5). Nada foi calculado, convertido ou arredondado.
- `unit`: unidade como impressa ou informada na legenda ou no cabeçalho ("kg/ha", "kg ha-1", "sc/ha", "g", "%"). Vazia quando não há unidade impressa, como em notas e na AACPD.
- `statistic`: o que o número é: `mean` (média), `relative_to_check` (calculado pelos autores em relação à testemunha), `total`, `median`, `single_value` (uma parcela ou uma observação), `percentage_of_total` ou `other`. Quando o valor vem do rótulo da tabela inteira, `inherited_from_table` registra isso.
- `significance_letter`: letra(s) do teste de médias exatamente como impressas ("a", "AB", "a A", "bc"). Vazia quando não há. O teste e o significado das letras estão em `significance_test` e `letters_meaning`.

## Como foi feito

1. **Coleta.** Um agente buscou nos repositórios abertos da Embrapa publicações com tabelas de ensaios quantitativos sobre o tema e baixou 20, registrando cada candidata que não entrou, com o motivo.
2. **Duas transcrições independentes.** Dois agentes por publicação transcreveram o contexto dos ensaios, os rótulos que valem para uma tabela inteira (qual estatística, qual teste, o que as letras significam, quando a cultura foi avaliada) e cada célula de tabela sobre o tema num schema fixo, sem ver o trabalho um do outro, copiando os números exatamente como impressos e prestando contas de cada célula de dados.
3. **Comparação e arbitragem.** Um script pareou as duas transcrições, ensaio por ensaio, tabela por tabela e registro por registro, e listou cada divergência e cada valor presente em só uma delas. Cada caso foi resolvido conferindo o PDF, com a página como evidência.

## Qual a precisão

- **Números:** nenhum valor foi lido errado em nenhuma das duas transcrições. Os 2.990 valores pareados bateram com o impresso, e 2.949 (98,6%) bateram também na letra de significância; nos outros 41, uma transcrição pôs o asterisco nas notas em vez do campo da letra.
- **Contexto e rótulos:** sozinha, uma transcrição estava totalmente correta em 89,2% dos registros, e a outra em 79,8%. Os erros foram, na maior parte, regras aplicadas à linha ou à coluna errada, como o estádio de avaliação de uma coluna medida num momento diferente do resto da tabela. As 3.544 divergências foram resolvidas conferindo o PDF, então o dataset não depende de nenhuma das duas transcrições sozinha.
- **Limites conhecidos:** valores mostrados só em gráficos, sem número impresso, não foram lidos. Seis documentos mais antigos são escaneados, sem camada de texto aproveitável, e foram lidos a partir da imagem da página. Um documento, santos1989 (germoplasma no Amazonas), tem 609 registros, 20% do dataset. santos2005 imprime a dose do Mancozeb líquido como "5,01", "6,01" e "4,01"; o 1 final provavelmente é um "l" de litros, mas foi mantido como impresso, com uma nota no registro.

## Licença e citação

- O dataset (os arquivos CSV, o schema e os scripts) é publicado sob a licença [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Por favor, cite as publicações originais listadas em `data/sources.csv` e também este dataset.
- As publicações não são redistribuídas. Os repositórios da Embrapa exibem um aviso CC BY-NC-ND 4.0; artigos de periódico e trabalhos de congresso mantêm os próprios termos, e um artigo (souza2021) traz copyright dos autores com licença Creative Commons Atribuição. Aqui são usados só os números, que são fatos, e citações curtas.

Erros ou ensaios que faltam: por favor, [abra uma issue](https://github.com/paper-rerun/rice-blast-trials-br/issues).

## Como este dataset foi feito

Este dataset foi montado por agentes de IA (Claude, da Anthropic) num computador doméstico e revisado por uma pessoa antes da publicação. Nenhum valor foi estimado ou digitado à mão: cada um foi transcrito do PDF original duas vezes, de forma independente, e cada divergência foi conferida na página. O método e os scripts estão em `method/`. Como funciona o projeto como um todo (em inglês): https://github.com/paper-rerun/paper-rerun/blob/main/METHOD.md

Contato: Filipe Tessaro, pelas issues deste repositório.
