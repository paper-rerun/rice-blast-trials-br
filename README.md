# Rice blast management trials in Brazil

2,990 trial results from 55 trials on managing rice blast (*Pyricularia oryzae*, teleomorph *Magnaporthe oryzae*, "brusone") in upland and irrigated rice (*Oryza sativa*) in Brazil, taken from the tables of 20 open-access Embrapa publications: foliar fungicide, seed treatment, resistant cultivars and lines, silicon, nitrogen and potassium, sowing date, furrow irrigation and induced resistance. Each row is one number exactly as printed, with the page and table it came from, and points to the trial it belongs to.

Rice is a staple food in most Brazilian households. Much of the trial evidence on keeping blast under control sits in regional bulletins, journal articles and congress papers, several of them scanned. This dataset makes 20 of them searchable and comparable, from Roraima and Amazonas to Rio Grande do Sul.

Part of [Paper Rerun](https://paper-rerun.github.io), in its Open Tables line. The work was done by AI agents on a home computer and reviewed by a human before publication.

## What is in it

| | |
|---|---|
| Publications | 20 (Alice and Infoteca-e, Embrapa's open repositories), 1983 to 2023 |
| Trials | 55 (51 field, 3 greenhouse, 1 laboratory), in Goiás, Tocantins, Rio Grande do Sul, Amazonas, Roraima, Pará and Maranhão |
| Records | 2,990 (leaf and panicle blast scores, severity and incidence, grain yield, milling yield, other diseases, plant traits, economics and others) |

Files:
- `data/rice_blast_trials.csv`: the dataset, one record per printed value, with `doc_id` and `trial_id`. Columns are described in `method/schema.json`.
- `data/rice_blast_trials_context.csv`: one row per trial (place, season, sowing date, crop system, cultivar, blast pressure, spray timing, spacing, design). Join on `doc_id` + `trial_id`; an empty context field in a record means the trial's value applies.
- `data/sources.csv`: the 20 publications, with authors, record link and licence notice.
- `qa/decisions.csv`: every disagreement between the two independent transcriptions and how it was settled against the PDF (3,544 decisions, with page).
- `method/`: the schema, the comparison script and the merge script.

## How it was made

1. **Collection.** An agent searched Embrapa's open repositories for publications with quantitative trial tables on this topic and downloaded 20, recording every candidate it did not take, with the reason.
2. **Two independent transcriptions.** Two agents per publication transcribed the trial context, the labels that apply to a whole table (which statistic, which test, what the letters mean, when the crop was assessed) and every table cell on the topic into a fixed schema, without seeing each other's work, copying numbers exactly as printed and accounting for every data cell.
3. **Comparison and adjudication.** A script paired the two transcriptions, trial by trial, table by table and record by record, and listed every disagreement and every value present in only one of them. Each one was settled by checking the PDF, with the page as evidence.

## How accurate it is

- **Numbers:** no value was misread in either transcription. All 2,990 paired values matched as printed, and 2,949 (98.6%) also matched on the significance letter; the other 41 were asterisks that one transcription put in the notes instead of the letter field.
- **Context and labels:** one transcription alone was fully correct on 89.2% and 79.8% of records. The errors were mostly rules applied to the wrong row or column, such as the assessment stage of a column measured at a different time from the rest of its table. All 3,544 disagreements were settled against the PDF, so the dataset does not depend on either transcription alone.
- **Known limits:** values shown only in charts without printed numbers were not read. Six older documents are scans with no usable text layer and were read from the rendered page. One document, santos1989 (germplasm in Amazonas), holds 609 records, 20% of the dataset. santos2005 prints the dose of liquid Mancozeb as "5,01", "6,01" and "4,01"; the trailing 1 is probably an "l" for litres, but it was kept as printed, with a note on the record.

## Licence and citation

- The dataset (the CSV files, schema and scripts) is released under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Please cite the original publications listed in `data/sources.csv` as well as this dataset.
- The publications are not redistributed. Embrapa's repositories show a CC BY-NC-ND 4.0 notice; journal articles and congress papers keep their own terms, and one article (souza2021) prints an author copyright with a Creative Commons Attribution licence. Only numbers, which are facts, and short citations are used here.

Errors or missing trials: please [open an issue](https://github.com/paper-rerun/rice-blast-trials-br/issues).

## How this dataset was made

This dataset was built by AI agents (Claude, by Anthropic) on a home computer and reviewed by a human before publication. No value was estimated or typed by hand: each one was transcribed from the source PDF twice, independently, and every disagreement was checked against the page. The method and scripts are in `method/`. How the wider project works: https://github.com/paper-rerun/paper-rerun/blob/main/METHOD.md

Contact: Filipe Tessaro, via issues on this repository.
